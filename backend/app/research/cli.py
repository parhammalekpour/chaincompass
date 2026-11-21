from __future__ import annotations

import argparse
import asyncio
import subprocess
import time
from pathlib import Path

from app.research.health_score import run_health_score_study
from app.research.regimes import run_regime_study
from app.research.reports import write_study_report
from app.research.repository import load_research_data
from app.research.scenarios import run_scenario_study

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIRECTORY = REPOSITORY_ROOT / "docs"
STUDIES = ("S", "H", "R")


def _protocol_commit() -> str | None:
    result = subprocess.run(
        [
            "git",
            "log",
            "-n",
            "1",
            "--format=%H",
            "--",
            "docs/RESEARCH_PROTOCOL.md",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run read-only historical research.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run registered research studies.")
    run.add_argument(
        "--study",
        choices=(*STUDIES, "all"),
        required=True,
        help="Study to run: S, H, R, or all.",
    )
    return parser


async def _run_selected(study: str) -> list[Path]:
    data = await load_research_data()
    protocol_commit = _protocol_commit()
    selected = STUDIES if study == "all" else (study,)
    outputs: list[Path] = []
    for selected_study in selected:
        if selected_study == "S":
            result = run_scenario_study(data.prices_by_chain, protocol_commit)
        elif selected_study == "H":
            result = run_health_score_study(
                data.scores_by_chain,
                data.prices_by_chain,
                protocol_commit,
            )
        else:
            result = run_regime_study(
                data.features_by_chain,
                data.stored_regimes_by_chain,
                protocol_commit,
            )
        outputs.extend(write_study_report(DOCS_DIRECTORY, selected_study, result))
    return outputs


def main() -> None:
    args = _parser().parse_args()
    started = time.perf_counter()
    outputs = asyncio.run(_run_selected(args.study))
    runtime = time.perf_counter() - started
    for output in outputs:
        print(output.relative_to(REPOSITORY_ROOT))
    print(f"Completed study {args.study} in {runtime:.3f}s.")
