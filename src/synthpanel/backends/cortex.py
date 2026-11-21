"""Run a study entirely inside Snowflake with Cortex (Claude + Voyage embeddings).

No Anthropic or Voyage API keys are needed, nothing leaves the Snowflake account, and each
step persists to a stage, so a run is auditable and re-scorable without new LLM calls.

Pipeline (one SQL statement per step, each `COPY INTO @stage`):

1. `personas_sql`: draw the panel's personas from its marginals -> personas/<panel>/
2. `answers_sql`: build each prompt (same template as `prompts.py`) and call
   SNOWFLAKE.CORTEX.TRY_COMPLETE -> answers/<panel>/<cell>/
3. `score_sql`: parse the intent and choice lines, embed the intent sentence and anchors with
   EMBED_TEXT_1024, apply SSR exactly as `ssr.similarities_to_pmf` -> scored/<panel>/
4. `readout_sql` / `paired_sql`: per-cell summaries and within-persona deltas vs control.

Steps 2-3 can be re-run per cell. Persona draws in SQL use Snowflake RANDOM(seed) and are
not the same draws as `PersonaSampler` in Python; they are persisted in step 1 and reused.

The SQL can be run with any Snowflake client (e.g. `snowflake.connector`, see
`run_step`), or pasted into a worksheet.
"""

from __future__ import annotations

from dataclasses import dataclass

from synthpanel.personas import attribute_label
from synthpanel.prompts import PERSONA_INTRO
from synthpanel.study import Panel, Study

NL = "\n"


def lit(text: str) -> str:
    """Snowflake dollar-quoted literal (no escape processing inside)."""
    if "$$" in text or text.endswith("$"):
        raise ValueError("Text for a dollar-quoted literal may not contain '$$' or end with '$'")
    return f"$${text}$$"


def sq(text: str) -> str:
    """Single-quoted literal with backslashes and quotes escaped (for regex patterns)."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


@dataclass(frozen=True)
class Col:
    """A reference to a column/expression inside the generated SQL."""

    expr: str
    key: str  # key used when rendering the same template in Python


def prompt_parts(panel: Panel) -> list[str | Col]:
    """The user prompt as literal pieces and column references, in order.

    Mirrors `prompts.user_text`: concept_intro + stimulus + "\\n\\n" + persona block + question.
    """
    spec = panel.spec
    parts: list[str | Col] = [spec.concept_intro, Col("c.stimulus", "__stimulus__"), NL + NL + PERSONA_INTRO]
    attrs = list(panel.marginals)
    for i, name in enumerate(attrs):
        parts.append(f"- {attribute_label(name, spec.labels)}: ")
        parts.append(Col(f"p.v:{name}::string", name))
        if i < len(attrs) - 1:
            parts.append(NL)
    parts.append(NL + NL + spec.question + spec.tail())
    return parts


def render_parts(parts: list[str | Col], values: dict[str, str]) -> str:
    """Python rendering of `prompt_parts` (used to test SQL/Python parity)."""
    return "".join(values[p.key] if isinstance(p, Col) else p for p in parts)


def _concat(parts: list[str | Col]) -> str:
    return " || ".join(p.expr if isinstance(p, Col) else lit(p) for p in parts if p != "")


def _weighted_case(u: str, dist: dict[str, float]) -> str:
    total = sum(dist.values())
    cum, whens = 0.0, []
    items = list(dist.items())
    for value, w in items[:-1]:
        cum += w / total
        whens.append(f"WHEN {u} < {cum:.10f} THEN {lit(str(value))}")
    return f"CASE {' '.join(whens)} ELSE {lit(str(items[-1][0]))} END"


def personas_sql(panel: Panel, stage: str) -> str:
    attrs = list(panel.marginals)
    uniforms = ", ".join(
        f"UNIFORM(0::float, 1::float, RANDOM({panel.seed * 1000 + k + 1})) AS u{k}" for k in range(len(attrs)))
    fields = ", ".join(f"{lit(name)}, {_weighted_case(f'u{k}', panel.marginals[name])}" for k, name in enumerate(attrs))
    return f"""COPY INTO {stage}/personas/{panel.name}/ FROM (
  SELECT OBJECT_CONSTRUCT('persona_id', {lit(panel.name + '-')} || LPAD(idx::string, 4, '0'), {fields})
  FROM (SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS idx, {uniforms}
        FROM TABLE(GENERATOR(ROWCOUNT => {panel.n})))
) FILE_FORMAT = (TYPE = JSON COMPRESSION = GZIP) OVERWRITE = TRUE SINGLE = TRUE MAX_FILE_SIZE = 268435456"""


def answers_sql(study: Study, panel: Panel, cell_id: str, stage: str, max_personas: int | None = None) -> str:
    cell = panel.cell(cell_id)
    limit = f"WHERE p.v:persona_id::string < {lit(f'{panel.name}-{max_personas:04d}')}" if max_personas else ""
    return f"""COPY INTO {stage}/answers/{panel.name}/{cell_id}/ FROM (
  WITH p AS (SELECT $1 AS v FROM {stage}/personas/{panel.name}/),
  c AS (SELECT {lit(cell_id)} AS cell, {lit(cell.as_text())} AS stimulus),
  q AS (SELECT c.cell, p.v:persona_id::string AS persona_id, p.v AS persona, {_concat(prompt_parts(panel))} AS prompt
        FROM p CROSS JOIN c {limit}),
  r AS (SELECT q.*, SNOWFLAKE.CORTEX.TRY_COMPLETE({lit(study.model)},
          [{{'role': 'system', 'content': {lit(panel.spec.system_prompt)}}}, {{'role': 'user', 'content': q.prompt}}],
          {{'temperature': {study.temperature}, 'max_tokens': {study.max_tokens}}}) AS raw
        FROM q)
  SELECT OBJECT_CONSTRUCT('cell', cell, 'persona_id', persona_id, 'persona', persona,
           'answer', j:choices[0]:messages::string, 'model', j:model::string, 'usage', j:usage)
  FROM (SELECT r.*, TRY_PARSE_JSON(raw::string) AS j FROM r)
) FILE_FORMAT = (TYPE = JSON COMPRESSION = GZIP) OVERWRITE = TRUE SINGLE = TRUE MAX_FILE_SIZE = 268435456"""


WS = "CHR(32) || CHR(10) || CHR(13) || CHR(9)"


def _line_pat(label: str) -> str:
    return sq(rf"^[ \t*_`>#-]*{label}[ \t]*:[ \t]*([^\n]*)$")


def _line_value(expr: str, label: str) -> str:
    """Value of the last `label:` line (NULL if none). Mirrors choices.extract_line."""
    pat = _line_pat(label)
    return (f"TRIM(REGEXP_SUBSTR({expr}, {pat}, 1, GREATEST(REGEXP_COUNT({expr}, {pat}, 1, 'im'), 1), 'ime', 1),"
            f" ' *_`' || CHR(9) || CHR(13))")


def _remove_line(expr: str, label: str) -> str:
    return f"REGEXP_REPLACE({expr}, {_line_pat(label)}, '', 1, 0, 'im')"


def _parse_sql(panel: Panel, answer: str) -> dict[str, str]:
    """SQL expressions mirroring choices.parse_answer.

    Returns expressions for: clean (answer without labelled lines), intent_raw, choice_raw,
    and - over parsed0's columns - score_text and choice.
    """
    spec = panel.spec
    clean = answer
    for s in (spec.intent, spec.choice):
        if s:
            clean = _remove_line(clean, s.label)
    out = {"clean": f"TRIM({clean}, {WS})",
           "intent_raw": _line_value(answer, spec.intent.label) if spec.intent else "NULL",
           "choice_raw": f"LOWER(TRIM({_line_value(answer, spec.choice.label)}, ' *_`.' || {WS}))" if spec.choice else "NULL",
           "score_text": "IFF(LENGTH(intent_raw) > 0, intent_raw, answer)"}
    if spec.choice:
        whens = " ".join(f"WHEN STARTSWITH(choice_raw, {lit(o.lower())}) THEN {lit(o)}" for o in spec.choice.options)
        out["choice"] = f"COALESCE(CASE {whens} END, 'unparsed')"
    else:
        out["choice"] = "''"
    return out


def score_sql(study: Study, panel: Panel, stage: str, embed_model: str = "voyage-multilingual-2",
              epsilon: float = 0.0, temperature: float = 1.0) -> str:
    k = panel.anchors[0].n_points
    anchor_rows = ", ".join(f"({lit(a.name)}, {i + 1}, {lit(s)})" for a in panel.anchors for i, s in enumerate(a.statements))
    x = _parse_sql(panel, "v:answer::string")
    part = "PARTITION BY cell, persona_id, set_name"
    return f"""COPY INTO {stage}/scored/{panel.name}/ FROM (
  WITH a AS (SELECT $1 AS v FROM {stage}/answers/{panel.name}/),
  parsed0 AS (SELECT v:cell::string AS cell, v:persona_id::string AS persona_id, v:persona AS persona,
                     {x["clean"]} AS answer, {x["intent_raw"]} AS intent_raw, {x["choice_raw"]} AS choice_raw
              FROM a WHERE v:answer IS NOT NULL),
  parsed AS (SELECT cell, persona_id, persona, answer, {x["score_text"]} AS score_text, {x["choice"]} AS choice
             FROM parsed0),
  emb AS (SELECT cell, persona_id, SNOWFLAKE.CORTEX.EMBED_TEXT_1024({lit(embed_model)}, score_text) AS e
          FROM parsed WHERE LENGTH(score_text) > 0),
  anc AS (SELECT column1 AS set_name, column2 AS k, SNOWFLAKE.CORTEX.EMBED_TEXT_1024({lit(embed_model)}, column3) AS e
          FROM VALUES {anchor_rows}),
  sims AS (SELECT emb.cell, emb.persona_id, anc.set_name, anc.k, VECTOR_COSINE_SIMILARITY(emb.e, anc.e) AS s
           FROM emb CROSS JOIN anc),
  shifted AS (SELECT *, s - MIN(s) OVER ({part}) AS d,
                     ROW_NUMBER() OVER ({part} ORDER BY s, k) AS rn FROM sims),
  eps AS (SELECT *, d + IFF(rn = 1, {epsilon}, 0) AS d2 FROM shifted),
  pm AS (SELECT *, IFF(SUM(d2) OVER ({part}) > 0, d2 / SUM(d2) OVER ({part}), 1 / {k}) AS p0 FROM eps),
  pt AS (SELECT *, POWER(p0, {1.0 / temperature}) / SUM(POWER(p0, {1.0 / temperature})) OVER ({part}) AS p FROM pm),
  avg_p AS (SELECT cell, persona_id, k, AVG(p) AS p FROM pt GROUP BY cell, persona_id, k),
  wide AS (SELECT cell, persona_id, OBJECT_AGG('p' || k, p::variant) AS pmf, SUM(k * p) AS expected
           FROM avg_p GROUP BY cell, persona_id)
  SELECT OBJECT_CONSTRUCT('cell', w.cell, 'persona_id', w.persona_id, 'persona', x.persona, 'answer', x.answer,
                          'scored_text', x.score_text, 'choice', x.choice, 'pmf', w.pmf, 'expected', w.expected)
  FROM wide w JOIN parsed x USING (cell, persona_id)
) FILE_FORMAT = (TYPE = JSON COMPRESSION = GZIP) OVERWRITE = TRUE SINGLE = TRUE MAX_FILE_SIZE = 268435456"""


def _revenue_case(panel: Panel) -> str:
    whens = []
    for cell in panel.cells:
        for option, value in panel.revenue(cell.concept_id).items():
            whens.append(f"WHEN cell = {lit(cell.concept_id)} AND choice = {lit(option)} THEN {value}")
    return f"CASE {' '.join(whens)} END" if whens else "NULL"


def _scored_cte(panel: Panel, stage: str) -> str:
    k = panel.anchors[0].n_points
    return f"""s AS (SELECT $1:cell::string AS cell, $1:persona_id::string AS persona_id, $1:persona AS persona,
                $1:choice::string AS choice, $1:expected::float AS expected,
                $1:pmf:p{k}::float + $1:pmf:p{k - 1}::float AS top2
         FROM {stage}/scored/{panel.name}/),
  r AS (SELECT s.*, {_revenue_case(panel)} AS revenue FROM s)"""


def readout_sql(panel: Panel, stage: str, segment: str | None = None) -> str:
    seg_sel = f", persona:{segment}::string AS {segment}" if segment else ""
    seg_grp = f", {segment}" if segment else ""
    shares = ", ".join(f"ROUND(AVG(IFF(choice = {lit(o)}, 1, 0)), 3) AS {lit_ident(o)}"
                       for o in (panel.spec.choice.options if panel.spec.choice else ()))
    shares = (", " + shares) if shares else ""
    return f"""WITH {_scored_cte(panel, stage)},
  g AS (SELECT r.*{seg_sel} FROM r)
SELECT cell{seg_grp}, COUNT(*) AS n, ROUND(AVG(expected), 3) AS mean_intent, ROUND(AVG(top2), 3) AS top2box{shares},
       ROUND(AVG(IFF(choice = 'unparsed', 1, 0)), 3) AS unparsed, ROUND(AVG(revenue), 3) AS revenue_per_respondent
FROM g GROUP BY cell{seg_grp} ORDER BY cell{seg_grp}"""


def paired_sql(panel: Panel, stage: str) -> str:
    return f"""WITH {_scored_cte(panel, stage)},
  ctl AS (SELECT persona_id, revenue AS rev0, expected AS exp0, top2 AS top0 FROM r WHERE cell = {lit(panel.control)}),
  d AS (SELECT r.cell, r.revenue - ctl.rev0 AS d_rev, r.expected - ctl.exp0 AS d_int, r.top2 - ctl.top0 AS d_top2, ctl.rev0
        FROM r JOIN ctl USING (persona_id) WHERE r.cell <> {lit(panel.control)})
SELECT cell, COUNT(*) AS n_pairs,
       ROUND(AVG(d_rev), 3) AS d_revenue, ROUND(1.96 * STDDEV_SAMP(d_rev) / SQRT(COUNT(*)), 3) AS d_revenue_ci_half,
       ROUND(AVG(d_rev) / NULLIF(AVG(rev0), 0), 4) AS d_revenue_pct,
       ROUND(AVG(d_int), 3) AS d_intent, ROUND(1.96 * STDDEV_SAMP(d_int) / SQRT(COUNT(*)), 3) AS d_intent_ci_half,
       ROUND(AVG(d_top2), 3) AS d_top2box, ROUND(1.96 * STDDEV_SAMP(d_top2) / SQRT(COUNT(*)), 3) AS d_top2box_ci_half
FROM d GROUP BY cell ORDER BY cell"""


def switching_sql(panel: Panel, stage: str, cell: str) -> str:
    return f"""WITH {_scored_cte(panel, stage)}
SELECT a.choice AS control_choice, b.choice AS test_choice, COUNT(*) AS n
FROM r a JOIN r b ON a.persona_id = b.persona_id AND a.cell = {lit(panel.control)} AND b.cell = {lit(cell)}
GROUP BY 1, 2 ORDER BY 1, 2"""


def lit_ident(text: str) -> str:
    return '"' + text.replace('"', "") + '"'


def run_step(conn, sql: str) -> list[tuple]:
    """Execute one generated statement with a snowflake.connector connection."""
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()
