"""Contract and boundary tests for the production GitHub Actions season gate."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import subprocess

import pytest

from scraper import contest_window

ROOT = Path(__file__).resolve().parents[2]
START = contest_window.START
END = contest_window.END


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (START - timedelta(microseconds=1), False),
        (START, True),
        (START + timedelta(microseconds=1), True),
        (START + timedelta(days=3), True),
        (END - timedelta(microseconds=1), True),
        (END, False),
        (END + timedelta(microseconds=1), False),
    ],
)
def test_half_open_contest_boundary(when, expected):
    assert contest_window.is_active(when) is expected


def test_utc_and_local_time_represent_same_boundary():
    assert START.astimezone(timezone.utc).isoformat() == "2026-11-30T05:00:00+00:00"
    assert END.astimezone(timezone.utc).isoformat() == "2026-12-08T01:00:00+00:00"
    assert contest_window.is_active(datetime.fromisoformat("2026-11-30T05:00:00+00:00"))
    assert not contest_window.is_active(datetime.fromisoformat("2026-12-08T01:00:00+00:00"))


def test_timezone_required():
    naive_datetime = datetime(2026, 12, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        contest_window.is_active(naive_datetime)


def test_frontend_and_backend_read_one_season_config():
    from scraper import season_config

    config = season_config.load_config()
    assert START == datetime.fromisoformat(config["start"])
    assert END == datetime.fromisoformat(config["end"])
    generated = season_config.BROWSER_PATH.read_text(encoding="utf-8")
    assert generated == season_config.render_browser_config(config)
    script = (ROOT / "public/assets/js/main.js").read_text(encoding="utf-8")
    assert "globalThis.CWKC_SEASON" in script
    assert "2026-11-30T00:00:00-05:00" not in script
    assert "2026-12-07T20:00:00-05:00" not in script
    html = (ROOT / "public/index.html").read_text(encoding="utf-8")
    assert html.index('src="assets/js/season-config.js"') < html.index('src="assets/js/main.js"')


@pytest.mark.parametrize("active", [True, False])
def test_github_output_is_boolean(tmp_path, monkeypatch, capsys, active):
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(contest_window, "is_active", lambda: active)
    monkeypatch.setenv("CWKC_INGESTION_ENABLED", "true")
    monkeypatch.setattr("sys.argv", ["contest_window"])
    contest_window.main()
    assert output.read_text(encoding="utf-8") == f"active={str(active).lower()}\n"
    assert ("enabled" if active else "disabled") in capsys.readouterr().out


def test_require_active_fails_closed(tmp_path, monkeypatch):
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(contest_window, "is_active", lambda: False)
    monkeypatch.setenv("CWKC_INGESTION_ENABLED", "true")
    monkeypatch.setattr("sys.argv", ["contest_window", "--require-active"])
    with pytest.raises(SystemExit, match="Outside approved collection window"):
        contest_window.main()
    assert output.read_text(encoding="utf-8") == "active=false\n"


def test_missing_enable_switch_blocks_collection_even_in_window(tmp_path, monkeypatch):
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("CWKC_INGESTION_ENABLED", raising=False)
    monkeypatch.setattr(contest_window, "is_active", lambda: True)
    monkeypatch.setattr("sys.argv", ["contest_window", "--require-active"])
    with pytest.raises(SystemExit, match="Outside approved collection window"):
        contest_window.main()
    assert output.read_text(encoding="utf-8") == "active=false\n"


def test_changed_vs_unchanged_csv_against_published_snapshot(tmp_path):
    baseline = tmp_path / "last-published.csv"
    generated = tmp_path / "results.csv"
    baseline.write_text("uva,vt\n0,0\n", encoding="utf-8")
    generated.write_bytes(baseline.read_bytes())

    def identical():
        return subprocess.run(["cmp", "-s", str(baseline), str(generated)],
                              check=False).returncode

    assert identical() == 0
    generated.write_text("uva,vt\n1,0\n", encoding="utf-8")
    assert identical() == 1


def test_update_workflow_guards_and_single_publisher():
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert workflow.count("CWKC_INGESTION_ENABLED:") == 2
    assert workflow.count('python -m scraper.contest_window --require-active') == 2
    assert "if: needs.check-window.outputs.active == 'true'" in workflow
    assert "python -m scraper.contest_window --require-active" in workflow
    assert 'cmp -s .cwkc-previous-results.csv public/assets/csv/results.csv' in workflow
    assert "python -m scraper.scoreboard_snapshot restore --backup" in workflow
    assert 'if: steps.changes.outputs.changed == \'true\'' in workflow
    assert "if: needs.recompute.result == 'success' && needs.recompute.outputs.changed == 'true'" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "group: updates" in workflow
    assert "group: pages" in workflow
    assert "python -m scraper.getLglFormData" in workflow
    assert "python getGoogleFormData.py" in workflow
    assert workflow.index("python -m scraper.getLglFormData") < workflow.index("python getGoogleFormData.py")
    assert workflow.index("python getGoogleFormData.py") < workflow.index("cmp -s")
    assert "git push origin HEAD:main" not in workflow
    assert workflow.count("git -C \"$RUNNER_TEMP/cwkc-published\" push origin HEAD:cwkc-results") == 1
    assert "actions/upload-artifact@" in workflow
    assert "actions/download-artifact@" in workflow
    assert "name: results-csv-" in workflow
    assert workflow.index("Reject publication after cutoff") < workflow.index(
        "Commit reconciled scoreboard to data branch")
    assert "git diff public/assets/csv/results.csv &> /dev/null" not in workflow
    assert "|| github.event_name == 'workflow_dispatch'" not in workflow
    assert "2025-11-01" not in workflow
    assert "2025-12-10" not in workflow


def test_no_mutable_action_refs_in_update_workflow():
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    refs = re.findall(r"^\s*uses:\s+(\S+)", workflow, flags=re.MULTILINE)
    assert refs
    assert all(re.search(r"@[0-9a-f]{40}$", action) for action in refs)


def test_update_workflow_uses_explicit_2026_donations_sheet_variable():
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assert "SPREADSHEET_SHEET: ${{ vars.CWKC_DONATIONS_WORKSHEET || 'entries' }}" in workflow
    assert "python -m scraper.getLglFormData" in workflow
