# Moderated photo gallery

Photo publication is independent of participation scoring: a submitted photo can
count toward a score without permission to display it.

## One-time setup

1. Enable the Google Drive API in the existing service account's Google Cloud
   project. Give the service-account client email Viewer access to both private
   Forms upload folders and response spreadsheets. Keep the folders private.
2. Append two columns to the right of the existing Form Responses 1 tab in
   **each** response workbook: **Image Approved** and **Image Alt Text**. Configure a strict Yes/No dropdown on the entire Image Approved column,
   excluding the header; leave new rows blank by default. Do not change the form questions. Restrict editing access
   to authorized reviewers; protect these columns if other editors need access.
3. In each spreadsheet's Extensions → Apps Script, update the existing
   triggerGithubAction function using [photo-moderation.gs](../scripts/photo-moderation.gs).
   Set or preserve Script Properties GITHUB_REPO (owner/repo),
   GITHUB_DISPATCH_TOKEN (existing restricted dispatch token), and optionally
   PHOTO_REVIEW_EMAILS (comma-separated authorized reviewer addresses).
   Do not paste tokens into source or cells. Authorize the new MailApp scope
   using the trigger owner account.
4. Retain the existing installable **From spreadsheet → On form submit** and
   **From spreadsheet → On change** triggers, both pointing to
   triggerGithubAction. Verify that a manual cell edit fires the change trigger;
   if not, add an installable On edit trigger for the same handler. A form-submit
   event sends a review email with the private response-row link and dispatches
   sheet-change; a change event dispatches without emailing. Script/API writes
   do not reliably fire these triggers.
5. Set the repository Actions variable CWKC_PHOTOS_ENABLED=true after review.
   Keep CWKC_INGESTION_ENABLED=false until the authorized competition opening.

## Approve or remove a photo

Open the uploaded image(s) using the original response row. Confirm public
display permission for everyone depicted, including appropriate guardian consent
for minors. Enter brief descriptive Image Alt Text (1–300 characters, no private
information) and set Image Approved to Yes. All images attached to that response share
the approval and description. Hanukkah photos additionally require the exact affirmative
answer in the form's photo-release field: “YES! You can share my photo on the CWKC webpage.”
Case and surrounding whitespace are normalized; a bare “Yes” is not accepted. Gathering uploads require organizer
verification of publication permission. Scoring eligibility is unchanged.

Clear Image Approved, set it to No, or clear Image Alt Text to revoke publication. The same
trigger runs the existing update workflow. Do not replace the contents of an
approved Drive file; revoke and review a new submission instead.

## Publication and recovery

The existing update.yml handles both scoring and photo updates. It uses the same
getGoogleFormData.py entry point for both, including --photos-only before kickoff
or after closing when photos are enabled but scoring is gated off. During the
competition, scheduled recomputation also refreshes photos; a daily fallback
handles missed changes outside the event window.

Approved JPEG/PNG/WebP uploads (up to 25 MiB and 40 megapixels) are resized to at
most 1600 pixels and re-encoded as JPEG without original metadata. Only optimized
images and their public manifest are committed alongside the scoreboard on
cwkc-results. Every Pages deployment overlays the validated, current-season
snapshot. Unapproved, revoked or prior-year submissions are omitted. Inaccessible
or unsupported approved files are omitted with an aggregate warning.

The browser polls photos.json every five seconds, independently of the scoreboard
timer; unchanged manifests do not reset the galleries. Failed polls retain the
last successful view. An already-visible gallery is cleared only after three
consecutive successful empty manifests, avoiding brief deployment flicker.
Removing the final image can therefore take two extra polling intervals (about
10 seconds after the first empty response); partial removals apply immediately.

**Public history:** Approved derivatives are public and may remain in Git history,
caches or third-party copies after revocation. Revocation removes the image from
the next deployed website, not from every historical copy. For urgent takedown,
disable CWKC_PHOTOS_ENABLED and manually deploy the site. Reconcile approval rows
and run an update before re-enabling display. Never make the original upload
folders public.

## End-to-end test before kickoff

Submit a synthetic photo with no private information. Confirm an email with the
private response-row link and the sheet-change run. Leave approval blank and
confirm no photo is published. Enter Image Alt Text and set Image Approved to Yes; verify the
change trigger, update run, Pages deployment and correct gallery appearing in an
already-open browser. Revoke approval and verify the photo disappears without a
reload. The donation inbox, ledger and published scoreboard must remain unchanged.
Remove the synthetic submission from Forms and the linked response sheet.

If a dispatch is missed or a deployment failed after a commit, manually run
Update results from multiple locations with the normal inputs (no rehearsal);
when the photo flag is enabled, it can sync and redeploy even outside the event
window. Verify the photo flag and the actual score gate before testing.
