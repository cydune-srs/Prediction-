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

Planet Fitness club locations come from the 2023 FDD (SharePoint) and are not stored here.
