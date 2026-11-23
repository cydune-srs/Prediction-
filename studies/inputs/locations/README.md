# Competitor club lists (scraped 2026-11-21/22)

Inputs to `scripts/build_geo_personas.py` for `studies/planet_fitness_black_card_geo2.yaml`. All are public web pages.

| File | Source | Notes |
|---|---|---|
| `crunch_hvlp_open.csv` | crunch.com club pages (sitemap), `scripts/scrape_crunch.py` | 544 open low-price clubs with their Base / Peak prices; 60 presale clubs and 2 Costa Rica clubs excluded |
| `crunch_premium.csv` | same | 27 company-run full-service clubs ("One Crunch" / "All Crunch", $72–$127/mo) |
| `state_peak.csv` | derived | Mean Crunch Peak price by state (blank where a state has fewer than 3 clubs) |
| `fitness_connection_web.csv` | fitnessconnection.com gym pages | 47 clubs; no prices published; its "coming soon" flag matches template text on every page and is ignored |
| `eos_locations.csv` | eosfitness.com club pages | 251 listed clubs; open status not verified |
| `vasa_locations.csv` | vasafitness.com location sitemap | 88 listed clubs; open status not verified |

| `plnt_us_alltheplaces.csv` | All The Places open-data runs of its `planet_fitness_us` spider (data.alltheplaces.xyz) | 2,670 US clubs: the last complete scrape (2025-09-27, 2,560 clubs) merged with partial scrapes of 2026-10-10 (1,771) and 2026-11-07 (46); `first_seen` / `last_seen` give the run dates. About 97% of the US clubs open in Nov 2026 by a licensed weekly count (not stored here); short by ~26 in TX, ~13 in NY, ~11 each in PA and IL, ~9 in NV; ~17 extra in NJ that have probably closed. planetfitness.com and the state franchise registries (WI, MN) block automated access. All The Places publishes its data as CC0 (unverified for each run). |

The 2023 FDD Planet Fitness list (SharePoint) used by the first geo runs is not stored here.
