# Planet Fitness Black Card $24.99 → $27.99: synthetic panel read-out

Run `run_20261121` of `studies/planet_fitness_black_card.yaml`, executed in Snowflake Cortex on
2026-11-21. Raw answers, personas and scored rows are kept in
`@SRS_ANALYSTS.CYRUS_SHIRZADI.SYNTHPANEL/plnt_black_card_2799/run_20261121/`.

- Respondent model: `claude-opus-4-6` (the most capable Claude model in Cortex), temperature 1.0.
- SSR embeddings: `voyage-multilingual-2` (Cortex `EMBED_TEXT_1024`); SSR scores a one-sentence
  free-text intent statement (`LIKELIHOOD:` line) against 4 anchor sets.
- 1,600 answers, 0 failed calls, 0 unparsed choices. 623,792 prompt tokens, 235,638 completion tokens.
- Design: every persona answers every cell of its panel in independent calls, so cells are compared
  within persona (paired). 95% intervals are from the paired differences.

## Context from SRS sources

- Current prices: Black Card $24.99, Classic $15 (Q1 2026 call). Classic went $10 → $15 for **new**
  members on June 28, 2024; existing members kept their price (Q2 2024 call). Price increases have
  applied to new joiners only.
- PF tested Black Card at **$27.99** and $29.99 from June 2024; on the Q1 2025 call management said
  the tests showed no significant difference between the two and sunset $27.99. The national $29.99
  rollout was paused on the Q1 2026 call to prioritise member growth (about 150 bps of the same-club
  sales guidance cut). The Q3 2026 call announced "highly targeted regional Black Card price
  increases in the second quarter of 2027", level not disclosed.
- Black Card penetration ~68% of members (Q3 2026); average monthly attrition 3.6% (Q3 2026).

## 1. New joiners (PF's actual practice: existing members grandfathered)

300 personas, each shown all four offers (Classic $15 unless stated).

| Offer | Black Card | Classic | Not joining | Black Card share of joiners | Revenue per prospect ($/mo) | Δ revenue vs $24.99 (95% CI) | Δ join intent (SSR, 1-5) |
|---|---|---|---|---|---|---|---|
| Black Card $24.99 (control) | 55.7% | 38.7% | 5.7% | 59.0% | 19.71 | – | – |
| Black Card **$27.99** | 54.3% | 40.3% | 5.3% | 57.4% | 21.26 | **+$1.55 (+$1.03 to +$2.07), +7.8%** | −0.024 ± 0.045 |
| Black Card $29.99 | 52.3% | 42.7% | 5.0% | 55.1% | 22.10 | +$2.38 (+$1.84 to +$2.93), +12.1% | −0.056 ± 0.042 |
| Backtest: Classic $10 | 51.3% | 43.3% | 5.3% | 54.2% | 17.16 | −$2.55 (−$3.08 to −$2.02) | −0.012 ± 0.041 |

Paired transitions at $27.99: of the 167 personas choosing Black Card at $24.99, 159 kept it, 5
switched to Classic and 3 chose not to join. The same Black Card → not-joining flow (3) appears in
the $10-Classic backtest offer, where Black Card did not change, so it is answer noise rather than a
price effect. The panel keeps 92.6% of the mechanical uplift (55.7% × $3.00 = $1.67 if nobody
reacted).

**Break-even join loss** (the join decline that would cancel the revenue gain per prospect):
7.3% at $27.99, 10.8% at $29.99.

## 2. Existing Black Card members repriced (harsher scenario PF has not used)

200 personas, each shown a normal $24.99 renewal (control) and a notice of $27.99.

| Offer | Keep Black Card | Switch to Classic | Cancel | Revenue per member ($/mo) |
|---|---|---|---|---|
| Renewal at $24.99 (control) | 63.5% | 35.5% | 1.0% | 21.19 |
| Raised to $27.99 | 54.5% | 43.0% | 2.5% | 21.71 |

Paired Δ revenue per member: +$0.51 (−$0.12 to +$1.14), +2.4%, not significant. Of the 127 members who
would keep Black Card at $24.99, 17 (13.4%) switch to Classic and 1 (0.8%) cancels at $27.99. If
those 127 represent members who would otherwise stay, revenue per member goes from $24.99 to
$26.03 (+4.2%). Break-even is about a 21% downgrade rate.

The control is not realistic in level: with no price change, 35.5% of synthetic members say they
would drop to Classic because they don't use the perks. Real members are far more inert
(penetration is rising and total attrition is ~3.5% a month), so only the paired change is used.

## 3. Calibration against what actually happened

| Check | Synthetic panel | Reality (source) | Verdict |
|---|---|---|---|
| Black Card share of joiners at current prices | 59.0% | "Six out of 10 or more online joiners take the Black Card" (Q3 2024 call) | Matches |
| Classic $10 → $15: mix | Black Card share of joiners 54.2% → 59.0% | Black Card penetration 62.4% (Q2 2024) → 63.1% (Q3) → ~64% (Q4) → 65% (Q1 2025); management attributed it to the narrower $10 gap | Direction right |
| Classic $10 → $15: join volume | No measurable change (not joining 5.3% vs 5.7%) | Management expected "a slight Q3 membership decline"; YipitData: Aug-24 total members net negative, Q3 net adds roughly flat; former franchisee VP: joins typically dip 5–8% for a couple of months after a price change, then level off | **Panel misses the join dip** |
| $27.99 vs $29.99 | Black Card share of joiners 57.4% vs 55.1% | PF test: "no significant difference" between the two (Q1 2025 call) | Consistent |

## Read

- For new joiners, $27.99 mostly works as a price increase on the ~59% who pick Black Card. The panel
  shows little trade-down to Classic (−1.6 pts of joiner mix) and no join loss, giving +7.8% revenue
  per prospect.
- The panel understated join sensitivity in the 2024 backtest, so treat +7.8% as an upper bound. A
  5–8% temporary join dip, the size the expert describes, takes $27.99 to roughly break-even (7.3%
  break-even) while it lasts, then accretive as joins recover. $29.99 has more cushion (10.8%) but
  more trade-down.
- Repricing existing members is riskier: trade-down to the $15 Classic is the main channel (13.4% of
  would-be keepers), cancellations are small, and the gain is thin (+2.4% to +4.2%) against a ~21%
  break-even downgrade rate. This lines up with management choosing targeted regional increases.

## Caveats

- Persona marginals (age, income, gym history, usage, perk use) are assumptions informed by sources,
  not measured PF member data, and Black Card take-up levels depend on them. Paired changes depend
  on them less.
- LLM respondents are more rational and less inert than real consumers, and are agreeable (few say
  "not joining"). Volume effects are understated; mix effects are more reliable.
- `claude-opus-4-6` was trained on public data that may include PF's 2024 price change and later
  Black Card news. Leakage would flatter the backtest; here the backtest still missed the join dip.
- Single run; answer noise floor is roughly 2% of personas switching between cells for no reason.
