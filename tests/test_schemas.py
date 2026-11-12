import json

import pytest
from pydantic import ValidationError

from src.schemas import TriageResult, export_json_schemas, load_test_cases
from src.taxonomy import ROOT

CASES = load_test_cases(ROOT / "eval" / "test_cases.jsonl")


def test_exactly_twelve_cases_with_required_mix():
    assert len(CASES) == 12
    cats = [c.category for c in CASES]
    assert (cats.count("representative"), cats.count("edge"), cats.count("failure")) == (5, 4, 3)


HOLDOUT = load_test_cases(ROOT / "eval" / "test_cases_holdout.jsonl")


def test_ids_unique():
    assert len({c.id for c in CASES}) == 12
    assert len({c.ticket.ticket_id for c in CASES}) == 12


def test_holdout_set_mix_and_ids_disjoint_from_dev():
    cats = [c.category for c in HOLDOUT]
    assert len(HOLDOUT) == 12 and (cats.count("representative"), cats.count("edge"), cats.count("failure")) == (5, 4, 3)
    all_ids = [c.id for c in CASES + HOLDOUT] + [c.ticket.ticket_id for c in CASES + HOLDOUT]
    assert len(all_ids) == len(set(all_ids))
    assert all(c.ticket.synthetic and "holdout" in c.tags for c in HOLDOUT)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case_is_synthetic_and_valid(case):
    assert case.ticket.synthetic is True
    assert case.risk_tested.strip()


def _valid(**over):
    base = dict(ticket_id="T-1", intent="billing_invoice", priority="P3", queue="billing", escalate=False,
                summary="s", suggested_next_action="a", confidence=0.8, rationale="r")
    base.update(over)
    return base


def test_triage_result_accepts_valid():
    TriageResult.model_validate(_valid())


@pytest.mark.parametrize("bad", [
    {"priority": "P5"},
    {"intent": "refund_request"},
    {"confidence": 1.5},
    {"escalate": True},                                   # escalate without reason
    {"escalation_reasons": ["churn_risk"]},              # reason without escalate
    {"secondary_intent": "billing_invoice"},             # same as primary
    {"unexpected_field": 1},                             # extra=forbid
])
def test_triage_result_rejects_invalid(bad):
    with pytest.raises(ValidationError):
        TriageResult.model_validate(_valid(**bad))


def test_json_schema_export(tmp_path):
    paths = export_json_schemas(tmp_path)
    assert {p.name for p in paths} == {"inbound_ticket.schema.json", "triage_result.schema.json", "test_case.schema.json"}
    schema = json.loads((tmp_path / "triage_result.schema.json").read_text())
    assert "priority" in schema["required"]
