"""Quality: how well the assistant does on the labelled test tickets (read from eval/results/day4)."""
import json

import streamlit as st

from src.taxonomy import ROOT

BASE = ROOT / "eval" / "results" / "day4"
SET_TEXT = {"dev": "Development set", "holdout": "Held-out set (never used for tuning)",
            "adversarial": "Break-it set (tricky and hostile tickets)"}
SYSTEM_TEXT = {"pipeline": "Triage assistant", "keyword_baseline": "Keyword rules only", "naive_llm_baseline": "Plain AI prompt"}


@st.cache_data(ttl=60)
def load(label: str) -> dict[str, dict]:
    out = {}
    for name in SET_TEXT:
        # The held-out checkpoint is run separately and saved as "<label>-holdout".
        for folder in (label, f"{label}-{name}"):
            p = BASE / folder / f"summary_{name}.json"
            if p.exists():
                out[name] = json.loads(p.read_text(encoding="utf-8"))
                break
    return out


def spread(a: dict, fmt: str) -> str:
    return format(a["max"], fmt) if a["min"] == a["max"] else f"{format(a['min'], fmt)}–{format(a['max'], fmt)}"


def pct(a: dict | None) -> str:
    return "n/a" if not a else f"{a['mean']:.0%}"


labels = sorted((d.name for d in BASE.iterdir() if d.is_dir() and any(d.glob("summary_*.json"))
                 and not d.name.endswith(tuple(f"-{s}" for s in SET_TEXT))), reverse=True) \
    if BASE.exists() else []
if not labels:
    st.info("Run `python -m scripts.run_eval --label v1 --sets dev,adversarial --runs 3` to create results.",
            title="No evaluation results yet", icon=":material/science:")
    st.stop()

st.caption("The assistant is tested on labelled **synthetic** tickets where the right answer is known. "
           "A ticket only passes if category, priority, team, escalation and safety rules are all right.")
label = st.segmented_control("Version", labels, default=labels[0], required=True, key="quality_version") \
    if len(labels) > 1 else labels[0]
data = load(label)

for name, d in data.items():
    pipe = d["systems"]["pipeline"]
    st.subheader(SET_TEXT[name], anchor=False)
    st.caption(f"{len(d['case_passes'])} tickets × {d['runs']} runs. Range across runs for fully-correct tickets: "
               f"{spread(pipe['case_pass_rate'], '.0%')}.")
    with st.grid(4):
        st.metric("Tickets fully correct", pct(pipe["case_pass_rate"]), border=True,
                  help=f"Average of {d['runs']} runs. Range across runs: {spread(pipe['case_pass_rate'], '.0%')}.")
        st.metric("Dangerous mistakes per run", spread(pipe["critical_failure_cases"], ".0f"), border=True,
                  help="Lowest to highest across the runs. A dangerous mistake is a missed escalation, an "
                       "under-prioritised P1/P2, a forbidden outcome (such as a followed hidden instruction), or a "
                       "repeated secret.")
        st.metric("Escalations caught", pct(pipe["escalation_recall"]), border=True,
                  help="Of the tickets that needed a lead, how many the assistant flagged.")
        st.metric("Typical wait per ticket", f"{pipe['latency_ms_median']['mean'] / 1000:.1f} s", border=True)

    if len(d["systems"]) > 1:
        chart = [{"System": SYSTEM_TEXT.get(s, s), "Tickets fully correct (%)": round(100 * v["case_pass_rate"]["mean"])}
                 for s, v in d["systems"].items() if v.get("case_pass_rate")]
        st.bar_chart(chart, x="System", y="Tickets fully correct (%)", horizontal=True, height=200, color="#3B82F6")

    with st.expander(f"Ticket by ticket ({len(d['case_passes'])})", icon=":material/checklist:"):
        st.dataframe([{"Case": cid, "Passed": f"{n}/{d['runs']}", "Stable": n in (0, d["runs"]),
                       "Why it failed": (d["case_failures"].get(cid) or [""])[0]} for cid, n in d["case_passes"].items()],
                     hide_index=True, column_config={"Stable": st.column_config.CheckboxColumn(
                         help="Same result on every run. Unticked means the AI gave different answers on different runs.")},
                     alt=f"Per-ticket results for the {SET_TEXT[name]}")

st.caption(f"Source: `eval/results/day4/{label}/`. Reproduce with `python -m scripts.run_eval`.")
