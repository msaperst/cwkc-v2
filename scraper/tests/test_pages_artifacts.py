"""Regression checks for retry-safe Pages artifacts."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wait-for-pages-artifact.sh"


@pytest.mark.parametrize("workflow", ["update.yml", "deploy.yml"])
def test_pages_artifact_is_unique_to_attempt_and_waited_for(workflow):
    source = (ROOT / ".github/workflows" / workflow).read_text()
    name = "github-pages-${{ github.run_id }}-${{ github.run_attempt }}"
    assert f"name: {name}" in source
    assert f"PAGES_ARTIFACT_NAME: {name}" in source
    assert f"artifact_name: {name}" in source
    assert "PAGES_ARTIFACT_ID: ${{ steps.pages-artifact.outputs.artifact_id }}" in source
    assert "actions: read" in source
    assert source.index("uses: actions/upload-pages-artifact@") < source.index(
        "bash scripts/wait-for-pages-artifact.sh") < source.index("uses: actions/deploy-pages@")


@pytest.mark.parametrize(("responses", "expected", "calls"), [
    (["42"], 0, 1),
    (["", "41", "ERROR", "42"], 0, 4),
    (["41"] * 12, 1, 12),
    ([""] * 12, 1, 12),
])
def test_wait_for_exact_artifact(tmp_path, responses, expected, calls):
    counter = tmp_path / "count"
    counter.write_text("0")
    values = tmp_path / "responses"
    values.write_text("\n".join(responses) + "\n")
    gh = tmp_path / "gh"
    gh.write_text(
        '#!/bin/bash\n'
        '[[ "$*" == *"repos/example/site/actions/runs/123/artifacts"* ]] || exit 9\n'
        '[[ "$*" == *"name=github-pages-123-2"* ]] || exit 9\n'
        'n=$(cat "$COUNTER"); n=$((n+1)); echo "$n" > "$COUNTER"\n'
        'value=$(sed -n "${n}p" "$RESPONSES")\n'
        '[[ "$value" != ERROR ]] || exit 1\n'
        'printf "%s\\n" "$value"\n'
    )
    sleep = tmp_path / "sleep"
    sleep.write_text("#!/bin/bash\nexit 0\n")
    for executable in (gh, sleep):
        executable.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}",
               COUNTER=str(counter), RESPONSES=str(values),
               GITHUB_REPOSITORY="example/site", GITHUB_RUN_ID="123",
               PAGES_ARTIFACT_NAME="github-pages-123-2", PAGES_ARTIFACT_ID="42")
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == expected
    assert int(counter.read_text()) == calls
    assert ("Pages artifact is visible" in result.stdout) == (expected == 0)
