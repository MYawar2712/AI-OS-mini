# Day 4: Failure analysis

> Synthetic data. Evidence files are under `eval/results/day4/`. "Run" = one pass of the pipeline over a test set with the real model (`qwen3.8-27b`).
> Method: run each set 3 times (the model does not give identical answers every time), read the model's extracted facts for every failing run, find the cause, fix it, re-run.

## Summary

| # | Failure | Where seen | Root cause | Fix | Result after fix |
|---|---|---|---|---|---|
| F1 | Ticket sent to manual triage although the model answered correctly | Dev TC04 (1 of 3 runs), break-it TC34 (1 of 3), v0.3 | The model wrote a field name in US spelling (`duplicate_or_unauthorized_payment`). Strict validation rejected the whole answer, and the retry made the same slip | Known spelling variants are mapped; unknown extra keys are dropped; a *missing* key or wrong type still fails (`normalise_keys`, `src/pipeline/llm_extract.py`) | 0 fallbacks in 102 v1 case-runs (dev 36 + break-it 30 + held-out 36) |
| F2 | A company-wide outage marked P2 with **no escalation** | Dev TC02 (1 of 3 runs), v0.3 | The model contradicted itself: "whole team affected", "job today affected", "no workaround", but "core workflow not blocked". The P1 rule required the "blocked" flag | Consistency rule **R-C1**: many users + job today + no workaround ⇒ treated as blocked (`rules.priority`) | TC02 was P1 in 3 of 3 v1 runs, but the model happened to be consistent in those runs, so **R-C1 did not need to fire**. The rule is proven by unit tests (`test_contradictory_facts_are_treated_as_blocked_p1`), not yet by a live recurrence |
| F3 | A pasted live API token was not flagged, and the ticket was not escalated | Break-it TC31 (3 of 3 runs), v0.3 | The redactor only knew cards, CVV, expiry and passwords | Token patterns added: known prefixes (`sk_live_`, `sk-`, `ghp_`, `xoxb-`, `AKIA…`) and long opaque values after "token / api key / secret / bearer" (`src/pipeline/redact.py`) | TC31 flagged `sensitive_data_present` and the token never reaches the model, logs or traces: 3 of 3 |
| F4 | When the assistant failed, the "triage manually" suggestion carried **P3** | Follows from F1 (TC04 is a P2 ticket) | The fallback used a fixed P3. If the assistant cannot read a ticket, its urgency is unknown, and P3 means an 8-hour reply target | Fallback now uses **P2** ("fail high") and still always asks for a lead | Covered by `test_missing_key_still_falls_back` |
| F5 | A quote request read as a general question (P4, Tier-1 instead of P3, Customer Success) | Held-out TC19 (1 of 3 runs; also Day 2) | Model reads "how much would it cost to add 10 seats" as a question rather than a commercial request. Intent is the one field no rule cross-checks | **Not fixed, on purpose:** held-out failures are never used for tuning (ADR-021). Candidate for next iteration: a similar *new* dev case, then a prompt example | Open. Not a safety failure |
| F6 | A bulk-rescheduling request for tomorrow read as a feature request and given P4 | Held-out TC24 (1 of 3 runs) | Model treats "can we move all of tomorrow's jobs at once" as asking for a feature. P4 is forbidden for this case because jobs are affected tomorrow | **Not fixed, on purpose** (same reason). Candidate: a "time-bound request is never P4" rule, tested on new dev cases first | Open. Counted as 1 dangerous mistake in 1 of 3 held-out runs |
| F7 | Latency gate (< 5 s) | Day 2: 6.3 s median | Output tokens dominate (about 20 ms per token) | Prompt extract-v2 (Day 3, ADR-026) | Median 3.4–3.7 s on all three sets over 3 runs each. **p95 is 5.5–6.3 s**: the tail is still above 5 s |

## What the failures have in common

1. **The model is good at reading and unreliable at being consistent.** F1 and F2 were not wrong readings of the ticket. They were formatting and self-consistency slips that appear in roughly 1 run in 3 for a given ticket. A single evaluation run would have missed both (Day 3's single dev run showed 12/12).
2. **Deterministic guards fix deterministic gaps well.** F1–F4 were fixed in code with unit tests, without touching the prompt.
3. **Intent is the weak point.** F5 and F6 are both intent misreadings, and intent is the only decision the model makes alone. That is where the next iteration should add a cross-check.

## What a failure costs, and who catches it

| Failure type | Caught by | If nobody catches it |
|---|---|---|
| Fallback (F1) | Shown to the rep as "Automatic triage failed" with a lead flag | Slower handling only |
| Under-prioritised P1 (F2) | Only the rep reading the card | A company-wide outage waits up to 2 h instead of 30 min, with no lead told |
| Secret not flagged (F3) | Nobody | The token is sent to the model provider and stored in logs |
| Wrong category (F5, F6) | The rep (Edit) | Ticket goes to the wrong team; reply target too slow |

F2 and F3 are the reason the release gates count "dangerous mistakes" separately from the pass rate.

## Honest limits
- The dev and break-it sets were used to find and fix F1–F4, so their 100% after the fix is expected and is **not** an unbiased score. The held-out set (94%, range 92–100%) is the better estimate.
- 34 tickets and 3 runs each is a small sample. "0 fallbacks in 102 case-runs" does not mean it cannot happen.
- One label was corrected after the first run: break-it TC31 was labelled P3 while also accepting "general question" as its category, which the taxonomy defines as P4. The label is now P4. It failed before and after that correction for the real reason (the token was not flagged).
- The plain-AI baseline also varies between runs (dev 58% in one run, 42% in another), so baseline numbers are single-run indications.
- The fake API token in break-it TC31 was shortened after the runs (to `sk_live_DEMO0token1234`) so it cannot be mistaken for a real provider key by secret scanners. The saved result files were updated with the same replacement; the redaction test covers the new value.
