"""Suggest IQ dashboard. Owner: P4.   python -m p4_eval_ui.ui.launch   (light theme; or: streamlit run p4_eval_ui/ui/dashboard.py)

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
from p4_eval_ui.ui import nav, theme  # noqa: E402
from p4_eval_ui.ui import tokens as T  # noqa: E402
from p4_eval_ui.ui.flow import build_flow_html  # noqa: E402

esc = theme.esc
FLOW_HEIGHT = 560
BRIEF_EXAMPLE = ("Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement "
                 "parts should we order, and what actions should we take to prevent future outages?")
BRIEF_WITH_MODEL = BRIEF_EXAMPLE.replace("Cisco enterprise router", "Cisco Catalyst 8200 enterprise router")  # a model number lets the recommender pick compatible parts
DIAG_EXAMPLE = (
    "show tech-support output attached: no crash files found.\n"
    "show logging: repeated power-supply 1 fault messages and WAN link flaps.\n"
    "show interfaces GigabitEthernet0/0/1 counters: input errors 0, CRC errors 0.\n"
    "show environment: power supply 1 reports FAILED, power supply 2 OK; temperature and fan status normal.\n"
    "show platform hardware status: all modules ok except power supply 1.\n"
    "software version: IOS XE 17.9, uptime 12 days.\n"
    "Optic DOM readings on the WAN fibre uplink are within the normal range."
)
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
    """(label, question, diagnostics) chips for the home page. One click asks the question."""
    items = {i["id"]: i["query"] for i in json.loads((REPO_ROOT / "core" / "fixtures" / "benchmark_queries.json").read_text())}
    return [
        ("Failing Cisco router", BRIEF_EXAMPLE, ""),
        ("With logs attached", BRIEF_WITH_MODEL, DIAG_EXAMPLE),
        ("Pathology scanner", items["Q07"], ""),
        ("Cisco risk factors", items["Q11"], ""),
        ("Food insecurity in 2023", items["Q16"], ""),
        ("Cross-domain example", items["Q22"], ""),
    ]


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
    html = build_flow_html(trace, dark=_is_dark())  # all dynamic text inside is HTML-escaped by build_flow_html
    if hasattr(st, "iframe"):  # st.components.v1.html is deprecated in newer Streamlit
        st.iframe(html, height=FLOW_HEIGHT)
    else:
        components.html(html, height=FLOW_HEIGHT, scrolling=False)


def _run(manager, query: str, diagnostics: str) -> None:
    ctx = {"diagnostics": diagnostics.strip()} if diagnostics and diagnostics.strip() else None
    try:
        with st.spinner("Suggest IQ is routing your question to the right specialists..."):
            st.session_state["report"] = manager.handle(query, ctx)
            st.session_state["report_had_diagnostics"] = bool(ctx)
    except Exception as err:  # noqa: BLE001
        st.error(f"The pipeline failed: {type(err).__name__}: {err}")


def render_needs_info(manager, report, view, blocked: bool = False) -> None:
    missing = []
    for resp in report.domain_findings.values():
        for m in resp.missing_diagnostics_needed:
            if m not in missing:
                missing.append(m)
    items = "".join(f"<li>{esc(m)}</li>" for m in missing)
    st.markdown(f'<div class="need"><h4>More information needed before parts can be recommended</h4>'
               f'<div class="meta">{"Suggest IQ cannot recommend anything yet. Please provide:" if blocked else "The answer below is provisional. Please provide:"}</div><ul>{items}</ul></div>', unsafe_allow_html=True)
    st.text_area("Paste the requested output here", key="followup_diag", height=110, label_visibility="collapsed",
                 placeholder="Paste logs, error counters, versions...")
    c = st.columns([2.2, 1.6, 3])
    if c[0].button("Add diagnostics and re-run", type="primary", disabled=manager is None, key="rerun"):
        _run(manager, report.query, st.session_state.get("followup_diag", ""))
        st.rerun()
    c[1].button("Use example logs", key="use_example_logs", on_click=lambda: st.session_state.update(followup_diag=DIAG_EXAMPLE))


def _ask(manager, query: str, diagnostics: str = "") -> None:
    _run(manager, query, diagnostics)
    st.session_state["view"] = "result" if st.session_state.get("report") is not None else "home"


def _queue(query: str, diagnostics: str = "") -> None:
    st.session_state["pending"] = (query, diagnostics)


def _new_question() -> None:
    for k in ("report", "query", "diagnostics", "followup_diag", "pending"):
        st.session_state.pop(k, None)
    st.session_state["view"] = "home"


def _show(view: str) -> None:
    st.session_state["view"] = view


CHIP_ICONS = {"Failing Cisco router": ":material/router:", "With logs attached": ":material/attach_file:", "Pathology scanner": ":material/biotech:",
              "Cisco risk factors": ":material/gavel:", "Food insecurity in 2023": ":material/restaurant:", "Cross-domain example": ":material/hub:"}


def render_home(manager) -> None:
    nav.render_navbar("consult")
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        st.markdown('<div class="headline">Guiding enterprises from <em>questions</em> to <em>decisions</em></div>'
                    '<div class="subline">Ask a business question. Suggest IQ routes it to specialist agents and answers with cited evidence.</div>',
                    unsafe_allow_html=True)
        with st.form("ask", border=True):
            st.text_area("Ask a business question", key="query", height=110, label_visibility="collapsed",
                         placeholder="Ask a business question, e.g. which parts should we order for our failing Cisco router?")
            with st.expander("Attach logs or telemetry (optional)", icon=":material/attach_file:"):
                st.text_area("Diagnostics", key="diagnostics", height=100, label_visibility="collapsed",
                             placeholder="Paste show tech-support output, error codes, versions...")
            foot = st.columns([3, 1.3], vertical_alignment="center")
            foot[0].caption("Press Ctrl + Enter to ask")
            with foot[1]:
                go = st.form_submit_button("Ask Suggest IQ", disabled=manager is None)
        if go:
            q = (st.session_state.get("query") or "").strip()
            if q:
                _ask(manager, q, st.session_state.get("diagnostics", ""))
                if st.session_state.get("report") is not None:
                    st.rerun()
            else:
                st.warning("Type a question first.")
        st.markdown('<div class="eyebrow">Try an example</div><div class="chiprow">', unsafe_allow_html=True)
        examples = _examples()
        for row in range(0, len(examples), 3):
            cols = st.columns(3)
            for col, (label, text, diag) in zip(cols, examples[row:row + 3]):
                col.button(label, key=f"ex_{label}", icon=CHIP_ICONS.get(label), on_click=_queue, args=(text, diag), width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="trust"><span>Every claim is cited</span><span>Never guesses a fault</span><span>Scored on 37 test questions</span></div>',
                    unsafe_allow_html=True)


def render_topbar(show_new: bool = True) -> None:
    nav.render_navbar("consult", action=("New question", ":material/add:", _new_question) if show_new else None)


def render_eval_page(manager) -> None:
    nav.render_navbar("eval")
    st.subheader("Evaluation")
    render_evaluation(manager)


def render_results(manager, report) -> None:
    render_topbar()
    st.markdown(f'<div class="ask">{esc(report.query)}</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Answer", "Evidence", "Trace"])  # Evaluation lives in the navbar so it is one click from every screen
    with tabs[0]:
        render_answer(manager, report)
    with tabs[1]:
        render_evidence()
    with tabs[2]:
        render_trace()


BOILERPLATE = "A prioritized action plan and measurable risk-mitigation framework are detailed below to ensure business continuity."


def is_blocked(statuses) -> bool:
    """True when no agent could answer (every domain asked for more information): there is nothing to rank, route or measure yet."""
    return bool(statuses) and all(s == "INFORMATION_REQUEST" for s in statuses)


def strip_boilerplate(summary: str) -> str:
    return summary.replace(BOILERPLATE, "").strip()


def answer_status(statuses):
    """Headline status for the answer tile, from the domain statuses. A hypothesis is never shown as 'Complete'."""
    n = len(statuses)
    if n == 0:
        return "No match", "no specialist could take this question", T.MUTED
    if any(s == "INFORMATION_REQUEST" for s in statuses):
        return "Provisional", f"{sum(s == 'INFORMATION_REQUEST' for s in statuses)} of {n} needs more information", T.WARNING
    if any(s == "CONFIRMED_FAULT" for s in statuses):
        return "Fault confirmed", "supplied diagnostics establish it", T.DANGER
    if any(s == "HYPOTHESIS" for s in statuses):
        return "Hypothesis", "plausible causes, none confirmed", T.INFO
    return "Complete", f"{n} of {n} analyses finished", T.SUCCESS


def split_rationale(why: str):
    """Scoring formulas ('Score 0.17 = similarity ...') are engineering detail: return (friendly_line, details_or_None)."""
    if why.lstrip().startswith("Score ") and "=" in why:
        return "Ranked by similarity to your description and catalog compatibility; see scoring details.", why
    return why, None


def is_unrouted(report) -> bool:
    """The router matched no specialist, so nothing ran and there is nothing honest to show except how to rephrase."""
    return not report.detected_domains


def _rephrase(query_key: str = "rephrase_text") -> None:
    text = (st.session_state.get(query_key) or "").strip()
    if text:
        _queue(text, "")


def render_unrouted(manager, report) -> None:
    st.markdown(f'<div class="strip">{theme.pill("No specialist matched this question", T.MUTED)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="need"><h4>We couldn\'t tell what you want to decide</h4>'
                '<div class="meta">Suggest IQ answers questions in four areas, and nothing in your message pointed to any of them.</div>'
                '<ul><li><b>Network hardware and diagnostics:</b> Cisco and Google equipment, failures, replacement parts</li>'
                '<li><b>Lab instruments and clinical evidence:</b> Agilent instruments, clinical trials and papers</li>'
                '<li><b>Company filings and risk:</b> Cisco, Agilent and Alphabet annual reports</li>'
                '<li><b>Food security and sustainability:</b> FAO State of Food Security reports</li></ul></div>', unsafe_allow_html=True)
    st.text_area("Rephrase your question", value=report.query, key="rephrase_text", height=90,
                 placeholder="Name a product, a company or a problem, e.g. which parts should we order for our failing Cisco router?")
    st.button("Ask again", key="rephrase_go", type="primary", icon=":material/refresh:", on_click=_rephrase, disabled=manager is None)
    st.markdown('<div class="eyebrow">Or try an example</div><div class="chiprow">', unsafe_allow_html=True)
    examples = _examples()[:3]
    cols = st.columns(3)
    for col, (label, text, diag) in zip(cols, examples):
        col.button(label, key=f"un_{label}", icon=CHIP_ICONS.get(label), on_click=_queue, args=(text, diag), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)


def render_answer(manager, report) -> None:
    """Reading order: the answer first (summary, recommendations, next steps, KPIs), supporting detail after (how it was routed)."""
    if is_unrouted(report):
        render_unrouted(manager, report)
        return
    view = explain(report)
    info_req = any(r.status == "INFORMATION_REQUEST" for r in report.domain_findings.values())
    statuses = [r.status for r in report.domain_findings.values()]
    n_cites = sum(len(r.citations) for r in report.domain_findings.values())
    label, sub, color = answer_status(statuses)
    conf = view.overall_confidence.replace(" (provisional)", "")

    # 0. be explicit when the live language model failed and built-in rules answered instead
    fallbacks = report.audit_trace.get("fallbacks_used") or []
    if fallbacks:
        st.warning("The language model was unavailable for part of this answer, so built-in keyword rules were used instead "
                   f"({esc(str(fallbacks[0]))[:160]}). Results may be less accurate; try again later or check the API quota.")

    blocked = is_blocked(statuses)

    # 1. one-line trust strip (status, confidence, evidence, who answered); confidence and citations mean nothing until something was answered
    agents = " ".join(theme.domain_pill(d.value) for d in report.detected_domains)
    extra = "" if blocked else (theme.pill("Confidence " + conf, T.BUCKET_COLOR.get(conf, T.MUTED)) + theme.pill(str(n_cites) + " citations", T.MUTED))
    st.markdown(f'<div class="strip">{theme.pill(label + ": " + sub, color)}{extra}<span class="strip-agents">{agents}</span></div>', unsafe_allow_html=True)

    # 2. what is needed to firm up the answer (only when something is missing)
    if info_req:
        render_needs_info(manager, report, view, blocked)

    # 3. the answer (or, when nothing could be answered yet, what we know so far)
    text = trim_summary(report.executive_summary, info_req)
    st.subheader("What we know so far" if blocked else "Executive summary")
    st.markdown(f'<div class="summary">{esc(strip_boilerplate(text) if blocked else text)}</div>', unsafe_allow_html=True)
    if report.cross_domain_synthesis:
        st.markdown(f'<div class="card">{esc(report.cross_domain_synthesis)}</div>', unsafe_allow_html=True)

    if blocked:
        # Focused view: the checklist above is the next step. No recommendations, KPIs or routing diagram until there is an answer to show.
        with st.expander("How your question was routed", icon=":material/account_tree:"):
            st.markdown(theme.path_ribbon(report.audit_trace), unsafe_allow_html=True)
            show_flow(report.audit_trace)
        return

    st.subheader("Recommendations")
    if not view.recommendations:
        st.markdown('<div class="card"><b>No specific recommendation was produced for this question.</b>'
                    '<div class="meta">Naming the exact product or model (for example Catalyst 8200) and attaching the requested logs '
                    'lets Suggest IQ match compatible parts and actions.</div></div>', unsafe_allow_html=True)
    for r in view.recommendations:
        caveats = "".join(f'<div class="caveat">⚠ {esc(c)}</div>' for c in r.caveats)
        ev = f'<div class="meta">Evidence ({r.evidence_count}): {esc("; ".join(r.evidence_sources))}</div>' if r.evidence_sources else ""
        st.markdown(
            f'<div class="card accent" style="--accent:{T.DOMAIN_COLOR.get(r.domain or "", T.BRAND)}"><div class="rec-top"><div><div class="rec-title">{esc(r.title)}</div>'
            f'<div class="meta">{esc(r.category)}</div></div><div>{theme.domain_pill(r.domain) if r.domain else ""}</div></div>'
            f'{theme.conf_bar(r.confidence_score, r.confidence_bucket)}'
            f'<div class="why"><b>Why:</b> {esc(split_rationale(r.why)[0])}</div>{ev}{caveats}</div>', unsafe_allow_html=True)
        if split_rationale(r.why)[1]:
            with st.expander("Scoring details"):
                st.caption(r.why)

    st.subheader("Next steps")
    for i, step in enumerate(report.next_steps, 1):
        st.markdown(f'<div class="step"><div class="n">{i}</div><div>{esc(step)}</div></div>', unsafe_allow_html=True)
    st.subheader("How impact will be measured")
    st.markdown("".join(f'<span class="kpi">{esc(k)}</span>' for k in dict.fromkeys(report.measuring_impact_kpis)), unsafe_allow_html=True)  # de-duplicated
    if view.what_would_change_this_answer:
        with st.expander("What would change this answer"):
            for w in view.what_would_change_this_answer:
                st.markdown(f"- {w}")

    # 4. supporting detail: how Suggest IQ got here (shown when at least one agent produced an answer)
    st.subheader("How Suggest IQ routed your question")
    st.markdown(theme.path_ribbon(report.audit_trace), unsafe_allow_html=True)
    show_flow(report.audit_trace)


def render_trace() -> None:
    report = st.session_state.get("report")
    if report is None:
        st.info("Ask a question to see the routing decision and per-agent execution.")
        return
    t = report.audit_trace
    c = st.columns(3)
    c[0].metric("Total latency (ms)", t.get("total_ms", "n/a"))
    c[1].metric("LLM mode", t.get("mode", "n/a"))
    c[2].metric("Fallbacks used", len(t.get("fallbacks_used", [])))
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
        unc = T.UNCERTAINTY_COLOR.get(resp.uncertainty_level, T.MUTED)
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
        return T.MUTED
    return T.SUCCESS if value >= target else T.WARNING if value >= 0.8 * target else T.DANGER


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
        theme.tile("Errors", str(res["errors"]), "pipeline crashes during the run", T.SUCCESS if res["errors"] == 0 else T.DANGER)
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
                                                                     color=alt.Color("metric:N", scale=alt.Scale(range=T.SERIES)), tooltip=["run", "metric", "score"]), width="stretch")

    st.subheader("Retrieval hit-rate by domain")
    df = pd.DataFrame({"domain": [theme.DOMAIN_LABEL.get(d, d) for d in res["retrieval_hit_rate_by_domain"]],
                       "hit_rate": [v if v is not None else 0 for v in res["retrieval_hit_rate_by_domain"].values()]})
    st.altair_chart(alt.Chart(df).mark_bar(cornerRadiusEnd=6).encode(
        x=alt.X("domain", sort=None, title=None), y=alt.Y("hit_rate", scale=alt.Scale(domain=[0, 1]), title="hit-rate"),
        color=alt.Color("domain", legend=None, scale=alt.Scale(range=list(T.DOMAIN_COLOR.values()))), tooltip=["domain", "hit_rate"]), width="stretch")

    st.subheader("Routing: per-domain precision / recall")
    prf = pd.DataFrame(res["per_domain_routing"]).T[["precision", "recall", "f1", "support"]]
    st.dataframe(prf, width="stretch", column_config={k: st.column_config.ProgressColumn(k, min_value=0, max_value=1, format="%.2f") for k in ("precision", "recall", "f1")})
    st.subheader("Routing: gold domain (rows) vs predicted domain (columns), query counts")
    cm = pd.DataFrame(res["confusion_matrix"]).T
    long = cm.reset_index().melt(id_vars="index", var_name="predicted", value_name="queries").rename(columns={"index": "gold"})
    heat = alt.Chart(long).mark_rect(cornerRadius=4).encode(x="predicted:N", y="gold:N", color=alt.Color("queries:Q", scale=alt.Scale(range=T.HEATMAP)), tooltip=["gold", "predicted", "queries"])
    mx = max(1, int(long["queries"].max()))
    txt = heat.mark_text().encode(text="queries:Q", color=alt.condition(f"datum.queries > {mx / 2}", alt.value(T.ON_BRAND), alt.value(T.INK)))
    st.altair_chart(heat + txt, width="stretch")

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
    st.set_page_config(page_title="Suggest IQ", page_icon="💡", layout="wide", initial_sidebar_state="collapsed")
    theme.inject_css()
    if st.query_params.get("app") == "retail" and "retail_deeplinked" not in st.session_state:  # ?app=retail&cart=SKU1,SKU2 opens the checkout directly
        st.session_state["retail_deeplinked"] = True
        st.session_state["app"] = "retail"
        cart = [c for c in (st.query_params.get("cart") or "").split(",") if c]
        if cart:
            st.session_state["retail_cart"] = cart
    if st.session_state.get("app") == "retail":  # the home-page toggle switches the whole app to the retail checkout
        from retail_basket import ui as retail_ui

        retail_ui.render()
        return
    manager = get_manager()
    demo = st.query_params.get("demo")  # ?demo=cisco or ?demo=cisco-diag preloads a run (handy for demos and screenshots)
    if demo and manager is not None and "report" not in st.session_state and "demo_done" not in st.session_state:
        st.session_state["demo_done"] = True
        _ask(manager, BRIEF_WITH_MODEL if demo == "cisco-diag" else BRIEF_EXAMPLE, DIAG_EXAMPLE if demo == "cisco-diag" else "")
    pending = st.session_state.pop("pending", None)
    if pending and manager is not None:
        _ask(manager, pending[0], pending[1])
    if manager is None:
        st.error("The Manager Agent (P1) is not built yet, so Suggest IQ cannot run.")
    view = st.session_state.get("view", "home")
    report = st.session_state.get("report")
    if view == "eval":
        render_eval_page(manager)
    elif report is not None:
        render_results(manager, report)
    else:
        render_home(manager)


if __name__ == "__main__":  # Streamlit runs the script as __main__; importing it (e.g. from tests) must not render
    main()
