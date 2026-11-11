# 03: Evidence of pain

> **Labels used here.** **MEASURED-SYN** = measured on our 12-case synthetic set. **ESTIMATE** = derived from stated assumptions. **ASSUMED** = an input we chose and have not yet validated. **No production data was used.** Reproduce the cost table with `python -m scripts.pain_model`. Inputs are in [`config/pain_model.yaml`](../../config/pain_model.yaml).

## 1. Pain-model inputs

| Input | Low / Base / High | Label | Reasoning / source | Assumption |
|---|---|---|---|---|
| Tier-1 reps | 3 | ASSUMED | Typical small-to-mid SaaS support team | A-02 |
| Tickets / rep / day | 35 / 50 / 65 | ASSUMED | Common practitioner range for email-heavy B2B Tier-1 desks. Not a cited benchmark. | A-03 |
| Minutes per manual triage | 2 / 3 / 5 | ESTIMATE | Read (≈1 min) + CRM lookup (≈1 min) + classify/route/note (≈1 min). Excludes resolution. To be timed with [protocol 05](05_manual_baseline_protocol.md). | A-04 |
| Misroute rate | 6% / 12% / 20% | ASSUMED | Practitioners commonly report "around 1 in 10" tickets reassigned. Unverified. | A-05 |
| Rework per misroute | 8 / 15 / 25 min | ESTIMATE | Receiving team reads and bounces it, then Tier-1 re-reads and re-routes | A-06 |
| Priority error rate | 8% / 15% / 25% | ASSUMED | No written P-definitions today plus subjective tone. Our cheat-sheet baseline got 17% wrong on the synthetic set (MEASURED-SYN, n=12). | A-08 |
| Added customer wait per misroute | 1 / 3 / 6 h | ESTIMATE | One extra queue hop at typical P3 response targets | A-09 |
| Loaded labour cost | £12 / £14 / £17 per hour | ASSUMED | Deliberately low, per the project owner's request (demo) | A-07 |

## 2. Cost model (ESTIMATE)

| Metric | Low | Base | High |
|---|---|---|---|
| Tickets / week | 525 | 750 | 975 |
| Triage hours / week | 17.5 | 37.5 | 81.2 |
| Misroutes / week | 32 | 90 | 195 |
| Rework hours / week | 4.2 | 22.5 | 81.2 |
| **Total hours / week** | **21.7** | **60.0** | **162.5** |
| FTE equivalent (37.5 h) | 0.58 | 1.60 | 4.33 |
| Labour cost / week | £260 | £840 | £2,762 |
| **Labour cost / year** | **£13.5k** | **£43.7k** | **£143.7k** |
| Priority errors / week | 42 | 112 | 244 |
| Customer wait hours added / week | 32 | 270 | 1,170 |
| Projected LLM cost / week (Haiku-class, ~2.5k in / 0.4k out tokens per ticket) | $0.24 | $0.34 | $0.44 |

**Reading this table:** even in the low scenario, triage costs over half an FTE. The base case spends **60 hours a week** on triage and rework. Running an LLM on every ticket is projected at **under $1/week**, so model cost is not the constraint: **accuracy and safety are.** The money case is not "replace a rep". It is: give back roughly 1 FTE of time and cut misroutes and under-prioritisation.

The model **excludes** the cost of a missed P1 (idle field teams) and of churn. These are rarer but much larger, so we treat them as **safety gates** rather than putting a £ value on them.

## 3. Failure modes of manual triage

| # | Failure mode | Consequence | Covered by test case |
|---|---|---|---|
| F1 | Inconsistent priority between reps (no written definitions) | Unfair queueing, SLA misses, bad reporting | TC04, TC09 |
| F2 | Calmly described outage under-prioritised | Whole field team idle; most expensive failure | TC02 |
| F3 | Multi-intent ticket: second issue silently dropped | Customer has to chase; repeat contact | TC06 |
| F4 | Vague ticket guessed at, not clarified | Wrong queue, ping-pong with the customer | TC07 |
| F5 | Churn signal buried in a technical complaint | CS finds out too late to save the renewal | TC08 |
| F6 | Mixed-language / informal text misread | Urgent on-site issue treated as routine | TC09 |
| F7 | Missing account info not requested up front | Extra round-trip before work starts | TC03, TC05, TC11 |
| F8 | Card data / PII copied into internal notes | PCI/GDPR exposure | TC11 |
| F9 | Text that tries to manipulate the handler (social engineering; prompt injection once AI is involved) | Wrong priority, unauthorised refunds | TC10 |
| F10 | Out-of-scope requests sent to specialists | Wasted Tier-2 / Product time | TC12 |

## 4. What the synthetic baseline already shows (MEASURED-SYN, n=12)

The cheat-sheet keyword baseline mimics a rep following a cheat sheet. It passed **5/12** cases, with **33% escalation recall**, **1 under-prioritised P2**, a **failed injection case**, and **card digits copied into the summary**. See [00 summary](00_day1_summary.md). This is a synthetic smoke test, not a measurement of real reps. It does show that the failure modes above can be detected and measured with this harness.
