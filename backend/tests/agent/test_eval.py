import os
import subprocess
import sys
from pathlib import Path

from app.agent.eval import load_cases

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_eval_cases_cover_english_and_persian_categories() -> None:
    cases = load_cases()
    assert len(cases) >= 30
    assert {case["language"] for case in cases} == {"en", "fa"}
    assert {
        "refusal",
        "allowed",
        "grounding",
        "injection",
        "banned_output",
        "persian_digits",
    }.issubset({case["category"] for case in cases})


def test_offline_eval_cli_passes_committed_cases() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "app.agent.eval"],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Total: 35/35 passed." in completed.stdout
