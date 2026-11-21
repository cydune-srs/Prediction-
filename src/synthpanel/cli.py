"""Command line: synthpanel run | compare-human | backtest."""

from __future__ import annotations

import argparse
import logging
import sys
import zlib
from pathlib import Path

import pandas as pd

from synthpanel.anchors import DEFAULT_PURCHASE_INTENT_ANCHORS, load_anchor_sets
from synthpanel.concepts import load_concepts
from synthpanel.embeddings import get_embedder
from synthpanel.personas import PersonaSampler, load_personas
from synthpanel.respondents import ClaudeBatchRespondent, ClaudeRespondent, ScriptedRespondent
from synthpanel.ssr import SSRScorer
from synthpanel.survey import SurveyResult, run_survey


def _dry_run_script(task) -> str:
    # Deterministic placeholder answers so the pipeline can be exercised without API calls.
    options = [
        "I definitely would not buy this, it is not for me.",
        "I probably would not buy this.",
        "I might or might not buy this, I am not sure.",
        "I would probably buy this, it looks useful.",
        "I would definitely buy this right away.",
    ]
    return options[zlib.crc32(task.task_id.encode()) % len(options)]


def cmd_run(args: argparse.Namespace) -> None:
    concepts = load_concepts(args.concepts)
    if Path(args.personas).exists():
        personas = load_personas(args.personas)
    else:
        personas = PersonaSampler(seed=args.seed).sample(int(args.personas))
    n_tasks = len(concepts) * len(personas) * args.draws
    print(f"{len(concepts)} concepts x {len(personas)} personas x {args.draws} draws = {n_tasks} LLM calls")

    if args.dry_run:
        respondent, embedder = ScriptedRespondent(_dry_run_script), get_embedder("hashing")
    else:
        embedder = get_embedder(args.embedder)
        if args.mode == "batch":
            respondent = ClaudeBatchRespondent(model=args.model, effort=args.effort)
        else:
            respondent = ClaudeRespondent(model=args.model, effort=args.effort, concurrency=args.concurrency)

    anchors = load_anchor_sets(args.anchors) if args.anchors else DEFAULT_PURCHASE_INTENT_ANCHORS
    scorer = SSRScorer(embedder, anchors, epsilon=args.epsilon, temperature=args.temperature)
    result = run_survey(concepts, personas, respondent, scorer, draws_per_persona=args.draws)
    result.save(args.out)
    print(result.by_concept()[["concept_id", "n", "mean_pi", "top2box"]].to_string(index=False))
    print(f"\nSaved to {args.out}")


def cmd_compare_human(args: argparse.Namespace) -> None:
    from synthpanel.validation.human import compare_with_humans, load_human_ratings

    report = compare_with_humans(SurveyResult.load(args.survey), load_human_ratings(args.human))
    print(report["per_concept"].to_string(index=False))
    print()
    for k, v in report["summary"].items():
        print(f"{k}: {v}")


def cmd_backtest(args: argparse.Namespace) -> None:
    from synthpanel.validation.realized import backtest

    summary = SurveyResult.load(args.survey).by_concept()
    outcomes = pd.read_csv(args.outcomes, dtype={"concept_id": str})
    rep = backtest(summary, outcomes, args.outcome_col, pi_col=args.pi_col,
                   group_col=args.group_col, log_outcome=not args.no_log)
    print(f"concepts: {rep['n_concepts']}  PI: {rep['pi_statistic']}  outcome: {rep['outcome']}")
    lo, hi = rep["spearman_ci95"]
    print(f"Spearman {rep['spearman']:.3f} (95% CI {lo:.3f} to {hi:.3f}, p={rep['spearman_p']:.3g})")
    if "within_group" in rep and not rep["within_group"].empty:
        print("\nWithin-group:\n" + rep["within_group"].to_string(index=False))
    if "calibration" in rep:
        c = rep["calibration"]
        print(f"\nCalibration: slope {c.slope:.3f}, leave-one-out MAPE {c.loo_mape:.1%}")
    elif "calibration_error" in rep:
        print(f"\nCalibration skipped: {rep['calibration_error']}")


def cmd_cortex_sql(args: argparse.Namespace) -> None:
    from synthpanel.backends import cortex
    from synthpanel.study import load_study

    study = load_study(args.study)
    panel = study.panels[args.panel]
    builders = {
        "personas": lambda: cortex.personas_sql(panel, args.stage),
        "answers": lambda: cortex.answers_sql(study, panel, args.cell, args.stage, args.max_personas,
                                              tuple(args.persona_range) if args.persona_range else None),
        "score": lambda: cortex.score_sql(study, panel, args.stage, embed_model=study.embedder),
        "readout": lambda: cortex.readout_sql(panel, args.stage, args.segment),
        "paired": lambda: cortex.paired_sql(panel, args.stage, args.segment, args.weighted),
        "switching": lambda: cortex.switching_sql(panel, args.stage, args.cell),
    }
    if args.step in ("answers", "switching") and not args.cell:
        raise SystemExit(f"--cell is required for step {args.step}; cells: {[c.concept_id for c in panel.cells]}")
    print(builders[args.step]())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="synthpanel", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run a synthetic purchase-intent survey")
    r.add_argument("--concepts", required=True, help="YAML file of concepts")
    r.add_argument("--personas", required=True, help="CSV of personas, or a number to sample")
    r.add_argument("--out", required=True, help="Output folder")
    r.add_argument("--draws", type=int, default=1, help="Answers per persona per concept")
    r.add_argument("--mode", choices=["realtime", "batch"], default="realtime")
    r.add_argument("--model", default="claude-opus-5-5")
    r.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    r.add_argument("--concurrency", type=int, default=16)
    r.add_argument("--embedder", default="voyage", help="voyage[:model] | st[:model] | hashing")
    r.add_argument("--anchors", help="YAML anchor sets (default: built-in purchase-intent sets)")
    r.add_argument("--temperature", type=float, default=1.0, help="SSR temperature")
    r.add_argument("--epsilon", type=float, default=0.0, help="SSR epsilon")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--dry-run", action="store_true", help="No API calls: canned answers, hashing embedder")
    r.set_defaults(func=cmd_run)

    h = sub.add_parser("compare-human", help="KS similarity and correlation attainment vs a human survey")
    h.add_argument("--survey", required=True, help="Folder written by `run`")
    h.add_argument("--human", required=True, help="CSV with concept_id, rating")
    h.set_defaults(func=cmd_compare_human)

    b = sub.add_parser("backtest", help="Synthetic PI vs realized purchases")
    b.add_argument("--survey", required=True)
    b.add_argument("--outcomes", required=True, help="CSV with concept_id and the outcome column")
    b.add_argument("--outcome-col", required=True)
    b.add_argument("--pi-col", default="top2box", choices=["top2box", "mean_pi"])
    b.add_argument("--group-col", help="Outcome-file column for within-group tests (e.g. category)")
    b.add_argument("--no-log", action="store_true", help="Calibrate on the raw outcome, not its log")
    b.set_defaults(func=cmd_backtest)

    s = sub.add_parser("cortex-sql", help="Print the Snowflake Cortex SQL for one step of a study")
    s.add_argument("--study", required=True, help="Study YAML (see studies/)")
    s.add_argument("--stage", required=True, help="Stage folder for this run, e.g. @DB.SCHEMA.STAGE/study/run_YYYYMMDD")
    s.add_argument("--panel", required=True)
    s.add_argument("--step", required=True, choices=["personas", "answers", "score", "readout", "paired", "switching"])
    s.add_argument("--cell", help="Cell id (answers, switching)")
    s.add_argument("--max-personas", type=int, help="Pilot: only the first N personas (answers)")
    s.add_argument("--persona-range", type=int, nargs=2, metavar=("START", "END"),
                   help="Answers for personas START..END-1 only, into their own part folder")
    s.add_argument("--segment", help="Persona attribute to break the readout/paired results down by")
    s.add_argument("--weighted", action="store_true", help="Paired: weight strata to the panel's strata_weights")
    s.set_defaults(func=cmd_cortex_sql)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
