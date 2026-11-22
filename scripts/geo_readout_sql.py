"""Print readout SQL for a persona-file (real-geography) run: weighted plan shares and paired revenue
deltas vs the control, by competition, brand, area type, region and income.

Usage: python scripts/geo_readout_sql.py STUDY.yaml STAGE [segments|qa]
"""
import sys
from synthpanel.study import load_study
from synthpanel.backends import cortex

study = load_study(sys.argv[1])
panel = study.panels["prospects"]
stage = sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "segments"
p = cortex._parse_sql(panel, "answer")
segs = {
    "all": "'all'",
    "competition": "IFF(n_comp > 0, 'competitor within 5 mi', 'none within 5 mi')",
    "n_competitors": "CASE WHEN n_comp = 0 THEN '0' WHEN n_comp = 1 THEN '1' WHEN n_comp <= 3 THEN '2-3' ELSE '4+' END",
    "brand": "CASE WHEN n_comp = 0 THEN 'none' WHEN CONTAINS(gyms, ',') THEN 'multiple brands' "
             "WHEN STARTSWITH(gyms, 'Crunch') THEN 'Crunch only' WHEN STARTSWITH(gyms, 'EoS') THEN 'EoS only' ELSE 'VASA only' END",
    "market_type": "market_type",
    "region": "region",
    "income": "CASE WHEN income IN ('under $35,000', '$35,000-$59,999') THEN 'under $60k' "
              "WHEN income = '$60,000-$99,999' THEN '$60-100k' ELSE '$100k+' END",
}
if "state_gym_price" in panel.spec.labels:   # price-context panels (v2 personas)
    segs.update({
        "state_price": "CASE WHEN state_price < 26 THEN 'under $26' WHEN state_price < 28 THEN '$26-28' ELSE '$28+' END",
        "crunch_peak_nearby": "CASE WHEN crunch_peak IS NULL THEN 'no Crunch nearby' WHEN crunch_peak <= 25.99 THEN 'Peak up to $25.99' "
                              "WHEN crunch_peak < 30 THEN 'Peak $26-29.99' ELSE 'Peak $30+' END",
        "premium_nearby": "IFF(premium = 1, 'premium Crunch within 5 mi', 'no premium club')",
        "city_x_income": "IFF(market_type = 'a big city', 'big city', 'suburb/town') || ' / ' || "
                         "IFF(income IN ('under $35,000', '$35,000-$59,999'), 'under $60k', '$60k+')",
    })
base = f"""WITH a AS (SELECT $1:cell::string AS cell, $1:persona_id::string AS persona_id, $1:persona AS persona,
              $1:answer::string AS answer, $1:usage AS usage
       FROM {stage}/answers/prospects/),
  c0 AS (SELECT a.*, {p['choice_raw']} AS choice_raw FROM a),
  c AS (SELECT c0.*, {p['choice']} AS choice,
               TRY_TO_DOUBLE(persona:_weight::string) AS w, TRY_TO_NUMBER(persona:_n_competitors::string) AS n_comp,
               persona:budget_gyms_nearby::string AS gyms, persona:market_type::string AS market_type,
               persona:_region::string AS region, persona:household_income::string AS income,
               TRY_TO_DOUBLE(persona:_state_price::string) AS state_price, TRY_TO_NUMBER(persona:_premium_nearby::string) AS premium,
               TRY_TO_DOUBLE(REGEXP_SUBSTR(persona:nearby_gym_prices::string, 'Crunch Fitness: [^;]*?[$]([0-9.]+)/mo for all clubs', 1, 1, 'e', 1)) AS crunch_peak
        FROM c0),
  r AS (SELECT c.*, {cortex._revenue_case(panel)} AS revenue FROM c)"""
if mode == "qa":
    print(base + """
SELECT cell, COUNT(*) AS n, COUNT_IF(answer IS NULL) AS failed, COUNT_IF(choice = 'unparsed') AS unparsed,
       SUM(usage:prompt_tokens::int) AS prompt_tokens, SUM(usage:completion_tokens::int) AS completion_tokens
FROM r GROUP BY cell ORDER BY cell""")
    sys.exit()
union = "\n  UNION ALL ".join(f"SELECT '{k}' AS seg_type, {v} AS seg, r.* FROM r" for k, v in segs.items())
print(base + f""",
  s AS ({union}),
  ctl AS (SELECT persona_id, revenue AS rev0, choice AS ch0 FROM r WHERE cell = '{panel.control}'),
  d AS (SELECT s.*, ctl.rev0, s.revenue - ctl.rev0 AS d_rev, ctl.ch0 FROM s JOIN ctl USING (persona_id))
SELECT seg_type, seg, cell, COUNT(*) AS n,
       ROUND(SUM(w * IFF(choice = 'Black Card', 1, 0)) / SUM(w), 3) AS bc,
       ROUND(SUM(w * IFF(choice = 'Classic', 1, 0)) / SUM(w), 3) AS classic,
       ROUND(SUM(w * IFF(choice = 'Not joining', 1, 0)) / SUM(w), 3) AS nj,
       ROUND(SUM(w * revenue) / SUM(w), 2) AS rev,
       ROUND(SUM(w * d_rev) / SUM(w), 2) AS d_rev,
       ROUND(1.96 * STDDEV_SAMP(d_rev) / SQRT(COUNT(*)), 2) AS ci,
       ROUND(100 * SUM(w * d_rev) / NULLIF(SUM(w * rev0), 0), 1) AS d_pct,
       ROUND(SUM(w * IFF(choice = ch0, 0, 1)) / SUM(w), 3) AS switched
FROM d GROUP BY seg_type, seg, cell ORDER BY seg_type, seg, cell""")
