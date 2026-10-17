"""Streamlit dashboard. Owner: P4.   streamlit run p4_eval_ui/ui/dashboard.py

Works on mocks and on real agents (REAL_DOMAINS in .env / environment). Reads ConsultingReport + audit_trace only.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # allow `streamlit run` from any directory
    sys.path.insert(0, str(REPO_ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from core import llm, registry  # noqa: E402
from p4_eval_ui.evaluation import benchmark  # noqa: E402
from p4_eval_ui.evaluation.explain import explain  # noqa: E402

BRIEF_EXAMPLE = ("Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement "
                 "parts should we order, and what actions should we take to prevent future outages?")
DIAG_EXAMPLE = ("show environment: power supply 1 reports FAILED, power supply 2 OK.\n"
                "show logging: repeated power-supply fault messages and WAN link flaps.\n"
                "show interfaces: input/CRC errors 0. IOS XE 17.9, uptime 12 days.")


def _examples():
    items = json.loads((REPO_ROOT / "core" / "fixtures" / "benchmark_queries.json").read_text())
    pick = {"Q07": "Clinical", "Q11": "SEC", "Q16": "Food security", "Q21": "Cross-domain: tech + SEC", "Q22": "Cross-domain: tech + SEC + CSR"}
    out = [("Brief example: Cisco router", BRIEF_EXAMPLE)]
    out += [(f"{label}", i["query"]) for i in items for qid, label in pick.items() if i["id"] == qid]
    return out


@st.cache_resource(show_spinner=False)
def get_manager():
    return registry.load_manager()


def _set_query(text: str) -> None:
    st.session_state["query"] = text


def render_sidebar() -> None:
    st.sidebar.title("Consulting platform")
    st.sidebar.caption(f"LLM mode: **{llm.llm_mode()}**  ·  REAL_DOMAINS: **{__import__('os').getenv('REAL_DOMAINS', 'auto')}**")
    st.sidebar.markdown("**Try an example**")
    for label, text in _examples():
        st.sidebar.button(label, key=f"ex_{label}", on_click=_set_query, args=(text,), use_container_width=True)
    st.sidebar.button("Add diagnostics example", key="ex_diag", on_click=lambda: st.session_state.update(diagnostics=DIAG_EXAMPLE),
                      use_container_width=True)


def _confidence_bar(score: float, bucket: str) -> None:
    st.progress(min(max(score, 0.0), 1.0), text=f"Confidence {score:.2f}  ({bucket})")


def render_consult(manager) -> None:
    st.text_area("Customer question", key="query", height=100,
                 placeholder="Describe the business problem, e.g. the Cisco router example from the sidebar.")
    st.text_area("Diagnostics / telemetry (optional: paste logs, error codes, versions)", key="diagnostics", height=100)
    if st.button("Get consulting recommendation", type="primary", disabled=manager is None):
        q = (st.session_state.get("query") or "").strip()
        if not q:
            st.warning("Enter a question first.")
        else:
            ctx = {"diagnostics": st.session_state["diagnostics"].strip()} if st.session_state.get("diagnostics", "").strip() else None
            try:
                with st.spinner("Routing to specialist agents..."):
                    st.session_state["report"] = manager.handle(q, ctx)
            except Exception as err:  # noqa: BLE001
                st.error(f"The pipeline failed: {type(err).__name__}: {err}")
    report = st.session_state.get("report")
    if report is None:
        st.info("Ask a question to see the recommendation, evidence and execution trace.")
        return
    view = explain(report)
    if view.banner:
        st.warning(view.banner)
    st.subheader("Executive summary")
    st.write(report.executive_summary)
    cols = st.columns(3)
    cols[0].metric("Domains consulted", ", ".join(d.value for d in report.detected_domains))
    cols[1].metric("Overall confidence", view.overall_confidence)
    cols[2].metric("Recommendations", len(view.recommendations))
    if report.cross_domain_synthesis:
        st.subheader("Cross-domain synthesis")
        st.write(report.cross_domain_synthesis)
    st.subheader("Recommendations")
    if not view.recommendations:
        st.caption("No recommendations yet.")
    for r in view.recommendations:
        with st.container(border=True):
            st.markdown(f"**{r.title}**  ·  `{r.category}`  ·  {r.domain or 'n/a'}")
            _confidence_bar(r.confidence_score, r.confidence_bucket)
            st.write("**Why:** " + r.why)
            if r.evidence_sources:
                st.caption(f"Evidence ({r.evidence_count}): " + "; ".join(r.evidence_sources))
            for c in r.caveats:
                st.caption("⚠ " + c)
    st.subheader("Next steps")
    for i, s in enumerate(report.next_steps, 1):
        st.markdown(f"{i}. {s}")
    st.subheader("How impact will be measured (KPIs)")
    for k in report.measuring_impact_kpis:
        st.markdown(f"- {k}")
    if view.what_would_change_this_answer:
        with st.expander("What would change this answer"):
            for w in view.what_would_change_this_answer:
                st.markdown(f"- {w}")


def render_trace() -> None:
    report = st.session_state.get("report")
    if report is None:
        st.info("Run a consultation to see the execution trace.")
        return
    t = report.audit_trace
    c = st.columns(3)
    c[0].metric("Total latency (ms)", t.get("total_ms", "n/a"))
    c[1].metric("LLM mode", t.get("mode", "n/a"))
    c[2].metric("Fallbacks used", len(t.get("fallbacks_used", [])))
    st.subheader("1. Routing decision")
    routing = t.get("routing", {})
    st.write(f"Detected: **{', '.join(str(d) for d in routing.get('domains', []))}**  ·  cross-domain: "
             f"**{routing.get('is_cross_domain')}**  ·  confidence: **{routing.get('confidence')}**")
    if routing.get("rationale"):
        st.caption(routing["rationale"])
    st.json(routing.get("sub_queries", {}), expanded=False)
    st.subheader("2. Parallel agent execution")
    rows = [{"domain": d, **a} for d, a in t.get("agents", {}).items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if any(r.get("real_or_mock") == "mock" for r in rows):
            st.caption("Rows marked `mock` are placeholder agents (the real ones are not wired in yet).")
    st.subheader("3. Synthesis")
    st.caption(f"Consolidated {len(report.consolidated_recommendations)} recommendation(s) from {len(report.domain_findings)} domain(s).")
    with st.expander("Raw audit trace"):
        st.json(t)


def render_evidence() -> None:
    report = st.session_state.get("report")
    if report is None:
        st.info("Run a consultation to see the evidence.")
        return
    for domain, resp in report.domain_findings.items():
        with st.container(border=True):
            st.markdown(f"### {domain}  ·  `{resp.status}`  ·  uncertainty **{resp.uncertainty_level}**")
            st.write(resp.findings_summary)
            if resp.missing_diagnostics_needed:
                st.warning("Missing information: " + "; ".join(resp.missing_diagnostics_needed))
            st.caption(f"{len(resp.citations)} citation(s)")
            for c in resp.citations:
                where = c.source_doc + (f", p.{c.page}" if c.page else "") + (f", {c.section}" if c.section else "")
                with st.expander(where):
                    st.write(f"“{c.snippet}”")


def _pct(v) -> str:
    return "n/a" if v is None else f"{100 * v:.1f}%"


def render_evaluation(manager) -> None:
    path = benchmark.EVAL_DIR / "scorecard.json"
    c = st.columns([1, 3])
    if c[0].button("Run benchmark now", disabled=manager is None):
        with st.spinner("Running benchmark queries..."):
            benchmark.write_scorecard(benchmark.run_benchmark(manager))
    if not path.exists():
        st.info("No scorecard yet. Click **Run benchmark now** or run `make eval`.")
        return
    res = json.loads(path.read_text())
    c[1].caption(f"Generated {res['generated_at']}  ·  {res['n_queries']} queries  ·  llm_mode={res['llm_mode']}")
    if any(s != "real" for s in res.get("agents_real", {}).values()):
        st.warning("Some agents in this run were mocks, so retrieval, faithfulness and recommendation numbers are not meaningful yet.")
    m = st.columns(4)
    m[0].metric("Routing accuracy", _pct(res["routing_accuracy"]))
    m[1].metric(f"Retrieval hit-rate@{res['k']}", _pct(res["retrieval_hit_rate"]))
    m[2].metric("Recommendation NDCG@3", _pct(res["recommendation_ndcg_at_3"]))
    m[3].metric("Faithfulness", _pct(res["faithfulness"]))
    m = st.columns(4)
    m[0].metric("Diagnostic-gate compliance", _pct(res["diagnostic_gate_compliance"]))
    m[1].metric("Out-of-scope handled", _pct(res["out_of_scope_low_confidence_rate"]))
    m[2].metric("Latency p50 (ms)", res["latency_ms_p50"])
    m[3].metric("Errors", res["errors"])

    st.subheader("Retrieval hit-rate by domain")
    df = pd.DataFrame({"domain": list(res["retrieval_hit_rate_by_domain"]), "hit_rate": [v if v is not None else 0 for v in res["retrieval_hit_rate_by_domain"].values()]})
    st.altair_chart(alt.Chart(df).mark_bar().encode(x="domain", y=alt.Y("hit_rate", scale=alt.Scale(domain=[0, 1])), tooltip=["domain", "hit_rate"]), use_container_width=True)

    st.subheader("Routing: per-domain precision / recall")
    st.dataframe(pd.DataFrame(res["per_domain_routing"]).T, use_container_width=True)
    st.subheader("Routing: gold domain (rows) vs predicted domain (columns), query counts")
    cm = pd.DataFrame(res["confusion_matrix"]).T
    long = cm.reset_index().melt(id_vars="index", var_name="predicted", value_name="queries").rename(columns={"index": "gold"})
    heat = alt.Chart(long).mark_rect().encode(x="predicted:N", y="gold:N", color=alt.Color("queries:Q", scale=alt.Scale(scheme="blues")), tooltip=["gold", "predicted", "queries"])
    st.altair_chart(heat + heat.mark_text().encode(text="queries:Q", color=alt.value("black")), use_container_width=True)

    st.subheader("Confidence calibration (top recommendation vs gold relevance)")
    st.dataframe(pd.DataFrame(res["calibration"]), use_container_width=True, hide_index=True)
    st.caption(f"Gold judgments on {res['gold_coverage']['queries_with_gold']} queries; "
               f"{res['gold_coverage']['skipped_placeholder_gold']} skipped because their gold items are still placeholders.")
    st.subheader("Per-query results")
    pq = pd.DataFrame(res["per_query"])
    keep = [c for c in ["id", "query", "expected_domains", "predicted_domains", "routing_exact", "ndcg_at_3", "faithfulness", "latency_ms", "error"] if c in pq]
    st.dataframe(pq[keep], use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="AI Consulting Platform", page_icon="📊", layout="wide")
    st.title("AI Management Consulting Platform")
    render_sidebar()
    manager = get_manager()
    if manager is None:
        st.error("The Manager Agent (P1) is not built yet, so the platform cannot run.")
    tabs = st.tabs(["Consult", "Agent trace", "Evidence", "Evaluation"])
    with tabs[0]:
        render_consult(manager)
    with tabs[1]:
        render_trace()
    with tabs[2]:
        render_evidence()
    with tabs[3]:
        render_evaluation(manager)


main()
