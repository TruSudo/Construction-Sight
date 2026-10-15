from pathlib import Path


def test_current_handoff_links_to_single_status_and_retains_history() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "STATUS.md" in readme
    assert Path("STATUS.md").read_text(encoding="utf-8").strip()
    for old_path in (
        "CURRENT_HANDOFF_CONTEXT.md",
        "architecture/current_implementation_status.md",
    ):
        assert not Path("docs", old_path).exists()
        assert Path("docs/archive", old_path).is_file()
