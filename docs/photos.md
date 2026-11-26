# Moderated photo gallery

Photo publication is separate from donation and participation scoring. No photo
is published merely because someone submitted it, or because a score counts it.

## One-time configuration

1. Enable the Google Drive API in the existing service account's Google Cloud
   project. Grant the actual service-account client email Viewer access to both
   response spreadsheets and both Forms upload folders. Keep the folders private.
2. In each response spreadsheet, open Extensions → Apps Script. Replace the
   existing CWKC dispatch script with [photo-moderation.gs](../scripts/photo-moderation.gs).
   Preserve the existing Script Properties GITHUB_REPO and GITHUB_DISPATCH_TOKEN.
   Optionally set PHOTO_REVIEW_EMAILS to a comma-separated list of authorized
   moderators. The script sends a short notification with a private Sheet link,
   not an attachment or public photo URL. Alternatively use Google Forms' native
   new-response email notifications.
3. Run setupPhotoApprovals once in each bound script, authorizing access as
   prompted. This creates the private Photo approvals tab.
4. Retain exactly one installable **From spreadsheet → On form submit** trigger
   for notifyGitHubOfParticipation. Add an installable **From spreadsheet →
   On edit** trigger for notifyGitHubOfPhotoEdit. Authorize both under the
   organizer's account. Simple triggers cannot make authenticated API calls.
5. Once reviewed and ready, set the repository Actions variable
   CWKC_PHOTOS_ENABLED to true. It controls photo synchronization and display,
   not the competition's existing date or ingestion gate.

## Review

Each new upload with applicable release permission is queued with Approved=No.
For each photo, open Review photo privately, confirm the organizer has permission
to publish it (including permission from any identifiable people and appropriate
guardian consent for minors), write short descriptive alt text without names or
private information, and set Approved to Yes. Hanukkah uploads also require the
form's affirmative Yes release answer. Gathering photos require organizer review
of publication permission even if the submission counts toward scoring.

Previously submitted photos can be added manually to the approval tab, one Drive
file ID per row; the importer checks each ID against the current season's
response sheet. Never approve an arbitrary Drive file. Do not replace the
contents of an approved Drive file; revoke approval and review a new upload.

Manual edits to the approval tab or response tab dispatch sheet-change. Setting
Approved to No or clearing approval removes the photo on the next successful
sync and deployment. If rows were deleted or modified by another script/API,
manually run **Sync approved photos**; installable edit triggers do not cover
all structural or programmatic changes.

## Publication and recovery

The separate photo-sync.yml workflow runs on sheet-change, manual dispatch and a
periodic fallback (15 minutes during the event calendar and daily otherwise).
It reads the private approval and response sheets using read-only credentials,
downloads approved JPEG/PNG/WebP files (up to 25 MiB, 40 megapixels), rotates and
resizes them to at most 1600 pixels, re-encodes as JPEG without original
metadata, and builds a new content-addressed gallery manifest. Missing approval,
revoked consent and prior-year submissions are excluded. An inaccessible or
unsupported approved image is omitted and logged as an aggregate warning.

Only approved, optimized derivatives and the public manifest are written to
cwkc-photos; original uploads, Drive IDs, response rows and credentials are
never committed. All Pages deployments overlay the validated gallery snapshot
and the appropriate published scoreboard. Missing or invalid photo snapshots
display an empty gallery without interrupting scoreboard deployment.

**Public history:** Approved derivatives are public and may remain in Git
history, browser/CDN caches or third-party copies after takedown. Moderators
must understand this before approval. Revocation removes the image from the
current deployed site, not all historical copies. In an urgent takedown,
disable CWKC_PHOTOS_ENABLED and manually run the normal Pages deploy; investigate
any historical copies separately. Reconcile approvals and sync before restoring
public display. Do not enable public sharing on the raw upload folders.

## Prelaunch test

Submit a synthetic photo with no private information; verify the review queue
and notification. The existing scoring workflow must remain gated off, while
the photo workflow runs with no approved images. Approve the photo and confirm
the edit triggers a successful photo sync and Pages deployment. Confirm the
school and category, then revoke approval and confirm the image and manifest
entry disappear. Verify the donation ledger and public results CSV were not
changed. If deployment failed after the photo branch was updated, manually run
Sync approved photos again (manual runs deploy even if the snapshot is unchanged).
