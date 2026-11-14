# Day 3: Clean-room README walkthrough (automated, not a user test)

> **What this is:** the README's "For support reps" steps followed literally in a fresh copy of the project
> (no virtual environment, no `.env`, no runtime data), with the app driven through its HTTP test interface and the real model.
> **What this is not:** a run by a support rep or any independent person. It cannot show whether a person
> understands the card or the wording. That evidence still has to come from a real session
> (first run by a person: still open).
> Date: 2026-11-13 · Windows 11, Python 3.14.2 · synthetic data only.

## Steps and measured times

| README step | Result | Time |
|---|---|---|
| 1. Install (`python -m venv` + `pip install`) | Worked. pip printed a red "new release of pip" notice that looks like an error | **6 min 19 s** (README said "about 2 minutes") |
| 2. Add the AI key | Without `.env`, and with the untouched example value, the setup check says the key is missing and tickets go to manual triage. With the key: "Ready" | n/a (file copy) |
| 3. Open the Triage Desk | Started; customer database and ticket queue were created automatically; inbox showed 24 new tickets | a few seconds |
| Process new tickets | 24 of 24 pre-filled, 0 fallbacks, 0 failures | **26.1 s** |
| Accept ×2 | SYN-24102 (P1, needs a lead): row written, escalation notice sent. SYN-24101 (P3): row written, no notice | |
| Reject ×1 | SYN-24104: marked manual triage, no triage fields written | |
| Edit ×1 | SYN-24103: priority changed P3 → P2, saved as "edited" | |
| Add a ticket in the CSV, saved the way Excel saves by default | **Failed: the app refused to start** (finding F1). After the fix: new ticket picked up, processed in 6.8 s, suggested P1 with escalation | |
| Add a row with an empty message | Skipped with a warning naming line 27; other tickets unaffected; the row stays in the file for fixing | |

Server console: no warnings or tracebacks. App log: no error events.

## Findings and fixes

| # | Finding | Severity | Fix (done) |
|---|---|---|---|
| F1 | A CSV saved in Excel's default "CSV (Comma delimited)" format (Windows-1252) containing a character like `£` could not be read, and the whole Triage Desk refused to start | **High**: the README tells reps to edit this file in Excel | The queue reader now accepts both encodings and saves back as UTF-8. Regression test `test_queue_reads_excel_default_cp1252_csv` |
| F2 | README said install takes "about 2 minutes"; measured 6 min 19 s | Medium (a rep may think it is stuck) | README now says 5–10 minutes |
| F3 | pip's upgrade notice appears in red and looks like a failure | Low | README says it can be ignored |
| F4 | Row-error text was technical ("body: String should have at least 1 character") | Medium | Plain wording per column ("the message is empty", valid channels, date format) |
| F5 | Copying `.env.example` without pasting a key gave the generic "not set" message | Low | Specific message: the example value is still there, replace it |
| F6 | README step 2 relied on renaming a dot-file in File Explorer, which hides extensions by default | Medium (not hit by the automation, a person likely would) | Step 2 is now one command that copies the file and opens it in Notepad |
| F7 | The "why" text boxes on Edit/Reject had no stable keys, so the automation could not fill them | Low (test-only) | Keys added |

## Limits of this evidence
- The times to decide in the audit log for this run (1.6–2.3 s) are automation speed, not a person's. They must not be used as review-time evidence.
- The copy inherited three old audit lines from the main project's `data/runs`; they are ignored above.
- Nothing here measures comprehension, trust, or whether the card wording is clear.

Tests after the fixes: 196 passing.
