"""Realized-purchase outcome data from the SRS Snowflake account.

The queries below were written against objects visible to the SRS MCP analyst role
(checked 2026-11-21):

- SRS_MCP.YIPIT.CHWY_CORE_METRICS: YipitData Chewy panel. `analysis_name =
  'Net Sales - by Brand'` gives net sales (USD) for 77 brands sold on Chewy at daily,
  weekly, monthly and quarterly cadence, 2021-02 onward. This is brand-level realized
  purchasing and is the best in-house backtest target found so far: test a panel of
  Chewy brands/products and compare synthetic PI with brand sales or share.
- SRS_VENDORS.FUNDAMENTALS.VISIBLE_ALPHA_KPIS_V: reported company KPIs and consensus,
  for company-level outcomes (e.g. a segment's revenue after a launch).

Card and receipt panels for other companies are reached through the YipitData connector
(key metrics are company-level, not brand-level, for most products). Raw panel tables
were not visible to the MCP analyst role; ask the SRS data team which panel tables your
own Snowflake role can read and add a query here.

Running these from Python needs your own Snowflake credentials
(`pip install synthpanel[snowflake]`); the MCP service user is not usable from code.
"""

from __future__ import annotations

import os

import pandas as pd

CHEWY_BRAND_SALES_SQL = """
SELECT
    slice_value_1                     AS brand,
    period_start,
    period_end,
    metric_value                      AS net_sales_usd
FROM SRS_MCP.YIPIT.CHWY_CORE_METRICS
WHERE analysis_name = 'Net Sales - by Brand'
  AND data_cadence  = %(cadence)s
  AND period_start >= %(start)s
  AND period_start <  %(end)s
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY slice_value_1, period_start ORDER BY publication_timestamp DESC
) = 1
ORDER BY brand, period_start
"""


def chewy_brand_outcomes(conn, start: str, end: str, cadence: str = "quarterly") -> pd.DataFrame:
    """Brand-level outcomes over [start, end): total net sales, share of the tracked
    brands' sales, and growth from the first to the last period in the window.

    Returns columns: concept_id (= brand), net_sales_usd, share, growth.
    Use brand names (or a mapping to them) as concept_id in the concepts file.
    """
    df = pd.read_sql(CHEWY_BRAND_SALES_SQL, conn, params={"cadence": cadence, "start": start, "end": end})
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values(["brand", "period_start"])
    agg = df.groupby("brand").agg(net_sales_usd=("net_sales_usd", "sum"),
                                  first=("net_sales_usd", "first"), last=("net_sales_usd", "last"))
    agg["share"] = agg["net_sales_usd"] / agg["net_sales_usd"].sum()
    agg["growth"] = agg["last"] / agg["first"] - 1
    return agg.drop(columns=["first", "last"]).reset_index().rename(columns={"brand": "concept_id"})


def snowflake_connection():
    """Connect with your own credentials from the environment (never commit them)."""
    import snowflake.connector  # optional dependency

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator=os.environ.get("SNOWFLAKE_AUTHENTICATOR", "externalbrowser"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
    )
