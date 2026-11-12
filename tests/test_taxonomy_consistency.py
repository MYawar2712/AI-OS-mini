"""Expected outputs in the test set and the schema enums must agree with config/taxonomy.yaml."""
import json
import typing

import pytest

from src import schemas
from src.schemas import PRIORITY_RANK, load_test_cases
from src.taxonomy import ROOT, load_taxonomy

TAX = load_taxonomy()
CASES = load_test_cases(ROOT / "eval" / "test_cases.jsonl") + load_test_cases(ROOT / "eval" / "test_cases_holdout.jsonl")


@pytest.mark.parametrize("literal,key", [
    (schemas.Intent, "intents"), (schemas.Priority, "priorities"), (schemas.Queue, "queues"),
    (schemas.EscalationReason, "escalation_reasons"), (schemas.MissingInfo, "missing_info_fields"),
])
def test_schema_enums_match_taxonomy(literal, key):
    assert set(typing.get_args(literal)) == set(TAX[key])


def test_priority_ranks_match():
    assert {p: v["rank"] for p, v in TAX["priorities"].items()} == PRIORITY_RANK


def test_every_intent_routes_to_known_queue():
    for name, spec in TAX["intents"].items():
        assert spec["default_queue"] in TAX["queues"], name
        assert spec["default_priority"] in TAX["priorities"], name


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_expected_queue_consistent_with_intent(case):
    """Expected queue must be the taxonomy default for the expected intent (acceptable_queues must map to an acceptable intent)."""
    e = case.expected
    assert e.queue == TAX["intents"][e.intent]["default_queue"]
    allowed = {TAX["intents"][i]["default_queue"] for i in [e.intent, *e.acceptable_intents]}
    for q in e.acceptable_queues:
        assert q in allowed, f"{case.id}: acceptable queue {q} not reachable from acceptable intents"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_escalation_rules_consistent(case):
    e, t = case.expected, case.ticket
    r = set(e.required_escalation_reasons)
    assert (e.priority == "P1") == ("p1_incident" in r)
    assert (t.customer_id is None) == ("missing_account_id" in r)
    assert (t.customer_id is None) == ("account_id" in e.required_missing_info)
    if e.intent == "cancellation_churn_risk":
        assert "churn_risk" in r
    if "injection" in case.tags:
        assert "prompt_injection_suspected" in r and e.must_not.escalate_false
    if "conflicting_intents" in r:
        sec_queues = {TAX["intents"][i]["default_queue"] for i in e.acceptable_secondary_intents}
        assert sec_queues - {e.queue}, "conflicting_intents requires a secondary intent in a different queue"
    if "low_confidence" in r:
        assert "clear_problem_description" in e.required_missing_info


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_expected_priority_not_forbidden_by_own_must_not(case):
    e = case.expected
    assert e.priority not in e.must_not.priority_in
    assert e.queue not in e.must_not.queue_in
    if e.must_not.escalate_false:
        assert e.escalate


def test_case_customers_exist_in_synthetic_data():
    customers = {c["customer_id"] for c in json.loads((ROOT / "data/synthetic/customers.json").read_text())["records"]}
    for c in CASES:
        if c.ticket.customer_id:
            assert c.ticket.customer_id in customers, c.id


def test_context_modifier_m1_respected():
    """Enterprise + technical/mobile at P3 would violate M1."""
    customers = {c["customer_id"]: c for c in json.loads((ROOT / "data/synthetic/customers.json").read_text())["records"]}
    for c in CASES:
        cust = customers.get(c.ticket.customer_id or "")
        if cust and cust["plan_tier"] == "enterprise" and c.expected.intent in ("technical_issue", "mobile_app_sync"):
            assert PRIORITY_RANK[c.expected.priority] <= 2, c.id
