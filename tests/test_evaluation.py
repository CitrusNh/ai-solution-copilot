from pathlib import Path

from eval import evaluate as evaluation_runner


PROJECT_ROOT = Path(__file__).parents[1]


def test_evaluation_dataset_has_unique_ten_cases():
    cases = evaluation_runner.load_cases(PROJECT_ROOT / "eval" / "questions.jsonl")

    assert len(cases) == 10
    assert len({case["case_id"] for case in cases}) == 10
    assert sum(case["risk_tier"] == "critical" for case in cases) == 3


def test_evaluation_summary_has_explicit_denominators():
    results = evaluation_runner.run_evaluation(
        PROJECT_ROOT / "eval" / "questions.jsonl",
        PROJECT_ROOT / "data" / "demo",
    )
    summary = evaluation_runner.summarize(results)

    assert summary["total_cases"] == 10
    assert summary["critical_cases"] == 3
    assert 0 <= summary["pass_rate"] <= 1
    assert summary["total_cost_usd"] == 0


def test_required_term_matching_ignores_whitespace_only():
    assert evaluation_runner.normalize_for_match("保留 180 天") == "保留180天"
