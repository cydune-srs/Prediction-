# Planet Fitness Black Card $26.99–$29.99 with real club geography: synthetic panel read-out

Run `run_20261122` of `studies/planet_fitness_black_card_geo.yaml`, run in Snowflake Cortex on
2026-11-22 (`claude-opus-4-6`, temperature 1.0). Personas and raw answers are stored in
`@SRS_ANALYSTS.CYRUS_SHIRZADI.SYNTHPANEL/plnt_black_card_geo/run_20261122/`. The personas were
loaded in four chunks, each checked against the local CSV. Full-panel MD5: `788f52f4…2504`.

- **Size:** 1,080 prospect personas × 5 prices = 5,400 answers.
  - 0 failed calls and 0 unparsed plan choices.
  - 2,229,820 prompt tokens and 791,377 completion tokens.
- **Paired design:** every persona answered every price in a separate call. The 95% intervals come from the paired differences.

## How the geography was built

| Input | Source | Coverage |
|---|---|---|
| Planet Fitness clubs | 2023 FDD, Item 20 exhibits (franchised + company-owned) | 2,314 clubs at year-end 2022; 2,311 matched to a ZIP centroid |
| Crunch clubs | 2023 Crunch FDD, Item 20 exhibits | 340 clubs at year-end 2022 |
| EoS clubs | eosfitness.com club pages (no FDD: EoS does not franchise) | 251 listed clubs |
| VASA clubs | vasafitness.com location sitemap (no FDD) | 88 listed clubs |
| Trade-area demographics | Census 2024 ZCTA Gazetteer; ACS 2024 5-year (B01003, B19001, B01001) | All ZCTAs within 5 miles of each club |

- **Club trade areas:** each persona is tied to one real Planet Fitness club. The club's trade area is every ZCTA within 5 miles.
  - **Area type** comes from trade-area population: 250k or more is a big city; under 50k is a small town or rural area; anything else is a suburb.
  - **Household income** is drawn from the trade area's ACS distribution.
  - **Age** is drawn from the trade area's ACS distribution, tilted toward younger adults (an assumption).
  - **Competitors** are the named competitor clubs within 5 miles. The prompt shows them, e.g. "Crunch Fitness (2), EoS Fitness (1)".
- **Sampling and weights:** clubs with and without a competitor nearby were sampled 540/540. `_weight` then restores the chain's real mix: 28.3% of clubs have a competitor nearby, 71.7% do not.
- **Chain footprint:**

  | Clubs with nearby competitors | Share |
  |---|---|
  | None | 71.7% |
  | 1 | 16.6% |
  | 2–3 | 8.0% |
  | 4+ | 3.7% |

  - The 85 clubs with 4 or more nearby are mostly in NY (27), AZ (22), CA (11) and NV (9).
  - Competitor presence by area type: 58.6% of big-city clubs, 29.5% of suburban clubs and 1.7% of small-town clubs.

## System level (weighted to the real club mix)

| Black Card price | Black Card | Classic | Not joining | Revenue per prospect | Δ vs $24.99 (95% CI) | Δ % | Break-even join loss |
|---|---|---|---|---|---|---|---|
| $24.99 (control) | 57.1% | 38.0% | 5.0% | $19.96 | – | – | – |
| $26.99 | 55.3% | 39.3% | 5.4% | $20.82 | +$0.86 ± 0.23 | +4.3% | 4.1% |
| $27.99 | 55.4% | 39.5% | 5.1% | $21.42 | +$1.47 ± 0.25 | +7.4% | 6.9% |
| $28.99 | 55.2% | 39.6% | 5.3% | $21.93 | +$1.97 ± 0.27 | +9.9% | 9.0% |
| $29.99 | 54.7% | 40.6% | 4.7% | $22.48 | +$2.53 ± 0.28 | +12.7% | 11.3% |

These are almost the same as the hypothetical-market run (`plnt_black_card_regional_run_20261121.md`): +5.2%, +7.4%, +9.2% and +12.5%. Real geography does not change the chain-level answer. It changes where the risk sits.

## Where it differs (Δ revenue vs $24.99)

| Segment | Share of clubs | n | Black Card at $24.99 | Not joining at $24.99 | $27.99 | $29.99 (95% CI) |
|---|---|---|---|---|---|---|
| **Competitors within 5 mi** | | | | | | |
| none | 71.7% | 540 | 57.2% | 4.1% | +7.6% | +12.9% (±$0.33) |
| 1 | 16.6% | 313 | 57.2% | 7.0% | +7.9% | +13.1% (±$0.60) |
| 2–3 | 8.0% | 157 | 60.5% | 6.4% | +6.0% | +9.8% (±$0.92) |
| 4+ | 3.7% | 70 | 45.7% | 10.0% | +3.2% | +13.8% (±$0.68) |
| **Brand nearby** | | | | | | |
| Crunch only | 15.4% | 283 | 58.3% | 7.4% | +6.2% | +12.9% (±$0.57) |
| EoS only | 5.3% | 107 | 56.1% | 5.6% | +7.9% | +10.6% (±$1.09) |
| VASA only | 2.9% | 53 | 60.4% | 3.8% | +8.9% | +14.8% (±$1.38) |
| more than one brand | 4.8% | 97 | 50.5% | 10.3% | +5.9% | +10.3% (±$1.24) |
| **Area type** | | | | | | |
| big city | 21.9% | 313 | 53.0% | 7.1% | +6.7% | +10.4% (±$0.49) |
| suburb | 50.9% | 545 | 58.8% | 3.6% | +7.2% | +12.4% (±$0.41) |
| small town / rural | 27.3% | 222 | 57.2% | 5.7% | +8.1% | +14.9% (±$0.57) |
| **Trade-area household income** | | | | | | |
| under $60k | – | 411 | 52.6% | 2.2% | +5.3% | +10.5% (±$0.42) |
| $60k–$100k | – | 233 | 54.9% | 6.5% | +8.9% | +15.2% (±$0.52) |
| $100k+ | – | 436 | 62.7% | 6.8% | +8.5% | +13.5% (±$0.49) |
| **Region** | | | | | | |
| West | 18.2% | 235 | 52.9% | 6.2% | +6.7% | +10.9% (±$0.65) |
| Midwest | 21.9% | 220 | 60.7% | 4.9% | +5.8% | +12.1% (±$0.66) |
| South | 38.3% | 388 | 57.1% | 4.4% | +8.2% | +13.3% (±$0.48) |
| Northeast | 21.7% | 237 | 56.5% | 5.0% | +8.2% | +13.7% (±$0.45) |

To separate city size from competition, here is $29.99 within each area type:

| Area type | Competitor nearby | No competitor |
|---|---|---|
| Suburb | +13.0% | +12.1% |
| Big city | +11.0% | +9.6% |

By income at $29.99:

| Household income | Competitor nearby | No competitor |
|---|---|---|
| Under $60k | +9.2% | +10.9% |
| $60k+ | +13.9% | +14.1% |

## Read

- **One competitor nearby does not move the panel.**
  - Clubs with a single Crunch, EoS or VASA nearby keep the same uplift as clubs with none (+13.1% vs +12.9% at $29.99). Prospects there are more likely to walk away (7% vs 4%), but at every price, not more as the price rises.
  - The competition effect from the hypothetical run ("two or more budget gyms within 10 minutes") shows up only in the densest markets. Those are the ~85 clubs (3.7%) with 4 or more competitor clubs nearby, plus the ~5% with more than one brand nearby. There, Black Card takes 46–51% at $24.99 and 10% walk away. Those cells are small (n = 70–97), so the price-by-price pattern is noisy.
  - The hypothetical run put a third of prospects in that situation. The real figure is about 5–8% of clubs.
- **City size and income matter more than competitor count.**
  - Big-city trade areas keep the least uplift (+10.4% at $29.99), and this holds with or without a competitor nearby.
  - Lower-income trade areas trade down to Classic more (+10.5% vs +13.5–15.2%).
  - Small-town and suburban clubs, 78% of the chain, keep +12–15%.
  - The income gradient was absent in the hypothetical run. Here income is drawn from real trade-area distributions and named places, which seems to make the respondents react to it. Treat it as directional.
- **For regional pricing,** the panel points to the higher end ($28.99–$29.99) in suburban and small-town, middle- and higher-income trade areas. It points to the lower end ($26.99–$27.99) in big-city, lower-income and multi-competitor trade areas, mostly NYC, Phoenix, Los Angeles and Las Vegas.
- **Calibration still applies.** In the 2024 Classic backtest, the panel missed a ~10% dip in joins and understated trade-down by about half. Every break-even join loss here (4–11%) is in the range of that miss. A $26.99 price is roughly break-even if joins dip that much; $29.99 keeps a cushion in most markets but not in the densest competitive ones.

## Limits of the geography

- The 2023 FDDs describe clubs at year-end 2022:
  - Planet Fitness: 2,314 clubs then vs about 2,900 now.
  - Crunch: 340 then vs roughly 550–600 now, per a Crunch franchisee call.
  - Competitor counts are therefore understated, most of all for Crunch, which has grown fastest.
- EoS and VASA do not file FDDs. Their lists come from their websites, and open status was not verified.
- Other HVLP chains (Chuze, Fitness Connection, Crunch's newer markets, regional independents) are not included.
- Income and age describe residents of the trade area, not gym prospects. The age tilt toward younger adults is an assumption.
- Region shares follow the club footprint. The respondents are still synthetic and agreeable: few walk away at any price.
