from pathlib import Path

import pandas as pd

from synthpanel.cli import main

EXAMPLE = Path(__file__).parent.parent / "examples" / "concepts_example.yaml"


def test_dry_run_then_backtest(tmp_path, capsys):
    out = tmp_path / "run"
    main(["run", "--concepts", str(EXAMPLE), "--personas", "30", "--out", str(out), "--dry-run"])
    assert (out / "responses.csv").exists() and (out / "concepts.csv").exists()
    summary = pd.read_csv(out / "concepts.csv")
    assert len(summary) == 4 and summary["n"].eq(30).all()

    outcomes = tmp_path / "outcomes.csv"
    pd.DataFrame({"concept_id": summary["concept_id"], "sales": range(1, 5)}).to_csv(outcomes, index=False)
    # Four concepts is below the backtest minimum; the error should say so clearly.
    try:
        main(["backtest", "--survey", str(out), "--outcomes", str(outcomes), "--outcome-col", "sales"])
    except ValueError as e:
        assert "need at least 5" in str(e)
    else:
        raise AssertionError("expected a ValueError for too few concepts")
