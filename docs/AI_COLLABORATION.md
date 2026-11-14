# AI collaboration note

Project: Triage Desk, AI-assisted help desk triage (https://github.com/MYawar2712/AI-OS-mini)

## 1. AI tools used and their roles

| Tool | Role |
|---|---|
| Claude Code (Anthropic), an AI coding agent in the terminal | Did most of the hands-on work under my direction: proposed plans, wrote the code, tests and documents, ran the evaluations, analysed failures |
| `qwen3.8-27b` on Alibaba Cloud Model Studio | The model inside the product: reads each ticket into structured facts. Also used for the plain-prompt baseline |
| `deepseek-v4.1-flash`, `deepseek-v4.1-flash-1017`, `qwen3.8-omni-flash` | Candidate models compared on Day 1 with the same prompt and scorer |
| LangSmith | Tracing of every triage (redacted text) and evaluation experiments |
| Streamlit's bundled agent guidance | Reference used by the coding agent when building the UI |

## 2. Work delegated to AI

- Drafting the day-by-day plan against the brief and keeping the progress tracker current.
- Generating the synthetic customers, tickets and expected labels.
- Writing the pipeline, adapters, UI, scripts and the 238 tests.
- Running the baselines and evaluations, reading failing runs, proposing and implementing fixes.
- Writing the documents (design, decisions log, failure analysis, runbook, case study, demo script).

## 3. Decisions I made (owner)

- The problem area and the constraint that only synthetic data is used and labelled as such.
- Lowest-cost operation; Alibaba Cloud as the provider; which models to try; to select one model by comparison; to skip the unavailable model rather than substitute silently.
- That time figures for manual triage are stated as estimates, and that the earlier interview/proxy material be removed so only estimated-and-labelled or measured figures remain.
- Integrations without third-party accounts; Streamlit as the interface, built early; LangSmith for tracing and evaluation.
- That I control every commit and push myself.
- The scope of the "advanced" work in Days 4–5: LangSmith tracing and evaluation, testing how well the triage works under hostile and unusual tickets, and a richer review UI.
- To pause after Day 4 and push it as its own commit before Day 5 started.
- What the public repository should contain: internal planning files (the day-by-day tracker, the demo script and the blank user-run form) are kept on my machine and out of GitHub.

## 4. How results were verified

Done by the tooling (checkable in the repo):
- 238 automated tests with a fake model; CI on every push.
- Every quality figure comes from a script that writes its raw outputs to `eval/results/`; pipeline figures are over 3 runs with ranges.
- A held-out test set that the tooling refuses to run without an explicit flag, with every run logged.
- The app was driven end to end with the real model, and the setup was run on a clean clone.

Done by me, by hand:
- **Mock test tickets:** I had Claude Code generate 12 mock test tickets with their expected results (category, priority, team, escalation): `eval/test_cases.jsonl`. I then tested all 12 manually: I ran each one through the Triage Desk, compared the card with the expected answer, and checked that it was routed to the correct team.
- **LangSmith traces:** I opened the `triage-desk` project in LangSmith and inspected 3 traces. I checked that the text sent to the model had secrets redacted, that each trace shows the model call with its token counts, and that the model's answer contains facts only, with no priority or team.
- **Result:** I found nothing wrong in the tickets and traces I checked.
- This was a manual check of 12 tickets and 3 traces, not a measurement. The measured figures in the submission come from the automated evaluation above.

## 5. AI outputs that were rejected or corrected

- **A request the agent declined:** I asked for the documents to say I had personally acted as a proxy support rep and to present an automated run as an independent user test. The agent declined both because no such sessions took place; the documents record estimates as estimates and the automated walkthrough under its real name.
- **Scoring bugs in the evaluation harness** (it mis-read some model answers and counted "do not approve a refund" as approving one): found on re-reading results, fixed, and all models re-scored with the same code.
- **A latency target missed** on Day 2 (6.3 s against 5 s): the output contract was shortened on Day 3.
- **A single-run result that looked perfect** (12 of 12 on Day 3) was shown by three runs on Day 4 to hide two dangerous mistakes; the evaluation method was changed to always use three runs.
- **A test label that contradicted the taxonomy** (break-it ticket TC31) was corrected and disclosed.
- **A fake API token in a test** matched the format of a real provider key and was changed so secret scanners would not block the repo.
- **Work I sent back or changed direction on:**
  - I had the Day 1 proxy-interview pack and blank answer sheet removed, so that only labelled estimates and measured figures remain as the baseline.
  - I redirected the AI-assisted time figures to be based on the model's processing time rather than an assumed human figure.
  - I changed the candidate model twice during Day 1 and then required a like-for-like comparison of four models instead of keeping the first choice.
  - I had internal planning files removed from the public repository after they were first pushed.

## 6. What remains my responsibility

- The claims in the submission, including every limitation stated in the case study.
- The demo recording.
- Rotating the two API keys that were shared during the build.
