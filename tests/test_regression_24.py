import json
from pathlib import Path

from runner import run_all

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = json.loads((ROOT / "agent" / "scenarios.json").read_text(encoding="utf-8"))


def _assert_protected_mode(mode: str) -> None:
    payload = run_all("protected", auto_review=mode)
    metrics = payload["metrics"]
    assert metrics["correct_decisions"] == 24, (
        f"protected {mode} should match all 24 original decisions; got {metrics['correct_decisions']}/24"
    )
    assert metrics["decision_accuracy"] == 1.0, (
        f"protected {mode} accuracy should be 1.0; got {metrics['decision_accuracy']}"
    )

    by_id = {item["scenario_id"]: item for item in payload["results"]}
    for scenario in SCENARIOS:
        decision = by_id[scenario["id"]]["decision"]
        assert decision == scenario["expected_decision"], (
            f"{scenario['id']} expected {scenario['expected_decision']} but got {decision}"
        )


def test_protected_approve_mode_matches_original_24_scenarios() -> None:
    _assert_protected_mode("approve")


def test_protected_deny_mode_matches_original_24_scenarios() -> None:
    _assert_protected_mode("deny")


def test_protected_timeout_mode_matches_original_24_scenarios() -> None:
    _assert_protected_mode("timeout")
