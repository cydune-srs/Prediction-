"""Validate synthetic purchase intent against ground truth.

- `human`: against a real human Likert survey (the paper's test: KS similarity and
  correlation attainment).
- `realized`: against realized purchases (card/receipt panels, reported KPIs). This is
  the test that matters for forecasting, and the paper did not run it.
- `sources`: SQL and loaders for SRS outcome data in Snowflake.
"""
