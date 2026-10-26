"""Season configuration is the single source for browser and ingestion dates."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from scraper import season_config


@pytest.fixture
def valid_config():
    return {
        "year": 2026,
        "timezone": "America/New_York",
        "start": "2026-11-30T00:00:00-05:00",
        "end": "2026-12-07T20:00:00-05:00",
    }


def test_repository_generated_browser_script_is_fresh(valid_config):
    assert season_config.load_config() == valid_config
    assert season_config.BROWSER_PATH.read_text(encoding="utf-8") == (
        season_config.render_browser_config(valid_config)
    )
    html = season_config.HTML_PATH.read_text(encoding="utf-8")
    assert season_config.render_html_metadata(html, valid_config) == html


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("year", True, "Invalid competition year"),
        ("year", "2026", "Invalid competition year"),
        ("year", 1900, "Invalid competition year"),
        ("start", "2026-11-30T00:00:00", "timezone offset"),
        ("end", "2026-12-07T20:00:00", "timezone offset"),
        ("start", "2026-11-30T00:00:00-04:00", "does not match"),
        ("end", "2026-12-07T20:00:00-04:00", "does not match"),
        ("start", "2026-12-10T00:00:00-05:00", "ordering"),
        ("end", "2025-12-07T20:00:00-05:00", "ordering"),
    ],
)
def test_config_rejects_invalid_fields(valid_config, tmp_path, field, value, error):
    data = {**valid_config, field: value}
    path = tmp_path / "season.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        season_config.load_config(path)


def test_config_rejects_missing_or_extra_fields(valid_config, tmp_path):
    path = tmp_path / "season.json"
    valid_config.pop("timezone")
    path.write_text(json.dumps(valid_config), encoding="utf-8")
    with pytest.raises(ValueError, match="must have"):
        season_config.load_config(path)


def test_generation_cli_write_and_check(tmp_path, valid_config, monkeypatch, capsys):
    generated = tmp_path / "season-config.js"
    html = tmp_path / "index.html"
    html.write_text(
        '<meta content="2025 Commonwealth Kiddush Cup" property="og:description" />\n'
        '<meta content="2025 Commonwealth Kiddush Cup" property="og:title" />\n'
        '<title>2025 Commonwealth Kiddush Cup | UVA vs. Virginia Tech</title>\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(season_config, "BROWSER_PATH", generated)
    monkeypatch.setattr(season_config, "HTML_PATH", html)
    monkeypatch.setattr(season_config, "load_config", lambda: valid_config)
    monkeypatch.setattr("sys.argv", ["season_config", "--write"])
    assert season_config.main() == 0
    assert generated.read_text(encoding="utf-8") == (
        season_config.render_browser_config(valid_config)
    )
    assert '2026 Commonwealth Kiddush Cup' in html.read_text(encoding="utf-8")
    assert '2025 Commonwealth Kiddush Cup' not in html.read_text(encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["season_config", "--check"])
    assert season_config.main() == 0
    assert "matches" in capsys.readouterr().out
    generated.write_text("// stale config", encoding="utf-8")
    with pytest.raises(SystemExit, match="stale"):
        season_config.main()
    generated.unlink()
    with pytest.raises(SystemExit, match="stale"):
        season_config.main()

    monkeypatch.setattr("sys.argv", ["season_config", "--write"])
    assert season_config.main() == 0
    html.write_text(
        html.read_text(encoding="utf-8").replace("2026 Commonwealth Kiddush Cup",
                                                 "2027 Commonwealth Kiddush Cup", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["season_config", "--check"])
    with pytest.raises(SystemExit, match="Static page metadata is stale"):
        season_config.main()


def test_cli_without_mode_shows_help(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["season_config"])
    assert season_config.main() == 0
    assert "--write" in capsys.readouterr().out


def test_html_metadata_updates_when_the_year_changes(valid_config):
    original = season_config.HTML_PATH.read_text(encoding="utf-8")
    next_season = {**valid_config, "year": 2027}
    rendered = season_config.render_html_metadata(original, next_season)
    assert '<title>2027 Commonwealth Kiddush Cup | UVA vs. Virginia Tech</title>' in rendered
    assert 'content="2027 Commonwealth Kiddush Cup" property="og:title"' in rendered
    assert 'content="2027 Commonwealth Kiddush Cup" property="og:description"' in rendered
    assert 'content="2026 Commonwealth Kiddush Cup" property="og:title"' not in rendered


def test_generator_fails_if_expected_seo_metadata_is_missing(valid_config):
    with pytest.raises(ValueError, match="Expected exactly one"):
        season_config.render_html_metadata("<title>Other page</title>", valid_config)
