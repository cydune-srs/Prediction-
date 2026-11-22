# Planet Fitness Black Card $26.99–$29.99: re-run with current competitors and local prices

Run `run_20261122` of `studies/planet_fitness_black_card_geo2.yaml`, run in Snowflake Cortex on 2026-11-22 (`claude-opus-4-6`, temperature 1.0).
- **Stage:** personas and raw answers are in `@SRS_ANALYSTS.CYRUS_SHIRZADI.SYNTHPANEL_V2/plnt_black_card_geo2/run_20261122/`. This is a new stage: the original `SYNTHPANEL` stage stopped being visible after the SRS MCP Snowflake role changed mid-session, so the new one is owned by the shared MCP role.
- **Personas:** loaded in four chunks, each checked against the local CSV. Full-panel MD5: `2d102676…4211`.
- **Answers:** 1,080 personas × 5 prices = 5,400 answers, with 0 failed calls and 0 unparsed plan choices.
- **Tokens:** 2,523,705 prompt tokens and 834,121 completion tokens.

## What changed from the previous run

| | Previous run (`plnt_black_card_geo`) | This run |
|---|---|---|
| Planet Fitness clubs | 2023 FDD list (year-end 2022) | Same: planetfitness.com blocks automated access |
| Competitors within 5 miles | Crunch from 2023 FDD (340); EoS, VASA from websites | Crunch from crunch.com (544 open low-price clubs; presale and the 27 premium clubs excluded); EoS, VASA; Fitness Connection (47) |
| Clubs with a competitor nearby | 28.3% | 39.7% (weights restore this) |
| Price shown to the persona | none | The nearest Crunch club's own prices, chain-wide EoS and VASA prices, any premium Crunch club within 5 miles, and the state's average Crunch Peak price |
| Sample seed | 41 | 42 (a fresh sample of clubs) |

Example of the new persona lines for a prospect in Atlanta:

```
- Other budget gym chains within a 10-minute drive: Crunch Fitness (2), EoS Fitness (1)
- What those nearby gyms charge: Crunch Fitness: $9.99/mo for one club with a 1-year contract or $15.99/mo month-to-month, $24.99/mo for all clubs (Peak); EoS Fitness: $9.99/mo basic, $24.99 to $29.99/mo for upper tiers
- Typical all-club price at budget gyms in your state: about $25/mo
```

## Chain level (weighted to the current club mix)

| Black Card price | Black Card | Not joining | Revenue per prospect | Δ vs $24.99 (95% CI) | Δ % | Break-even join loss | Previous run Δ % |
|---|---|---|---|---|---|---|---|
| $24.99 (control) | 52.0% | 5.2% | $19.41 | – | – | – | – |
| $26.99 | 50.3% | 5.0% | $20.28 | +$0.87 ± 0.23 | +4.5% | 4.3% | +4.3% |
| $27.99 | 49.7% | 5.9% | $20.58 | +$1.17 ± 0.29 | +6.0% | 5.7% | +7.4% |
| $28.99 | 49.7% | 5.8% | $21.09 | +$1.68 ± 0.30 | +8.6% | 7.9% | +9.9% |
| $29.99 | 49.5% | 6.3% | $21.47 | +$2.06 ± 0.32 | +10.6% | 9.6% | +12.7% |

Showing real local prices lowers the case for the top of the range.
- **Fewer Black Card choices at today's price.** Black Card takes 52% at $24.99, against 57% before. Next to Crunch's $9.99–$15.99 single-club plans, more prospects pick Classic.
- **Smaller uplift at higher prices.** The uplift at $27.99–$29.99 is about 1.5–2 points lower than in the previous run.
- **More prospects walk away at $29.99:** 6.3%, against 5.2% at $24.99.

## Where it differs (Δ revenue vs $24.99)

| Segment | n | Black Card at $24.99 | Not joining at $24.99 | $27.99 | $29.99 (95% CI) |
|---|---|---|---|---|---|
| **Competitor within 5 mi** | 540 | 52.2% | 8.3% | +5.3% | **+8.5%** (±$0.51) |
| **No competitor** | 540 | 51.9% | 3.1% | +6.4% | **+11.9%** (±$0.39) |
| 4+ competitor clubs | 45 | 51.1% | 24.4% | −7.8% | +3.4% (±$2.51) |
| **Big city** | 269 | 55.2% | 8.3% | +5.2% | **+11.5%** (±$0.75) |
| **Suburb** | 550 | 50.4% | 4.8% | +5.2% | **+8.5%** (±$0.44) |
| **Small town / rural** | 261 | 52.2% | 3.4% | +8.0% | **+13.5%** (±$0.54) |
| Household income $100k+ | 394 | 65.4% | 6.0% | +5.5% | +12.4% (±$0.61) |
| $60k–$100k | 255 | 43.6% | 5.0% | +6.7% | +10.4% (±$0.62) |
| Under $60k | 431 | 45.0% | 4.6% | +6.0% | +8.9% (±$0.44) |
| Big city, $60k+ | 164 | 58.4% | 8.8% | +3.7% | +12.4% (±$1.05) |
| Big city, under $60k | 105 | 50.4% | 7.6% | +7.6% | +10.0% (±$1.00) |
| Suburb or town, $60k+ | 485 | 56.2% | 4.7% | +6.6% | +11.4% (±$0.48) |
| Suburb or town, under $60k | 326 | 43.6% | 3.8% | +5.6% | +8.6% (±$0.49) |
| Premium Crunch club within 5 mi | 27 | 71.5% | 0.0% | +7.3% | +11.3% (±$1.84) |
| Region: West | 220 | 52.4% | 8.5% | +2.7% | +8.0% (±$0.85) |
| Region: Midwest | 214 | 48.1% | 3.6% | +6.9% | +10.8% (±$0.61) |
| Region: South | 406 | 52.9% | 5.3% | +6.8% | +11.2% (±$0.50) |
| Region: Northeast | 240 | 53.7% | 3.5% | +6.6% | +11.5% (±$0.68) |
| State Crunch Peak under $26 | 444 | 50.0% | 6.7% | +6.6% | +10.1% (±$0.54) |
| $26–$28 | 293 | 54.3% | 4.3% | +6.2% | +11.8% (±$0.57) |
| $28+ | 343 | 52.6% | 4.0% | +5.0% | +10.1% (±$0.54) |

## Read

- **Competition now matters, once prices are shown.**
  - Prospects with a low-price club nearby keep +8.5% at $29.99, against +11.9% with none.
  - Walk-away is 8–12% with a competitor nearby, against 3% without. When the persona can see that Crunch sells one club for $9.99–$15.99 or all clubs for about $25, a $30 Black Card looks expensive.
  - In the previous run, which named competitors but not their prices, one competitor nearby made no difference.
- **Big cities are no longer the most price-sensitive.**
  - With prices and current competitors in the prompt, big-city prospects keep +11.5% at $29.99, against +8.5% in suburbs and +13.5% in small towns. Big-city prospects also pick Black Card more often at $24.99 (55% vs 50% in suburbs).
  - Near a premium Crunch club ($72–$127 a month), 72% pick Black Card and almost none walk away. Only 27 personas are in this group, but it fits your point that urban members compare against more expensive options.
  - The urban risk that remains is walk-away: 8–11% of big-city prospects don't join, because big cities have the most low-price competitors.
- **Income is the clearest gradient.** Black Card share at $24.99 is 65% for $100k+ households against 44–45% below $100k. The uplift at $29.99 is +12.4% against +8.9%.
- **The state price level barely registered.** Showing "typical all-club price in your state" ($24–$32) did not change the uplift (+10% to +12% across all three bands). The respondents reacted to specific nearby prices, not to a regional average.
- **For regional pricing**, the read now favors:
  - **$29.99** in small-town clubs, higher-income trade areas, and urban clubs near premium gyms.
  - **$27.99–$28.99** in suburbs with Crunch or EoS nearby, lower-income areas and the West.
  - **Holding near $24.99–$26.99** in the few markets with 4 or more low-price clubs nearby. There, a quarter of prospects already walk away at today's price (n = 45, so this is directional).
- **Calibration still applies.** The 2024 backtest missed a ~10% dip in joins. Break-even join losses here are 4–10%, so $26.99–$27.99 is roughly break-even if joins dip that much, and $29.99 keeps a thin cushion.

## Limits

- Planet Fitness locations are still the 2023 FDD list (year-end 2022). The current list needs the Placer connector (not yet authorized) or a newer FDD from a state franchise registry.
- Missing competitors:
  - Chuze could not be scraped (bot check).
  - Fitness Connection publishes no prices.
  - Independents and LA Fitness / 24 Hour Fitness are not included.
- EoS and VASA prices are chain-wide headline prices. Some EoS clubs (California, "Lux", "Landmark") charge more.
- Prices from 19 upscale Crunch clubs ($35–$75 Base) are as published and were kept.
- Income and age describe trade-area residents, not gym prospects; the age tilt is an assumption.
