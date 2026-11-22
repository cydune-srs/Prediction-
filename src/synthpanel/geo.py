"""Real-geography personas: trade areas around actual store locations, described with Census data.

Inputs (all public, from www2.census.gov):
- 2024 Gazetteer ZCTA file (ZIP Code Tabulation Area centroids and land area)
- ACS 2024 5-year table-based summary files: B01003 (population), B19001 (household income
  brackets), B01001 (sex by age)

A store's trade area is every ZCTA whose centroid lies within `radius_miles` of the store's ZIP
centroid. Store ZIPs are matched to ZCTAs by code; ZIPs with no ZCTA (PO boxes, unique ZIPs) are
reported, not guessed. Distances between ZIP centroids are approximate (typically within a few miles).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

EARTH_MILES = 3958.8

# B19001 bracket columns grouped into persona income bands.
INCOME_BANDS = {
    "under $35,000": range(2, 8),            # <10k .. 30-35k
    "$35,000-$59,999": range(8, 12),         # 35-40k .. 50-60k
    "$60,000-$99,999": range(12, 14),        # 60-75k, 75-100k
    "$100,000-$149,999": range(14, 16),      # 100-125k, 125-150k
    "$150,000 or more": range(16, 18),       # 150-200k, 200k+
}
# B01001 male cells (female = +24) grouped into adult age bands.
AGE_BANDS = {
    "18-24": range(7, 11), "25-34": range(11, 13), "35-44": range(13, 15),
    "45-54": range(15, 17), "55-64": range(17, 20), "65+": range(20, 26),
}


def _read_acs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="|", dtype={"GEO_ID": str})
    df = df[df["GEO_ID"].str.startswith("860Z200US")].copy()
    df["zcta"] = df["GEO_ID"].str[-5:]
    return df.set_index("zcta")


def load_zcta_table(raw: str | Path) -> pd.DataFrame:
    """One row per ZCTA: lat, lon, land area, population, income-band and age-band counts."""
    raw = Path(raw)
    gaz = pd.read_csv(raw / "2024_Gaz_zcta_national.txt", sep="\t", dtype={"GEOID": str})
    gaz.columns = [c.strip() for c in gaz.columns]
    gaz = gaz.rename(columns={"GEOID": "zcta", "INTPTLAT": "lat", "INTPTLONG": "lon", "ALAND_SQMI": "land_sqmi"})
    out = gaz.set_index("zcta")[["lat", "lon", "land_sqmi"]]

    pop = _read_acs(raw / "acsdt5y2024-b01003.dat")["B01003_E001"].rename("population")
    inc = _read_acs(raw / "acsdt5y2024-b19001.dat")
    age = _read_acs(raw / "acsdt5y2024-b01001.dat")
    cols = {"population": pop}
    for band, idx in INCOME_BANDS.items():
        cols[f"hh_{band}"] = sum(pd.to_numeric(inc[f"B19001_E{i:03d}"], errors="coerce") for i in idx)
    for band, idx in AGE_BANDS.items():
        cols[f"age_{band}"] = sum(pd.to_numeric(age[f"B01001_E{i:03d}"], errors="coerce")
                                  + pd.to_numeric(age[f"B01001_E{i + 24:03d}"], errors="coerce") for i in idx)
    acs = pd.DataFrame(cols)
    return out.join(acs, how="inner").fillna(0)


def _haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_MILES * np.arcsin(np.sqrt(a))


def locate(stores: pd.DataFrame, zcta: pd.DataFrame) -> pd.DataFrame:
    """Attach ZCTA centroid lat/lon to stores by 5-digit ZIP. Unmatched rows get NaN."""
    s = stores.copy()
    s["zip"] = s["zip"].astype(str).str.extract(r"(\d{5})")[0]
    return s.join(zcta[["lat", "lon"]], on="zip")


def trade_areas(stores: pd.DataFrame, zcta: pd.DataFrame, radius_miles: float = 5.0,
                competitors: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Per store: population, density, income/age band counts within the radius, and competitor counts."""
    stores = stores.dropna(subset=["lat", "lon"]).copy()
    z_lat, z_lon = zcta["lat"].to_numpy(), zcta["lon"].to_numpy()
    sum_cols = [c for c in zcta.columns if c == "population" or c.startswith(("hh_", "age_"))]
    zvals = zcta[sum_cols].to_numpy(float)
    rows = []
    for lat, lon in zip(stores["lat"], stores["lon"]):
        near = _haversine(lat, lon, z_lat, z_lon) <= radius_miles
        rows.append(zvals[near].sum(axis=0))
    agg = pd.DataFrame(rows, columns=sum_cols, index=stores.index)
    stores = stores.join(agg)
    stores["density_per_sqmi"] = stores["population"] / (np.pi * radius_miles ** 2)
    for name, comp in (competitors or {}).items():
        comp = comp.dropna(subset=["lat", "lon"])
        c_lat, c_lon = comp["lat"].to_numpy(), comp["lon"].to_numpy()
        stores[f"n_{name}"] = [int((_haversine(lat, lon, c_lat, c_lon) <= radius_miles).sum())
                               for lat, lon in zip(stores["lat"], stores["lon"])]
    return stores


def area_type(population_within_radius: float, city: float = 250_000, small: float = 50_000) -> str:
    """Classify a 5-mile trade area by resident population (≈3,200 and ≈640 people per sq mi)."""
    if population_within_radius >= city:
        return "a big city"
    if population_within_radius < small:
        return "a small town or rural area"
    return "a suburb"


def draw_band(rng: np.random.Generator, row: pd.Series, prefix: str, tilt: dict[str, float] | None = None) -> str:
    """Draw one band from a store's trade-area counts (e.g. prefix 'hh_' or 'age_'), optionally tilted."""
    bands = [c[len(prefix):] for c in row.index if c.startswith(prefix)]
    w = np.array([row[prefix + b] * (tilt or {}).get(b, 1.0) for b in bands], float)
    if w.sum() <= 0:
        w = np.ones(len(bands))
    return str(rng.choice(bands, p=w / w.sum()))
