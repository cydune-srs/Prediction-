# synthpanel

Synthetic consumer panels that predict purchase intent for consumer products, using the
**Semantic Similarity Rating (SSR)** method from Maier et al., *"LLMs Reproduce Human Purchase
Intent via Semantic Similarity Elicitation of Likert Ratings"* (PyMC Labs and
Colgate-Palmolive). The platform also backtests synthetic intent against **realized purchases**
from SRS card and receipt data, a test the paper did not run.

## How it works

```
concepts.yaml ──┐
                ├─► Claude answers in free text as each persona ──► embed answer ──► cosine similarity
personas ───────┘   ("How likely would you be to purchase this?")      to Likert anchor statements
                                                                              │
                         per-answer distribution over 1..5  ◄─────────────────┘
                                         │
             aggregate by concept / segment: mean PI, top-2-box, full distribution
                                         │
        validate:  vs human survey (KS similarity, correlation attainment)
                   vs realized purchases (rank correlation, calibrated sales forecast)
```

The key idea from the paper: LLMs asked for a number give narrow, skewed rating
distributions. Asking for a short free-text answer and mapping it to the scale by embedding
similarity gives realistic distributions (KS similarity > 0.85 in the paper) and concept rankings
reaching about 90% of human test-retest reliability.

| Paper component | Module |
|---|---|
| Anchor statements per Likert point, several anchor sets averaged | `anchors.py` |
| Cosine similarity minus minimum, epsilon, temperature | `ssr.py` |
| Demographic personas (age, income, etc.) | `personas.py` |
| Concept shown as text or image | `concepts.py`, `prompts.py` |
| KS similarity, correlation attainment, split-half test-retest | `metrics.py` |
| Comparison with a human panel, SSR tuning | `validation/human.py` |
| Backtest against realized purchases (new) | `validation/realized.py`, `validation/sources.py` |

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,voyage]"      # or [local] for an on-machine embedder
pytest

# No API calls: exercises the pipeline with canned answers
synthpanel run --concepts examples/concepts_example.yaml --personas 50 --out runs/dry --dry-run

# Real run (needs ANTHROPIC_API_KEY, and VOYAGE_API_KEY for the default embedder)
synthpanel run --concepts examples/concepts_example.yaml --personas 300 --out runs/pet \
    --embedder voyage --mode batch

synthpanel compare-human --survey runs/pet --human human_ratings.csv
synthpanel backtest --survey runs/pet --outcomes outcomes.csv --outcome-col net_sales_usd --group-col category
```

Library use:

```python
from synthpanel import SSRScorer, PersonaSampler, load_concepts, run_survey
from synthpanel.embeddings import get_embedder
from synthpanel.respondents import ClaudeRespondent

result = run_survey(load_concepts("concepts.yaml"), PersonaSampler(seed=1).sample(300),
                    ClaudeRespondent(), SSRScorer(get_embedder("voyage")))
result.by_concept()            # mean_pi, top2box, p1..p5 per concept
result.by_segment("household_income")
```

## Studies and the Snowflake Cortex backend

A study YAML (see `studies/planet_fitness_black_card.yaml`) defines panels, the offers each panel
sees (cells), the question, an optional stated-choice line (e.g. `PLAN: Classic`), an optional
one-sentence intent line that SSR scores, anchors, persona marginals, and revenue per choice. Every
persona answers every cell in independent calls, so cells are compared within persona.

`backends/cortex.py` runs a study entirely inside Snowflake: Claude via `SNOWFLAKE.CORTEX.TRY_COMPLETE`,
embeddings via `EMBED_TEXT_1024`, each step persisted to a stage. No Anthropic or Voyage keys, and no
data leaves the account. Print the SQL for any step and run it in a worksheet or with
`snowflake.connector`:

```bash
STAGE=@SRS_ANALYSTS.<YOUR_SCHEMA>.SYNTHPANEL/plnt_black_card_2799/run_YYYYMMDD
synthpanel cortex-sql --study studies/planet_fitness_black_card.yaml --stage $STAGE --panel prospects --step personas
synthpanel cortex-sql ... --step answers --cell A1_bc2799        # once per cell (--max-personas N to pilot)
synthpanel cortex-sql ... --step score
synthpanel cortex-sql ... --step readout   # also: paired, switching --cell X, readout --segment household_income
```

Results of the first study are in `studies/results/`.

**Score a focused intent sentence.** For compound questions ("would you join, and which plan?"), SSR
on the full answer read plan talk as reluctance: a definite Classic joiner scored 2.7/5. Scoring a
one-sentence `LIKELIHOOD:` line instead restored the paper's setup. Use an `intent` line whenever
the question asks for more than purchase intent.

## Design choices

- **Model**: `claude-opus-5-5` by default (`--model` to change). It rejects `temperature`,
  so answer variety comes from the persona mix and `--draws`, not sampling settings.
- **Refusals**: real-time calls use server-side fallbacks (`fallbacks="default"`), so a
  declined request is retried on a fallback model in the same call. Refused or failed answers
  are kept in `responses.csv` with a reason and excluded from aggregates.
- **Cost**: `--mode batch` uses the Message Batches API at about half the token price
  (results usually within an hour; no server-side fallbacks there). The concept block is
  marked for prompt caching, which pays off for long descriptions and images.
  `--effort low` is a further cost lever to test against quality.
- **Embeddings**: Anthropic has no embeddings endpoint. Voyage (hosted) and
  sentence-transformers (local, nothing leaves the machine) are supported. The paper used
  OpenAI `text-embedding-3-small`; re-check SSR metrics whenever the embedder changes.
- **Anchors**: the six built-in anchor sets are our own wording, not the paper's. Tune them,
  and the SSR temperature and epsilon, on a labelled survey (`validation.human.tune_ssr`,
  which re-scores stored answers without new LLM calls), using held-out concepts.

## SRS data for validation (checked 2026-11-21)

| Need | Source | Status |
|---|---|---|
| Brand-level realized purchases | `SRS_MCP.YIPIT.CHWY_CORE_METRICS`, `Net Sales - by Brand`: 77 brands on Chewy, daily to quarterly, 2021-02 onward | Query in `validation/sources.py` |
| Company KPIs from card/receipt panels | YipitData connector: key metrics and research for hundreds of consumer companies (e.g. ELF sell-through GMV, ULTA net sales) | Company-level for most products, not brand- or SKU-level |
| Reported actuals and consensus | `SRS_VENDORS.FUNDAMENTALS.VISIBLE_ALPHA_KPIS_V` | Available |
| Raw card/receipt panel tables | Not visible to the MCP analyst role | Ask the data team which tables your role can read |
| Customer demographics for persona weighting | Not found in the panels above; Similarweb website demographics is a candidate | Open |

## Validation plan

1. **Chewy brand backtest.** Write each of the 77 brands as a concept (representative product,
   price, description), run a panel of pet owners, and compare top-2-box with brand sales
   share and growth from the Chewy query, within reported category. This is the first test of
   whether synthetic intent tracks real purchasing in SRS data.
2. **Launch backtest.** Pick launches tracked in YipitData (new brands, line extensions), write
   the concept as it was announced, and compare synthetic intent with the first quarters of
   sell-through.
3. **Human calibration (optional).** If a human concept survey is available, run
   `compare-human` to check SSR reproduces paper-level KS similarity and correlation attainment
   before relying on absolute levels.

**Look-ahead bias.** The LLM already knows how established brands performed up to its training
cutoff, so a backtest on well-known brands partly measures memorised market knowledge rather
than consumer simulation. Treat step 1 as a sanity check. The clean test is step 2 restricted to
launches after the model's training cutoff, or concepts written without brand names.

**What intent can and cannot predict.** Purchase intent is stated and relative. Realized sales
also depend on distribution, price, marketing and awareness, so expect rank agreement within a
category to be more reliable than absolute sales forecasts. The backtest reports both,
with bootstrap confidence intervals and leave-one-out error for the calibrated forecast.

## Layout

```
src/synthpanel/
  anchors.py  embeddings.py  ssr.py          SSR core
  concepts.py personas.py    prompts.py      what respondents see and who they are
  respondents.py                             Claude real-time, batch, scripted
  survey.py   metrics.py     cli.py
  study.py    pricing.py     choices.py     study YAML, price-test read-out, labelled-line parsing
  backends/cortex.py                         run a study inside Snowflake Cortex
  validation/ human.py realized.py sources.py
examples/concepts_example.yaml               fictional concepts
studies/                                     study definitions and results
tests/                                       no network or API keys needed
```
