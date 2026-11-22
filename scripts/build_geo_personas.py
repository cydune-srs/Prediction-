"""Build real-geography personas for a store chain from location lists and Census data.

Usage:
  python scripts/build_geo_personas.py --stores plnt.csv --competitor Crunch=crunch.csv \
      --competitor EoS=eos.csv --competitor VASA=vasa.csv --census-dir raw/ \
      --n 1080 --out studies/personas/plnt_geo_personas.csv --markets-out markets.csv \
      [--price-file Crunch=crunch_prices.csv --price-file "CrunchPremium=premium.csv" \
       --price-text "EoS=from $9.99/mo ..." --state-price state_peak.csv --national-price 25.99]

Each persona is anchored to one real store. Its trade area (ZCTAs within --radius miles) gives:
area type (from resident population), the persona's age band and household income band (drawn
from that trade area's ACS distributions; age tilted toward younger adults, see AGE_TILT), and the
count of competitor clubs within the radius. Stores with and without a competitor nearby are
sampled in equal numbers; `_weight` restores the chain's true mix.

Competitor files may carry their own lat/lon (used as given) or only a ZIP (placed at the ZCTA centroid).
Optional price context: --price-file Name=path (lat, lon, price_text) quotes the nearest such club within
the radius; --price-text Name=text quotes a chain-wide price for a brand present nearby; --state-price
(state, price) sets "typical all-club price at budget gyms in your state", --national-price where missing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from synthpanel.geo import _haversine, area_type, draw_band, load_zcta_table, locate, trade_areas

# Gym joiners skew young (PLNT: Gen Z is the largest share of joins; FISA panel via BWG: highest gym
# penetration at 18-24). ASSUMPTION: relative join propensity by age, applied to trade-area adults.
AGE_TILT = {"18-24": 2.0, "25-34": 1.5, "35-44": 1.2, "45-54": 1.0, "55-64": 0.7, "65+": 0.4}
GENDER = {"man": 0.51, "woman": 0.49}  # FY2025 10-K: ~51% male
GYM_HISTORY = {"former Planet Fitness member": 0.35, "has never belonged to a gym": 0.30,
               "belonged to another gym in the past": 0.20, "currently belongs to another gym": 0.15}
WORKOUT = {"alone": 0.65, "with a friend or partner": 0.35}
AWAY = {"rarely": 0.55, "sometimes": 0.30, "often": 0.15}
REGIONS = {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX PR",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}
STATE_REGION = {s: r for r, states in REGIONS.items() for s in states.split()}
BRAND_LABEL = {"Crunch": "Crunch Fitness", "EoS": "EoS Fitness", "VASA": "VASA Fitness",
               "FitnessConnection": "Fitness Connection", "CrunchPremium": "Crunch Fitness full-service club"}


def competitor_text(row: pd.Series, names: list[str]) -> str:
    parts = [f"{BRAND_LABEL.get(n, n)} ({row[f'n_{n}']})" for n in names if row[f"n_{n}"] > 0]
    return ", ".join(parts) if parts else "none"


def place(df: pd.DataFrame, zcta: pd.DataFrame) -> pd.DataFrame:
    """Use the file's own lat/lon where given, else the ZIP's ZCTA centroid."""
    if {"lat", "lon"} <= set(df.columns):
        df = df.copy()
        df["lat"], df["lon"] = pd.to_numeric(df["lat"], errors="coerce"), pd.to_numeric(df["lon"], errors="coerce")
        if df["lat"].notna().all():
            return df
        df = df.drop(columns=["lat", "lon"])
    return locate(df, zcta)


def nearest_text(markets: pd.DataFrame, clubs: pd.DataFrame, radius: float) -> list:
    """price_text of the nearest club within the radius, else None."""
    c_lat, c_lon, txt = clubs["lat"].to_numpy(), clubs["lon"].to_numpy(), clubs["price_text"].to_numpy()
    out = []
    for lat, lon in zip(markets["lat"], markets["lon"]):
        d = _haversine(lat, lon, c_lat, c_lon)
        i = int(np.argmin(d)) if len(d) else -1
        out.append(txt[i] if i >= 0 and d[i] <= radius else None)
    return out


def pick(rng, dist: dict[str, float]) -> str:
    return str(rng.choice(list(dist), p=np.array(list(dist.values())) / sum(dist.values())))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", required=True)
    ap.add_argument("--competitor", action="append", default=[], help="Name=path.csv")
    ap.add_argument("--census-dir", required=True, help="Census raw folder, or a pickled table from geo.load_zcta_table")
    ap.add_argument("--radius", type=float, default=5.0)
    ap.add_argument("--n", type=int, default=1080)
    ap.add_argument("--seed", type=int, default=41)
    ap.add_argument("--panel", default="prospects")
    ap.add_argument("--out", required=True)
    ap.add_argument("--markets-out", required=True)
    ap.add_argument("--price-file", action="append", default=[], help="Name=path.csv with lat, lon, price_text")
    ap.add_argument("--price-text", action="append", default=[], help="Name=chain-wide price text")
    ap.add_argument("--state-price", help="CSV with state, price (typical all-club budget gym price)")
    ap.add_argument("--national-price", type=float, help="Fallback where the state has no price")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    zcta = pd.read_pickle(a.census_dir) if a.census_dir.endswith(".pkl") else load_zcta_table(a.census_dir)
    stores = locate(pd.read_csv(a.stores, dtype=str), zcta)
    comps = {}
    for spec in a.competitor:
        name, path = spec.split("=", 1)
        df = pd.read_csv(path, dtype=str)
        if "status" in df:
            df = df[~df["status"].fillna("").str.lower().isin(["closed"])]
        comps[name] = place(df, zcta)
    unmatched = stores["lat"].isna().sum()
    markets = trade_areas(stores, zcta, a.radius, comps)
    markets["area_type"] = markets["population"].map(area_type)
    names = list(comps)
    markets["n_competitors"] = markets[[f"n_{n}" for n in names]].sum(axis=1) if names else 0
    markets["competitors"] = markets.apply(lambda r: competitor_text(r, names), axis=1)
    markets["region"] = markets["state"].map(STATE_REGION)
    price_files = {n: place(pd.read_csv(p, dtype=str), zcta) for n, p in (x.split("=", 1) for x in a.price_file)}
    price_texts = dict(x.split("=", 1) for x in a.price_text)
    for n, clubs in price_files.items():
        markets[f"price_{n}"] = nearest_text(markets, clubs.dropna(subset=["lat", "lon"]), a.radius)

    def prices(r):
        parts = []
        for n in names:
            if r[f"n_{n}"] > 0 and isinstance(r.get(f"price_{n}"), str):
                parts.append(f"{BRAND_LABEL.get(n, n)}: {r[f'price_{n}']}")
            elif r[f"n_{n}"] > 0 and n in price_texts:
                parts.append(f"{BRAND_LABEL.get(n, n)}: {price_texts[n]}")
        for n in price_files:
            if n not in names and isinstance(r.get(f"price_{n}"), str):
                parts.append(f"{BRAND_LABEL.get(n, n)}: {r[f'price_{n}']}")
        return "; ".join(parts) if parts else "none to compare"
    if price_files or price_texts:
        markets["nearby_prices"] = markets.apply(prices, axis=1)
    if a.state_price:
        sp = pd.read_csv(a.state_price).set_index("state")["price"]
        markets["state_price"] = markets["state"].map(sp).fillna(a.national_price)
    markets.to_csv(a.markets_out, index=False)

    comp_mask = markets["n_competitors"] > 0
    strata = {"competitor nearby": markets[comp_mask], "no competitor nearby": markets[~comp_mask]}
    half = a.n // 2
    rows = []
    for label, pool in strata.items():
        k = half if label == "competitor nearby" else a.n - half
        idx = rng.choice(len(pool), size=k, replace=len(pool) < k)
        weight = (len(pool) / len(markets)) / (k / a.n)
        for i in idx:
            m = pool.iloc[i]
            rows.append({
                "age": draw_band(rng, m, "age_", AGE_TILT),
                "gender": pick(rng, GENDER),
                "household_income": draw_band(rng, m, "hh_"),
                "lives_near": f"{str(m['city']).strip().title()}, {m['state']}",
                "market_type": m["area_type"],
                "budget_gyms_nearby": m["competitors"],
                "gym_history": pick(rng, GYM_HISTORY),
                "workout_style": pick(rng, WORKOUT),
                "away_from_home_club": pick(rng, AWAY),
                **({"nearby_gym_prices": m["nearby_prices"]} if "nearby_prices" in m else {}),
                **({"state_gym_price": f"about ${m['state_price']:.0f}/mo"} if "state_price" in m and pd.notna(m["state_price"]) else {}),
                "_weight": round(weight, 6),
                "_region": m["region"],
                "_state": m["state"],
                "_n_competitors": int(m["n_competitors"]),
                **({"_state_price": round(float(m["state_price"]), 2)} if "state_price" in m and pd.notna(m["state_price"]) else {}),
                **({"_premium_nearby": int(isinstance(m.get("price_CrunchPremium"), str))} if "price_CrunchPremium" in m else {}),
                "_stratum": label,
            })
    order = rng.permutation(len(rows))
    out = pd.DataFrame([rows[i] for i in order])
    out.insert(0, "persona_id", [f"{a.panel}-{i:04d}" for i in range(len(out))])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.drop(columns=["_stratum"]).to_csv(a.out, index=False)

    print(f"stores {len(stores)} (no ZCTA match: {unmatched}); markets {len(markets)}")
    print("competitor nearby:", f"{comp_mask.mean():.1%}", "| by brand:",
          {n: f"{(markets[f'n_{n}'] > 0).mean():.1%}" for n in names})
    print("area type:", markets["area_type"].value_counts(normalize=True).round(3).to_dict())
    print("personas:", len(out), out["_stratum"].value_counts().to_dict(),
          "weights:", out.groupby("_stratum")["_weight"].first().round(3).to_dict())
    # Store ZIPs and the full trade-area table stay in --markets-out, not in the persona file.


if __name__ == "__main__":
    main()
