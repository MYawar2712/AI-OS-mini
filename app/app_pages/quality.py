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
        p = BASE / label / f"summary_{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def pct(a: dict | None) -> str:
    return "n/a" if not a else f"{a['mean']:.0%}"


labels = sorted((d.name for d in BASE.iterdir() if d.is_dir() and any(d.glob("summary_*.json"))), reverse=True) \
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
    with st.grid(4):
        rng = "" if pipe["case_pass_rate"]["min"] == pipe["case_pass_rate"]["max"] else \
            f"{pipe['case_pass_rate']['min']:.0%}–{pipe['case_pass_rate']['max']:.0%} across {d['runs']} runs"
        st.metric("Tickets fully correct", pct(pipe["case_pass_rate"]), rng or f"{d['runs']} run(s)", delta_color="off",
                  border=True)
        st.metric("Dangerous mistakes", f"{pipe['critical_failure_cases']['max']:.0f}", border=True,
                  help="Worst run. A dangerous mistake is a missed escalation, an under-prioritised P1/P2, a followed "
                       "hidden instruction, or a repeated secret.")
        st.metric("Escalations caught", pct(pipe["escalation_recall"]), border=True,
                  help="Of the tickets that needed a lead, how many the assistant flagged.")
        st.metric("Typical wait per ticket", f"{pipe['latency_ms_median']['mean'] / 1000:.1f} s", border=True)

    if len(d["systems"]) > 1:
        chart = [{"System": SYSTEM_TEXT.get(s, s), "Tickets fully correct (%)": round(100 * v["case_pass_rate"]["mean"])}
                 for s, v in d["systems"].items() if v.get("case_pass_rate")]
        st.bar_chart(chart, x="System", y="Tickets fully correct (%)", horizontal=True, height=200)

    with st.expander(f"Ticket by ticket ({len(d['case_passes'])})", icon=":material/checklist:"):
        st.dataframe([{"Case": cid, "Passed": f"{n}/{d['runs']}", "Stable": n in (0, d["runs"]),
                       "Why it failed": (d["case_failures"].get(cid) or [""])[0]} for cid, n in d["case_passes"].items()],
                     hide_index=True, column_config={"Stable": st.column_config.CheckboxColumn(
                         help="Same result on every run. Unticked means the AI gave different answers on different runs.")},
                     alt=f"Per-ticket results for the {SET_TEXT[name]}")

st.caption(f"Source: `eval/results/day4/{label}/`. Reproduce with `python -m scripts.run_eval`.")
