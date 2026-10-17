"""Streamlit dashboard. Owner: P4.   streamlit run p4_eval_ui/ui/dashboard.py

Works on mocks and on real agents (REAL_DOMAINS in .env / environment). Reads ConsultingReport + audit_trace only.
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # allow `streamlit run` from any directory
    sys.path.insert(0, str(REPO_ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from core import llm, registry  # noqa: E402
from p4_eval_ui.evaluation import benchmark  # noqa: E402
from p4_eval_ui.evaluation.explain import explain  # noqa: E402
from p4_eval_ui.ui import theme  # noqa: E402
from p4_eval_ui.ui.flow import build_flow_html  # noqa: E402

esc = theme.esc
FLOW_HEIGHT = 540
BRIEF_EXAMPLE = ("Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement "
                 "parts should we order, and what actions should we take to prevent future outages?")
DIAG_EXAMPLE = ("show environment: power supply 1 reports FAILED, power supply 2 OK.\n"
                "show logging: repeated power-supply fault messages and WAN link flaps.\n"
                "show interfaces: input/CRC errors 0. IOS XE 17.9, uptime 12 days.")


def _examples():
    items = json.loads((REPO_ROOT / "core" / "fixtures" / "benchmark_queries.json").read_text())
    pick = {"Q07": "Clinical: pathology scanner", "Q11": "SEC: Cisco risk factors", "Q16": "Food security 2023",
            "Q21": "Cross-domain: tech + SEC", "Q22": "Cross-domain: tech + SEC + CSR"}
    out = [("Brief example: Cisco router", BRIEF_EXAMPLE)]
    out += [(label, i["query"]) for i in items for qid, label in pick.items() if i["id"] == qid]
    return out


@st.cache_resource(show_spinner=False)
def get_manager():
    return registry.load_manager()


def _set_query(text: str) -> None:
    st.session_state["query"] = text


def render_sidebar() -> None:
    st.sidebar.markdown("### Try an example")
    for label, text in _examples():
        st.sidebar.button(label, key=f"ex_{label}", on_click=_set_query, args=(text,), use_container_width=True)
    st.sidebar.markdown("---")
    st.sidebar.button("Add diagnostics example", key="ex_diag", on_click=lambda: st.session_state.update(diagnostics=DIAG_EXAMPLE),
                      use_container_width=True)
    st.sidebar.caption("Tip: run the Cisco example without logs first, then add the diagnostics and run again.")


def _is_dark():
    try:
        return st.context.theme.type == "dark"
    except Exception:  # noqa: BLE001 - older Streamlit or unknown theme: let the iframe follow the browser
        return None


def show_flow(trace) -> None:
    components.html(build_flow_html(trace, dark=_is_dark()), height=FLOW_HEIGHT, scrolling=False)


def render_consult(manager) -> None:
    with st.container(border=True):
        st.text_area("Customer question", key="query", height=96,
                     placeholder="Describe the business problem, e.g. the Cisco router example from the sidebar.")
        st.text_area("Diagnostics / telemetry (optional: paste logs, error codes, versions)", key="diagnostics", height=96)
        run = st.button("Get consulting recommendation", type="primary", disabled=manager is None)
    if run:
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
        st.subheader("How it works")
        show_flow(None)
        return
    view = explain(report)
    if view.banner:
        st.warning(view.banner)
    st.subheader("Executive summary")
    st.markdown(f'<div class="summary">{esc(report.executive_summary)}</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    cols[0].metric("Domains consulted", len(report.detected_domains))
    prov = view.overall_confidence.endswith("(provisional)")
    cols[1].metric("Overall confidence" + (" (provisional)" if prov else ""), view.overall_confidence.replace(" (provisional)", ""))
    cols[2].metric("Recommendations", len(view.recommendations))
    st.markdown(" ".join(theme.domain_pill(d.value) for d in report.detected_domains), unsafe_allow_html=True)

    st.subheader("How your question travelled")
    show_flow(report.audit_trace)

    if report.cross_domain_synthesis:
        st.subheader("Cross-domain synthesis")
        st.markdown(f'<div class="card">{esc(report.cross_domain_synthesis)}</div>', unsafe_allow_html=True)
    st.subheader("Recommendations")
    if not view.recommendations:
        st.caption("No recommendations yet.")
    for r in view.recommendations:
        caveats = "".join(f'<div class="caveat">⚠ {esc(c)}</div>' for c in r.caveats)
        ev = f'<div class="meta">Evidence ({r.evidence_count}): {esc("; ".join(r.evidence_sources))}</div>' if r.evidence_sources else ""
        st.markdown(
            f'<div class="card"><div class="rec-top"><div><div class="rec-title">{esc(r.title)}</div>'
            f'<div class="meta">{esc(r.category)}</div></div><div>{theme.domain_pill(r.domain) if r.domain else ""}</div></div>'
            f'{theme.conf_bar(r.confidence_score, r.confidence_bucket)}'
            f'<div class="why"><b>Why:</b> {esc(r.why)}</div>{ev}{caveats}</div>',
            unsafe_allow_html=True)
    st.subheader("Next steps")
    for i, s in enumerate(report.next_steps, 1):
        st.markdown(f'<div class="step"><div class="n">{i}</div><div>{esc(s)}</div></div>', unsafe_allow_html=True)
    st.subheader("How impact will be measured")
    st.markdown("".join(f'<span class="kpi">{esc(k)}</span>' for k in report.measuring_impact_kpis), unsafe_allow_html=True)
    if view.what_would_change_this_answer:
        with st.expander("What would change this answer"):
            for w in view.what_would_change_this_answer:
                st.markdown(f"- {w}")


def render_trace() -> None:
    report = st.session_state.get("report")
    if report is None:
        st.subheader("Architecture")
        show_flow(None)
        st.info("Run a consultation to see the real path, latency and status of each agent.")
        return
    t = report.audit_trace
    c = st.columns(3)
    c[0].metric("Total latency (ms)", t.get("total_ms", "n/a"))
    c[1].metric("LLM mode", t.get("mode", "n/a"))
    c[2].metric("Fallbacks used", len(t.get("fallbacks_used", [])))
    show_flow(t)
    routing = t.get("routing", {})
    st.subheader("1. Routing decision")
    st.markdown(f'Detected: {" ".join(theme.domain_pill(str(getattr(d, "value", d))) for d in routing.get("domains", []))}'
                f' &nbsp; cross-domain: **{routing.get("is_cross_domain")}** &nbsp; confidence: **{routing.get("confidence")}**',
                unsafe_allow_html=True)
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
        missing = (f'<div class="caveat">⚠ Missing information: {esc("; ".join(resp.missing_diagnostics_needed))}</div>'
                   if resp.missing_diagnostics_needed else "")
        st.markdown(
            f'<div class="card"><div class="rec-top"><div class="rec-title">{esc(theme.DOMAIN_LABEL.get(domain, domain))}</div>'
            f'<div>{theme.status_pill(resp.status)} {theme.pill("uncertainty " + resp.uncertainty_level, theme.BUCKET_COLOR["Low"] if resp.uncertainty_level == "HIGH" else theme.BUCKET_COLOR["Medium"] if resp.uncertainty_level == "MEDIUM" else theme.BUCKET_COLOR["High"])}</div></div>'
            f'<div class="why">{esc(resp.findings_summary)}</div>{missing}'
            f'<div class="meta">{len(resp.citations)} citation(s)</div></div>', unsafe_allow_html=True)
        for c in resp.citations:
            where = c.source_doc + (f", p.{c.page}" if c.page else "") + (f", {c.section}" if c.section else "")
            with st.expander(where):
                st.markdown(f'<div class="cite">“{esc(c.snippet)}”</div>', unsafe_allow_html=True)


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
    df = pd.DataFrame({"domain": [theme.DOMAIN_LABEL.get(d, d) for d in res["retrieval_hit_rate_by_domain"]],
                       "hit_rate": [v if v is not None else 0 for v in res["retrieval_hit_rate_by_domain"].values()]})
    st.altair_chart(alt.Chart(df).mark_bar(cornerRadiusEnd=6).encode(
        x=alt.X("domain", sort=None, title=None), y=alt.Y("hit_rate", scale=alt.Scale(domain=[0, 1]), title="hit-rate"),
        color=alt.Color("domain", legend=None, scale=alt.Scale(range=list(theme.DOMAIN_COLOR.values()))), tooltip=["domain", "hit_rate"]),
        use_container_width=True)

    st.subheader("Routing: per-domain precision / recall")
    st.dataframe(pd.DataFrame(res["per_domain_routing"]).T, use_container_width=True)
    st.subheader("Routing: gold domain (rows) vs predicted domain (columns), query counts")
    cm = pd.DataFrame(res["confusion_matrix"]).T
    long = cm.reset_index().melt(id_vars="index", var_name="predicted", value_name="queries").rename(columns={"index": "gold"})
    heat = alt.Chart(long).mark_rect(cornerRadius=4).encode(x="predicted:N", y="gold:N", color=alt.Color("queries:Q", scale=alt.Scale(scheme="blues")),
                                                           tooltip=["gold", "predicted", "queries"])
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
    theme.inject_css()
    theme.hero(llm.llm_mode(), os.getenv("REAL_DOMAINS", "auto"))
    render_sidebar()
    manager = get_manager()
    demo = st.query_params.get("demo")  # ?demo=cisco or ?demo=cisco-diag preloads a run (handy for demos and screenshots)
    if demo and manager is not None and "report" not in st.session_state:
        st.session_state["query"] = BRIEF_EXAMPLE
        st.session_state["diagnostics"] = DIAG_EXAMPLE if demo == "cisco-diag" else ""
        st.session_state["report"] = manager.handle(BRIEF_EXAMPLE, {"diagnostics": DIAG_EXAMPLE} if demo == "cisco-diag" else None)
    if manager is None:
        st.error("The Manager Agent (P1) is not built yet, so the platform cannot run.")
    tabs = st.tabs(["Consult", "Request flow", "Evidence", "Evaluation"])
    with tabs[0]:
        render_consult(manager)
    with tabs[1]:
        render_trace()
    with tabs[2]:
        render_evidence()
    with tabs[3]:
        render_evaluation(manager)


main()
