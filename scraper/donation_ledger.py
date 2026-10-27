"""Durable, replay-safe insertion of LGL submissions into the normalized Sheet.

The SHA-256 of the entire raw MIME message is the submission identity.
It stays stable when an unread message is retried after an IMAP flag failure,
or after an ambiguous append result (e.g. Sheets returned a timeout).

The ledger adds a final "submission id" column to the existing entries Sheet.
Legacy rows have empty IDs and must be reconciled before opening-day replay.
"""
import hashlib
import time

import gspread
from requests.exceptions import RequestException


SUBMISSION_ID = "submission id"
NORMALIZED_FIELDS = (
    "phone number", "total amount", "first name", "last name",
    "anonymous donation", "first time giver", "graduation year", "status",
    "work referral", "recurring payment", "source",
)
# Cumulative delay exceeds a per-minute Google Sheets quota window.
RETRY_DELAYS = (15, 30, 60, 60)


def fingerprint(raw_message: bytes) -> str:
    """Stable per-message key, without exposing the email or donor data."""
    return hashlib.sha256(raw_message).hexdigest()


def _retryable(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError, RequestException)):
        return True
    if isinstance(error, gspread.exceptions.APIError):
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        return status == 429 or status in (500, 502, 503, 504)
    return False


def retry(operation, *, sleeper=time.sleep):
    """Retry transient API failures without retrying permanent validation errors."""
    for delay in (*RETRY_DELAYS, None):
        try:
            return operation()
        except Exception as error:
            if delay is None or not _retryable(error):
                raise
            sleeper(delay)


class SubmissionLedger:
    """One Sheets read for known keys, followed by atomic row appends.

    A write exception is ALWAYS followed by a read to determine whether
    the row was actually appended; blindly retrying would double-count it.
    """

    def __init__(self, gc, spreadsheet_key: str, worksheet: str,
                 normalized_fields: tuple[str, ...], *, read_only: bool = False,
                 sleeper=time.sleep):
        self.sleeper = sleeper
        self.ws = self._open_worksheet(
            gc, spreadsheet_key, worksheet, len(normalized_fields), read_only,
        )
        initial_headers = retry(lambda: self.ws.row_values(1), sleeper=self.sleeper)
        self.headers = list(initial_headers)
        self._prepare_headers(normalized_fields, read_only)
        self.id_col = self.headers.index(SUBMISSION_ID) + 1
        self.tracking_enabled = (
            bool(initial_headers and SUBMISSION_ID in initial_headers) or not read_only
        )
        self.ids, self.legacy_rows = self._read_state()
        # Previously imported gifts without a stable ID cannot be replayed.
        if self.legacy_rows and not read_only:
            raise ValueError("Existing unkeyed donations require reconciliation before ingestion")

    def _open_worksheet(self, gc, key, name, width, read_only):
        spreadsheet = retry(lambda: gc.open_by_key(key), sleeper=self.sleeper)
        try:
            return retry(lambda: spreadsheet.worksheet(name), sleeper=self.sleeper)
        except gspread.WorksheetNotFound:
            if read_only:
                raise ValueError("Cannot reconcile: normalized worksheet does not exist")
            return retry(
                lambda: spreadsheet.add_worksheet(title=name, rows=1000, cols=width + 1),
                sleeper=self.sleeper,
            )

    def _prepare_headers(self, fields, read_only):
        if not self.headers:
            self.headers = [*fields, SUBMISSION_ID]
            if not read_only:
                retry(
                    lambda: self.ws.append_row(self.headers, value_input_option="RAW"),
                    sleeper=self.sleeper,
                )
            return

        if not set(fields).issubset(self.headers):
            raise ValueError("Normalized sheet columns do not match expected contract")
        if SUBMISSION_ID in self.headers:
            return

        # Inspect prior rows before writing even the new header cell.
        if not read_only:
            rows = retry(lambda: self.ws.get_all_values(), sleeper=self.sleeper)
            if any(any(row) for row in rows[1:]):
                raise ValueError(
                    "Existing unkeyed donations require reconciliation before ingestion"
                )
        self.headers.append(SUBMISSION_ID)
        if not read_only:
            retry(
                lambda: self.ws.update_cell(1, len(self.headers), SUBMISSION_ID),
                sleeper=self.sleeper,
            )

    def _read_state(self):
        rows = retry(lambda: self.ws.get_all_values(), sleeper=self.sleeper)
        index = self.id_col - 1
        ids = set()
        legacy = 0
        for values in rows[1:]:
            if not any(values):
                continue
            key = values[index].strip() if index < len(values) else ""
            if key:
                if key in ids:
                    raise ValueError("Duplicate submission IDs in normalized Sheet")
                ids.add(key)
            else:
                legacy += 1
        return ids, legacy

    def known(self, submission_id: str) -> bool:
        return submission_id in self.ids

    def insert(self, row: dict, submission_id: str) -> bool:
        """Return True if inserted; False if already persisted."""
        if submission_id in self.ids:
            return False

        payload = [submission_id if key == SUBMISSION_ID else row.get(key, "")
                   for key in self.headers]
        # The sheet stores a complete row, including its identity, in one append.
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                self.ws.append_row(payload, value_input_option="RAW")
                self.ids.add(submission_id)
                return True
            except Exception as error:
                # If the server applied the append before losing its response,
                # the persisted ID wins, even if the exception was a 429/timeout.
                self.ids, self.legacy_rows = self._read_state()
                if submission_id in self.ids:
                    return False
                if attempt == len(RETRY_DELAYS) or not _retryable(error):
                    raise
                self.sleeper(RETRY_DELAYS[attempt])
        raise AssertionError("unreachable")
