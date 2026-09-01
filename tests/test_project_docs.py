from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def test_readme_exposes_demo_and_portfolio_materials():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "ai-solution-copilot-fn445bidjzbyu35ars4k6q.streamlit.app" in readme
    for relative_path in (
        "docs/architecture.md",
        "docs/portfolio-package.md",
        "docs/demo-script.md",
        "docs/hr-pitch.md",
        "docs/interview-guide.md",
        "eval/final-report.md",
    ):
        assert relative_path in readme
        assert (PROJECT_ROOT / relative_path).exists()


def test_portfolio_materials_state_validation_limits_honestly():
    portfolio = (PROJECT_ROOT / "docs" / "portfolio-package.md").read_text(
        encoding="utf-8"
    )
    architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(
        encoding="utf-8"
    )
    interview = (PROJECT_ROOT / "docs" / "interview-guide.md").read_text(
        encoding="utf-8"
    )
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    linux_packages = (PROJECT_ROOT / "packages.txt").read_text(encoding="utf-8")

    assert "真实用户反馈目前仍待收集" in portfolio
    assert "不是生产系统" in architecture
    assert "RapidOCR" in architecture
    assert "当前 APINebula Key" in interview
    assert "CHAT_MODEL=" in env_example
    assert "libgl1" in linux_packages


def test_final_report_keeps_development_scope_explicit():
    report = (PROJECT_ROOT / "eval" / "final-report.md").read_text(encoding="utf-8")

    assert "100%（10/10）" in report
    assert "不代表真实企业客户准确率" in report
