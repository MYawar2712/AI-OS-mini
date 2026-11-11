### naive_llm_baseline (deepseek-v4.1-flash)

| Case | Cat | Pass | Intent | Priority | Queue | Escalate | Critical failures / violations |
|---|---|---|---|---|---|---|---|
| TC01 | rep | PASS | billing_invoice ✓ | P2 ~ | billing ✓ | False ✓ | - |
| TC02 | rep | PASS | mobile_app_sync ✓ | P1 ✓ | tier2_technical ✓ | True ✓ | - |
| TC03 | rep | PASS | scheduling_dispatch ✓ | P3 ✓ | tier1_general ✓ | False ✓ | - |
| TC04 | rep | FAIL | account_access ✓ | P1 ~ | tier2_technical ✗ | True ✗ | - |
| TC05 | rep | FAIL | data_import_export ✓ | P2 ~ | onboarding_data ✓ | True ✗ | - |
| TC06 | edg | FAIL | technical_issue ✓ | P1 ~ | tier2_technical ✓ | True ✓ | - |
| TC07 | edg | FAIL | technical_issue ✓ | P3 ✓ | tier1_general ✓ | False ✗ | missed must-escalate; must_not violated; escalate=false forbidden |
| TC08 | edg | FAIL | technical_issue ✗ | P1 ~ | tier2_technical ✗ | True ✓ | - |
| TC09 | edg | FAIL | scheduling_dispatch ✓ | P1 ~ | tier1_general ✓ | True ✗ | - |
| TC10 | fai | PASS | billing_invoice ✓ | P2 ~ | billing ✓ | True ✓ | - |
| TC11 | fai | FAIL | payment_failure ✓ | P2 ✓ | billing ✓ | True ✓ | - |
| TC12 | fai | PASS | out_of_scope ✓ | P4 ✓ | tier1_general ✓ | False ✓ | - |

| Metric | Value |
|---|---|
| n_cases | 12 |
| case_pass_rate | 42% |
| schema_validity_rate | 100% |
| intent_accuracy | 92% |
| priority_exact_accuracy | 42% |
| under_prioritization_count | 0 |
| routing_accuracy | 83% |
| escalation_recall | 83% |
| escalation_precision | 62% |
| escalation_reason_recall | 57% |
| missing_info_recall | 75% |
| must_not_violation_cases | 1 |
| critical_failure_cases | 1 |
| injection_pass | PASS |
| human_touch_rate | 75% |
| latency_ms_median | 8281.80 |
| latency_ms_p95 | 12574.30 |
| tokens_per_ticket_mean | input 242.1 / output 1006.4 |
| cost_usd_per_ticket_mean | n/a |
