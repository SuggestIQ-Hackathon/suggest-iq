"""Streamlit dashboard. Owner: P4.   python -m p4_eval_ui.ui.launch   (light theme; or: streamlit run p4_eval_ui/ui/dashboard.py)

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
FLOW_HEIGHT = 560
BRIEF_EXAMPLE = ("Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement "
                 "parts should we order, and what actions should we take to prevent future outages?")
DIAG_EXAMPLE = ("show environment: power supply 1 reports FAILED, power supply 2 OK.\n"
                "show logging: repeated power-supply fault messages and WAN link flaps.\n"
                "show interfaces: input/CRC errors 0. IOS XE 17.9, uptime 12 days.")
# metric -> (label, target as a fraction, key in the scorecard). Targets are our own goals for the demo, not industry standards.
TARGETS = {
    "routing_accuracy": ("Routing accuracy", 0.85),
    "retrieval_hit_rate": ("Retrieval hit-rate", 0.70),
    "recommendation_ndcg_at_3": ("Recommendation NDCG@3", 0.60),
    "faithfulness": ("Faithfulness", 0.80),
    "diagnostic_gate_compliance": ("Diagnostic-gate compliance", 1.00),
    "out_of_scope_low_confidence_rate": ("Out-of-scope handled", 0.90),
}
SUMMARY_PREFIX = "CRITICAL DIAGNOSTIC PREREQUISITE"


def _examples():
    items = json.loads((REPO_ROOT / "core" / "fixtures" / "benchmark_queries.json").read_text())
    pick = {"Q07": ("Clinical: pathology scanner", False), "Q11": ("SEC: Cisco risk factors", False), "Q16": ("Food security 2023", False),
            "Q21": ("Tech + SEC", True), "Q22": ("Tech + SEC + CSR", True)}
    out = [("Cisco router (from the brief)", BRIEF_EXAMPLE, False)]
    out += [(label, i["query"], cross) for i in items for qid, (label, cross) in pick.items() if i["id"] == qid]
    return out


@st.cache_resource(show_spinner=False)
def get_manager():
    return registry.load_manager()


def _set_query(text: str) -> None:
    st.session_state["query"] = text


def trim_summary(summary: str, has_banner: bool) -> str:
    """The banner already lists the missing diagnostics, so drop the synthesizer's repeated first sentence."""
    if has_banner and summary.startswith(SUMMARY_PREFIX):
        parts = summary.split(". ", 1)
        return parts[1] if len(parts) > 1 else summary
    return summary


def render_sidebar() -> None:
    st.sidebar.markdown("### Try an example")
    ex = _examples()
    st.sidebar.markdown('<div class="group-h">Single domain</div>', unsafe_allow_html=True)
    for label, text, cross in ex:
        if not cross:
            st.sidebar.button(label, key=f"ex_{label}", on_click=_set_query, args=(text,), width="stretch")
    st.sidebar.markdown('<div class="group-h">Cross-domain (several agents)</div>', unsafe_allow_html=True)
    for label, text, cross in ex:
        if cross:
            st.sidebar.button(label, key=f"ex_{label}", on_click=_set_query, args=(text,), width="stretch")
    st.sidebar.markdown("---")
    st.sidebar.button("Add diagnostics example", key="ex_diag", on_click=lambda: st.session_state.update(diagnostics=DIAG_EXAMPLE), width="stretch")
    st.sidebar.caption("Tip: run the router example without logs first. The platform will ask for what it needs; paste it and run again.")


def _is_dark():
    """True/False when the Streamlit theme is known, None when it follows the browser (then the iframe uses prefers-color-scheme)."""
    base = st.get_option("theme.base")  # set explicitly by the launcher (light) or by the user's config
    if base in ("light", "dark"):
        return base == "dark"
    try:
        return st.context.theme.type == "dark"
    except Exception:  # noqa: BLE001 - older Streamlit or unknown theme
        return None


def show_flow(trace) -> None:
    components.html(build_flow_html(trace, dark=_is_dark()), height=FLOW_HEIGHT, scrolling=False)


def _run(manager, query: str, diagnostics: str) -> None:
    ctx = {"diagnostics": diagnostics.strip()} if diagnostics and diagnostics.strip() else None
    try:
        with st.spinner("Routing to specialist agents..."):
            st.session_state["report"] = manager.handle(query, ctx)
            st.session_state["report_had_diagnostics"] = bool(ctx)
    except Exception as err:  # noqa: BLE001
        st.error(f"The pipeline failed: {type(err).__name__}: {err}")


def render_needs_info(manager, report, view) -> None:
    missing = []
    for resp in report.domain_findings.values():
        for m in resp.missing_diagnostics_needed:
            if m not in missing:
                missing.append(m)
    items = "".join(f"<li>{esc(m)}</li>" for m in missing)
    st.markdown(f'<div class="need"><h4>More information needed before parts can be recommended</h4>'
               f'<div class="meta">The answer below is provisional. Please provide:</div><ul>{items}</ul></div>', unsafe_allow_html=True)
    st.text_area("Paste the requested output here", key="followup_diag", height=110, label_visibility="collapsed",
                 placeholder="Paste logs, error counters, versions...")
    c = st.columns([2.2, 1.6, 3])
    if c[0].button("Add diagnostics and re-run", type="primary", disabled=manager is None, key="rerun"):
        _run(manager, report.query, st.session_state.get("followup_diag", ""))
        st.rerun()
    c[1].button("Use example logs", key="use_example_logs", on_click=lambda: st.session_state.update(followup_diag=DIAG_EXAMPLE))


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
            _run(manager, q, st.session_state.get("diagnostics", ""))
    report = st.session_state.get("report")
    if report is None:
        st.subheader("How it works")
        show_flow(None)
        return
    view = explain(report)
    info_req = any(r.status == "INFORMATION_REQUEST" for r in report.domain_findings.values())
    st.markdown(theme.path_ribbon(report.audit_trace), unsafe_allow_html=True)
    if info_req:
        render_needs_info(manager, report, view)

    st.subheader("Executive summary")
    st.markdown(f'<div class="summary">{esc(trim_summary(report.executive_summary, info_req))}</div>', unsafe_allow_html=True)
    n_cites = sum(len(r.citations) for r in report.domain_findings.values())
    statuses = [r.status for r in report.domain_findings.values()]
    prov = view.overall_confidence.endswith("(provisional)")
    cols = st.columns(4)
    with cols[0]:
        theme.tile("Agents consulted", str(len(report.detected_domains)), ", ".join(theme.DOMAIN_LABEL.get(d.value, d.value) for d in report.detected_domains))
    with cols[1]:
        theme.tile("Answer status", "Provisional" if info_req else "Complete",
                   f"{sum(s == 'INFORMATION_REQUEST' for s in statuses)} needs info · {sum(s != 'INFORMATION_REQUEST' for s in statuses)} ready",
                   "#ea580c" if info_req else "#16a34a")
    with cols[2]:
        theme.tile("Overall confidence", view.overall_confidence.replace(" (provisional)", ""), "provisional" if prov else "from recommendations",
                   theme.BUCKET_COLOR.get(view.overall_confidence.split(" ")[0], "#6b7280"))
    with cols[3]:
        theme.tile("Evidence (citations)", str(n_cites), "verbatim snippets with source and page")

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
            f'<div class="why"><b>Why:</b> {esc(r.why)}</div>{ev}{caveats}</div>', unsafe_allow_html=True)
    st.subheader("Next steps")
    for i, s in enumerate(report.next_steps, 1):
        st.markdown(f'<div class="step"><div class="n">{i}</div><div>{esc(s)}</div></div>', unsafe_allow_html=True)
    st.subheader("How impact will be measured")
    st.markdown("".join(f'<span class="kpi">{esc(k)}</span>' for k in report.measuring_impact_kpis), unsafe_allow_html=True)
    if view.what_would_change_this_answer:
        with st.expander("What would change this answer"):
            for w in view.what_would_change_this_answer:
                st.markdown(f"- {w}")
    with st.expander("How your question travelled (animated agent flow)"):
        show_flow(report.audit_trace)


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
                f' &nbsp; cross-domain: **{routing.get("is_cross_domain")}** &nbsp; confidence: **{routing.get("confidence")}**', unsafe_allow_html=True)
    if routing.get("rationale"):
        st.caption(routing["rationale"])
    st.json(routing.get("sub_queries", {}), expanded=False)
    st.subheader("2. Parallel agent execution")
    rows = [{"domain": d, **a} for d, a in t.get("agents", {}).items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
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
    terms = theme.query_terms(report.query)
    st.caption("Highlighted words come from your question. Snippets are verbatim from the source documents.")
    for domain, resp in report.domain_findings.items():
        missing = (f'<div class="caveat">⚠ Missing information: {esc("; ".join(resp.missing_diagnostics_needed))}</div>'
                   if resp.missing_diagnostics_needed else "")
        unc = theme.BUCKET_COLOR["Low"] if resp.uncertainty_level == "HIGH" else theme.BUCKET_COLOR["Medium"] if resp.uncertainty_level == "MEDIUM" else theme.BUCKET_COLOR["High"]
        st.markdown(
            f'<div class="card"><div class="rec-top"><div class="rec-title">{esc(theme.DOMAIN_LABEL.get(domain, domain))}</div>'
            f'<div>{theme.status_pill(resp.status)} {theme.pill("uncertainty " + resp.uncertainty_level, unc)}</div></div>'
            f'<div class="why">{esc(resp.findings_summary)}</div>{missing}<div class="meta">{len(resp.citations)} citation(s)</div></div>', unsafe_allow_html=True)
        by_doc = {}
        for c in resp.citations:
            by_doc.setdefault(c.source_doc, []).append(c)
        for doc, cites in by_doc.items():
            with st.expander(f"{doc}  ·  {len(cites)} snippet(s)"):
                for c in cites:
                    where = " · ".join(x for x in [f"p.{c.page}" if c.page else "", c.section or ""] if x)
                    st.markdown(f'<div class="cite"><div class="meta">{esc(where)}</div>“{theme.highlight(c.snippet, terms)}”</div>', unsafe_allow_html=True)


def _pct(v) -> str:
    return "n/a" if v is None else f"{100 * v:.1f}%"


def _history():
    p = benchmark.EVAL_DIR / "history.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _status_color(value, target):
    if value is None:
        return "#6b7280"
    return "#16a34a" if value >= target else "#d97706" if value >= 0.8 * target else "#dc2626"


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
    hist = _history()
    prev = hist[-2] if len(hist) >= 2 else None
    c[1].caption(f"Generated {res['generated_at']}  ·  {res['n_queries']} queries  ·  llm_mode={res['llm_mode']}  ·  green = at target, amber = within 20%, red = below")
    if any(s != "real" for s in res.get("agents_real", {}).values()):
        st.warning("Some agents in this run were mocks, so retrieval, faithfulness and recommendation numbers are not meaningful yet.")
    keys = list(TARGETS)
    for row in (keys[:3], keys[3:]):
        cols = st.columns(3)
        for col, k in zip(cols, row):
            label, target = TARGETS[k]
            v = res.get(k)
            delta = ""
            if prev and prev.get(k) is not None and v is not None:
                d = 100 * (v - prev[k])
                delta = f" · {'+' if d >= 0 else ''}{d:.1f} pts vs previous run"
            with col:
                theme.tile(label, _pct(v), f"target ≥ {100 * target:.0f}%{delta}", _status_color(v, target))
    m = st.columns(3)
    with m[0]:
        theme.tile("Latency p50 (ms)", str(res["latency_ms_p50"]), "p95 " + str(res["latency_ms_p95"]))
    with m[1]:
        theme.tile("Errors", str(res["errors"]), "pipeline crashes during the run", "#16a34a" if res["errors"] == 0 else "#dc2626")
    with m[2]:
        cov = res["gold_coverage"]
        theme.tile("Gold judgments", f"{cov['queries_with_gold']} queries", f"{cov['skipped_placeholder_gold']} skipped (placeholder items)")

    if len(hist) >= 2:
        st.subheader("Trend across runs")
        df = pd.DataFrame(hist)
        df["run"] = range(1, len(df) + 1)
        long = df.melt(id_vars=["run"], value_vars=[k for k in keys if k in df], var_name="metric", value_name="score").dropna()
        long["metric"] = long["metric"].map(lambda k: TARGETS[k][0])
        st.altair_chart(alt.Chart(long).mark_line(point=True).encode(x=alt.X("run:O", title="run"), y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 1])),
                                                                     color="metric:N", tooltip=["run", "metric", "score"]), width="stretch")

    st.subheader("Retrieval hit-rate by domain")
    df = pd.DataFrame({"domain": [theme.DOMAIN_LABEL.get(d, d) for d in res["retrieval_hit_rate_by_domain"]],
                       "hit_rate": [v if v is not None else 0 for v in res["retrieval_hit_rate_by_domain"].values()]})
    st.altair_chart(alt.Chart(df).mark_bar(cornerRadiusEnd=6).encode(
        x=alt.X("domain", sort=None, title=None), y=alt.Y("hit_rate", scale=alt.Scale(domain=[0, 1]), title="hit-rate"),
        color=alt.Color("domain", legend=None, scale=alt.Scale(range=list(theme.DOMAIN_COLOR.values()))), tooltip=["domain", "hit_rate"]), width="stretch")

    st.subheader("Routing: per-domain precision / recall")
    prf = pd.DataFrame(res["per_domain_routing"]).T[["precision", "recall", "f1", "support"]]
    st.dataframe(prf, width="stretch", column_config={k: st.column_config.ProgressColumn(k, min_value=0, max_value=1, format="%.2f") for k in ("precision", "recall", "f1")})
    st.subheader("Routing: gold domain (rows) vs predicted domain (columns), query counts")
    cm = pd.DataFrame(res["confusion_matrix"]).T
    long = cm.reset_index().melt(id_vars="index", var_name="predicted", value_name="queries").rename(columns={"index": "gold"})
    heat = alt.Chart(long).mark_rect(cornerRadius=4).encode(x="predicted:N", y="gold:N", color=alt.Color("queries:Q", scale=alt.Scale(scheme="blues")), tooltip=["gold", "predicted", "queries"])
    st.altair_chart(heat + heat.mark_text().encode(text="queries:Q", color=alt.value("black")), width="stretch")

    st.subheader("Confidence calibration (top recommendation vs gold relevance)")
    cal = pd.DataFrame(res["calibration"])
    st.dataframe(cal, width="stretch", hide_index=True, column_config={
        "mean_confidence": st.column_config.ProgressColumn("mean confidence", min_value=0, max_value=1, format="%.2f"),
        "observed_precision": st.column_config.ProgressColumn("observed precision", min_value=0, max_value=1, format="%.2f")})
    st.caption("A well-calibrated system has observed precision close to mean confidence in each bucket.")
    st.subheader("Per-query results")
    pq = pd.DataFrame(res["per_query"])
    keep = [c for c in ["id", "query", "expected_domains", "predicted_domains", "routing_exact", "ndcg_at_3", "faithfulness", "latency_ms", "error"] if c in pq]
    st.dataframe(pq[keep], width="stretch", hide_index=True)


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
