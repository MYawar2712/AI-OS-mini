# Day 4: Feedback from the target / proxy user

> **Status: no feedback from a person has been collected yet.** The brief asks for it, and it is recorded here as an open gap rather than filled with invented comments.

## What exists instead (not user feedback)

| Source | What it can tell us | What it cannot |
|---|---|---|
| Automated clean-room README walkthrough ([day3/03](../day3/03_cleanroom_walkthrough.md)) | Whether the written steps work on a fresh copy: 7 problems found and fixed (the main one: a ticket file saved by Excel in its default format stopped the app) | Whether a person understands the card, trusts it, or finds it faster |
| Evaluation on labelled tickets ([02_regression.md](02_regression.md)) | How often the suggestion is right | How a rep reacts to a wrong one |

## Changes made from those findings

| Finding | Change | Status |
|---|---|---|
| Excel-saved ticket file stopped the app | Reader accepts both Excel CSV formats | Done (Day 3) |
| Install time understated; pip notice looked like an error; `.env` step relied on renaming a hidden file | README corrected; `setup.ps1` does all three steps in one command | Done |
| Row errors were technical | Plain wording per column | Done (Day 3) |
| Riskiest tickets were not at the top of the inbox | Inbox sorted P1 first, with filters (Needs a lead, P1/P2, Low confidence, Not processed) | Done (Day 4) |

## How to collect the real thing (20 minutes)

1. A person who did not build it follows the README alone, processes the queue, and reviews at least 8 tickets.
2. They note their setup time, where they got stuck and what they misread, and answer:
   - Which card did you trust least, and why?
   - Was there a ticket where you would have accepted a wrong suggestion?
   - What on the card did you not use?
   - Would this be faster than triaging by hand? What would stop you using it?
3. The Activity page gives the measured part: accepted-as-is rate, edits by field, time to decide.

Each answer then becomes a row in the table above with the change made.
