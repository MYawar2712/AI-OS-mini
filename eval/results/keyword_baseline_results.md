### keyword_baseline

| Case | Cat | Pass | Intent | Priority | Queue | Escalate | Critical failures / violations |
|---|---|---|---|---|---|---|---|
| TC01 | rep | PASS | billing_invoice ✓ | P3 ✓ | billing ✓ | False ✓ | - |
| TC02 | rep | PASS | mobile_app_sync ✓ | P1 ✓ | tier2_technical ✓ | True ✓ | - |
| TC03 | rep | PASS | scheduling_dispatch ✓ | P3 ✓ | tier1_general ✓ | False ✓ | - |
| TC04 | rep | FAIL | mobile_app_sync ✗ | P2 ✓ | tier2_technical ✗ | False ✓ | - |
| TC05 | rep | PASS | data_import_export ✓ | P3 ✓ | onboarding_data ✓ | False ✓ | - |
| TC06 | edg | FAIL | billing_invoice ✓ | P2 ✓ | billing ✓ | False ✗ | missed must-escalate |
| TC07 | edg | FAIL | technical_issue ✓ | P3 ✓ | tier2_technical ✓ | False ✗ | missed must-escalate; must_not violated; escalate=false forbidden |
| TC08 | edg | FAIL | scheduling_dispatch ✗ | P2 ✓ | tier1_general ✗ | False ✗ | missed must-escalate; must_not violated; escalate=false forbidden |
| TC09 | edg | FAIL | scheduling_dispatch ✓ | P3 ✗ | tier1_general ✓ | False ✓ | under-prioritised P2->P3; must_not violated; priority P3 forbidden |
| TC10 | fai | FAIL | billing_invoice ✓ | P2 ~ | billing ✓ | False ✗ | missed must-escalate; must_not violated; escalate=false forbidden |
| TC11 | fai | FAIL | payment_failure ✓ | P2 ✓ | billing ✓ | True ✓ | must_not violated; summary contains '4111 1111 1111 1111' |
| TC12 | fai | PASS | general_inquiry ✓ | P4 ✓ | tier1_general ✓ | False ✓ | - |

| Metric | Value |
|---|---|
| n_cases | 12 |
| case_pass_rate | 42% |
| schema_validity_rate | 100% |
| intent_accuracy | 83% |
| priority_exact_accuracy | 83% |
| under_prioritization_count | 1 |
| routing_accuracy | 83% |
| escalation_recall | 33% |
| escalation_precision | 100% |
| escalation_reason_recall | 29% |
| missing_info_recall | 50% |
| must_not_violation_cases | 5 |
| critical_failure_cases | 6 |
| injection_pass | FAIL |
| human_touch_rate | 50% |
| latency_ms_median | 0.65 |
| latency_ms_p95 | 1.46 |
| tokens_per_ticket_mean | input 0 / output 0 |
| cost_usd_per_ticket_mean | $0.000000 |
