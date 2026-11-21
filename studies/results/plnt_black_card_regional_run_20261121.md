# Planet Fitness regional Black Card pricing ($26.99–$29.99): synthetic panel read-out

Run `run_20261121` of `studies/planet_fitness_black_card_regional.yaml`, executed in Snowflake Cortex on
2026-11-21 (`claude-opus-4-6`, temperature 1.0). Raw answers and personas are kept in
`@SRS_ANALYSTS.CYRUS_SHIRZADI.SYNTHPANEL/plnt_black_card_regional/run_20261121/`.

- 1,080 prospect personas × 5 prices = 5,400 answers; 0 failed, 0 unparsed plan choices.
  2,238,450 prompt tokens, 769,072 completion tokens.
- Balanced design: market type × budget gyms within 10 minutes × household income = 27 combinations
  × 40 personas. Gender 51% male (FY2025 10-K). Age, gym history and region are assumptions; region
  uses US population shares, not Planet Fitness's club footprint (not available in text form).
- Paired: every persona saw every price in independent calls. 95% intervals are from the paired
  differences. "Weighted" uses the assumed mix in the study file (suburb 55%, city 20%, small town 25%;
  0/1/2+ budget gyms 30/40/30%; income <$50k/$50–100k/$100k+ 40/40/20%).
- Not in the company's materials: the $26.99–$29.99 range. The Q3 2026 call says increases will be
  "highly targeted regional" from Q2 2027, read "at a DMA level", levels to be disclosed later.
- SSR intent scoring for this run did not complete (query cancelled by the connector timeout); plan
  choice and revenue do not depend on it.

## System level

| Black Card price | Black Card | Not joining | Revenue per prospect | Δ vs $24.99 (95% CI) | Δ % (weighted) | Break-even join loss |
|---|---|---|---|---|---|---|
| $24.99 (control) | 55.9% | 6.5% | $19.61 | – | – | – |
| $26.99 | 54.5% | 6.0% | $20.64 | +$1.02 ± 0.19 | +5.2% (+5.4%) | 5.0% |
| $27.99 | 54.0% | 6.3% | $21.07 | +$1.45 ± 0.17 | +7.4% (+7.6%) | 6.9% |
| $28.99 | 52.4% | 6.1% | $21.42 | +$1.80 ± 0.23 | +9.2% (+9.4%) | 8.5% |
| $29.99 | 53.3% | 6.2% | $22.06 | +$2.45 ± 0.26 | +12.5% (+12.8%) | 11.1% |

Black Card share moves 1–3.5 pts across the range; the $28.99 vs $29.99 reversal is within answer noise
(about 2% of personas switch between cells at random). Joins do not move.

## By local market factor (n = 360 per level; Δ revenue vs $24.99, 95% CI)

| Factor | Level | Black Card at $24.99 | $26.99 | $27.99 | $28.99 | $29.99 | Black Card at $29.99 |
|---|---|---|---|---|---|---|---|
| Budget gyms within 10 min | none | 58.1% | +5.0% | +8.0% | +9.2% | **+12.9%** (±$0.39) | 55.6% |
| | one | 58.3% | +6.5% | +7.8% | +10.7% | **+14.8%** (±$0.42) | 57.5% |
| | two or more | 51.4% | +4.1% | +6.4% | +7.6% | **+9.6%** (±$0.50) | 46.9% |
| Market type | big city | 56.4% | +4.7% | +7.1% | +7.9% | +10.8% (±$0.42) | 51.9% |
| | suburb | 57.2% | +5.2% | +7.4% | +9.4% | +13.2% (±$0.47) | 55.3% |
| | small town / rural | 54.2% | +5.7% | +7.7% | +10.3% | +13.6% (±$0.43) | 52.8% |
| Household income | under $50k | 55.6% | +5.5% | +7.6% | +9.7% | +13.1% (±$0.39) | 53.6% |
| | $50k–$99k | 56.1% | +5.2% | +7.5% | +8.0% | +11.2% (±$0.39) | 51.7% |
| | $100k+ | 56.1% | +5.0% | +7.1% | +9.8% | +13.2% (±$0.53) | 54.7% |

## Read

- Competition is the factor that matters. In markets with two or more budget gyms nearby, fewer
  prospects pick Black Card even at $24.99 (51.4% vs ~58%), more walk away (8.1% vs 3.6% with none),
  and trade-down at $28.99–$29.99 is about 4.5 pts. These markets keep about 70% of the mechanical
  price uplift, against about 90% where there is no nearby budget gym. That matches management saying
  competitive markets responded more strongly to the $10 promo.
- Big-city prospects are a little more price-sensitive than suburban and small-town ones; the gap is at
  the edge of the intervals.
- The panel shows almost no income gradient, which is not credible for a $3–$5 price change. Treat it
  as a limitation of the synthetic respondents, not evidence that income doesn't matter.
- Calibration from the 2024 backtest: the panel missed a ~10% dip in joins and understated trade-down by
  about half. Compare each price's break-even join loss (5–11%) with a dip of that size: $26.99–$27.99
  are roughly break-even while a dip lasts; $29.99 has the most cushion overall, but in competitive
  markets its corrected uplift is closer to +6% than +10%.

## Precision

| | Run 1 (n = 300) | This run (n = 1,080) |
|---|---|---|
| System Δ revenue at $27.99 | ±$0.52 | ±$0.17 |
| Per region / factor level | ±$0.60 to ±$1.08 (n = 52–108) | ±$0.26 to ±$0.53 (n = 360) |
| Black Card share step between adjacent $1 prices | not resolvable | still not resolvable (≈1 pt vs ≈2% noise) |

More personas would not fix the main limits: respondents are agreeable (few walk away), barely react to
income, and the market attributes are hypothetical rather than tied to real DMAs.
