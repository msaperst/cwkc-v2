#!/usr/bin/env bash
# GitHub may acknowledge an upload before artifact listing catches up.
set -euo pipefail

: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_RUN_ID:?}"
: "${PAGES_ARTIFACT_NAME:?}"
: "${PAGES_ARTIFACT_ID:?}"

for attempt in {1..12}; do
    if artifact_id="$(gh api --method GET \
        "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts" \
        -f "name=$PAGES_ARTIFACT_NAME" \
        --jq '.artifacts | map(select(.expired == false)) | if length == 1 then .[0].id else empty end')" \
        && [[ "$artifact_id" == "$PAGES_ARTIFACT_ID" ]]; then
        echo "Pages artifact is visible: $PAGES_ARTIFACT_NAME"
        exit 0
    fi
    echo "Waiting for Pages artifact visibility ($attempt/12)"
    if [[ "$attempt" != 12 ]]; then sleep 5; fi
done

echo "::error::Uploaded Pages artifact did not become visible; start a fresh deployment or retry this job."
exit 1
