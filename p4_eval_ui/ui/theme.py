"""Look and feel helpers for the dashboard. Owner: P4. Colours work on light and dark Streamlit themes."""
from html import escape as esc

import streamlit as st

DOMAIN_COLOR = {"technology": "#3b82f6", "clinical": "#14b8a6", "sec": "#f59e0b", "corporate_responsibility": "#22c55e"}
DOMAIN_LABEL = {"technology": "Technology", "clinical": "Clinical", "sec": "SEC", "corporate_responsibility": "Corporate Responsibility"}
BUCKET_COLOR = {"High": "#16a34a", "Medium": "#d97706", "Low": "#dc2626"}
STATUS_COLOR = {"ANALYSIS_COMPLETE": "#16a34a", "HYPOTHESIS": "#d97706", "INFORMATION_REQUEST": "#ea580c", "CONFIRMED_FAULT": "#2563eb"}

CSS = """
<style>
.block-container{max-width:1240px;padding-top:1.4rem;padding-bottom:3rem}
header[data-testid="stHeader"]{background:transparent}
.hero{background:linear-gradient(120deg,#4f46e5 0%,#0ea5e9 55%,#14b8a6 100%);border-radius:18px;padding:26px 30px;color:#fff;margin-bottom:18px;box-shadow:0 8px 30px rgba(14,165,233,.25)}
.hero h1{margin:0;font-size:2rem;line-height:1.15;color:#fff;padding:0;font-weight:750;letter-spacing:-.01em}
.hero p{margin:.45rem 0 .9rem;font-size:1.02rem;opacity:.95;color:#fff}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:3px 12px;font-size:.82rem;color:#fff}
.card{border:1px solid rgba(128,128,128,.28);border-radius:14px;padding:16px 18px;background:rgba(128,128,128,.07);margin:8px 0 12px}
.card h4{margin:0 0 6px;font-size:1.02rem}
.summary{margin-bottom:14px;border-left:5px solid #6366f1;border-radius:10px;padding:14px 18px;background:rgba(99,102,241,.09);font-size:1.02rem;line-height:1.55}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(128,128,128,.4);border-radius:999px;padding:1px 10px;font-size:.78rem;font-weight:600;white-space:nowrap}
.pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
.rec-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.rec-title{font-weight:700;font-size:1.05rem}
.meta{opacity:.75;font-size:.84rem}
.bar{height:9px;border-radius:99px;background:rgba(128,128,128,.25);overflow:hidden;margin:8px 0 4px}
.bar>div{height:100%;border-radius:99px}
.why{margin:.35rem 0 .2rem;line-height:1.5}
.caveat{font-size:.84rem;opacity:.85;margin-top:3px}
.step{display:flex;gap:14px;align-items:flex-start;padding:10px 14px;border:1px solid rgba(128,128,128,.25);border-radius:12px;margin:8px 0;background:rgba(128,128,128,.05)}
.step .n{flex:0 0 28px;height:28px;border-radius:50%;background:#6366f1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem}
.kpi{display:inline-block;margin:4px 8px 4px 0;padding:6px 12px;border-radius:10px;border:1px dashed rgba(128,128,128,.5);font-size:.9rem}
.cite{border-left:3px solid rgba(128,128,128,.5);padding:2px 12px;margin:6px 0;font-size:.92rem}
[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.28);border-radius:14px;padding:12px 16px;background:rgba(128,128,128,.06)}
[data-testid="stMetricLabel"]{opacity:.75}
div.stButton>button[kind="primary"]{background:linear-gradient(120deg,#4f46e5,#0ea5e9);border:0;color:#fff;font-weight:650;border-radius:10px;padding:.55rem 1.3rem}
div.stButton>button[kind="primary"]:hover{filter:brightness(1.08)}
section[data-testid="stSidebar"] div.stButton>button{border-radius:10px;text-align:left;justify-content:flex-start}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:10px 14px}
textarea{border-radius:10px!important}
mark{background:rgba(250,204,21,.45);color:inherit;border-radius:3px;padding:0 2px}
.ribbon{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 14px;border:1px solid rgba(128,128,128,.28);border-radius:12px;background:rgba(128,128,128,.05);margin:6px 0 14px}
.ribbon .node{border:1px solid rgba(128,128,128,.4);border-radius:8px;padding:2px 10px;font-size:.84rem;font-weight:600}
.ribbon .arrow{opacity:.5}
.need{border:1px solid #ea580c;border-left:6px solid #ea580c;border-radius:12px;padding:14px 18px;background:rgba(234,88,12,.07);margin:8px 0 6px}
.need h4{margin:0 0 6px}
.need ul{margin:6px 0 0;padding-left:22px}
.need li{margin:2px 0}
.tile{border:1px solid rgba(128,128,128,.28);border-radius:14px;padding:12px 16px;background:rgba(128,128,128,.06);height:100%}
.tile .lab{opacity:.75;font-size:.85rem}
.tile .val{font-size:1.9rem;font-weight:700;line-height:1.2}
.tile .sub{font-size:.8rem;opacity:.85;margin-top:2px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.group-h{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;opacity:.65;margin:10px 0 2px}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(llm_mode: str, real_domains: str) -> None:
    chips = "".join(f'<span class="chip">{esc(l)}</span>' for l in ("Technology", "Clinical", "SEC filings", "Corporate Responsibility"))
    st.markdown(
        f'<div class="hero"><h1>AI Management Consulting Platform</h1>'
        f"<p>Ask a business question. A manager agent routes it to specialist agents, grounds each answer in source documents, "
        f"and returns evidence, recommendations and next steps.</p>"
        f'<div class="chips">{chips}<span class="chip">LLM: {esc(llm_mode)}</span><span class="chip">agents: {esc(real_domains)}</span></div></div>',
        unsafe_allow_html=True,
    )


def pill(text: str, color: str) -> str:
    return f'<span class="pill"><i style="background:{color}"></i>{esc(text)}</span>'


def domain_pill(domain: str) -> str:
    return pill(DOMAIN_LABEL.get(domain, domain), DOMAIN_COLOR.get(domain, "#6b7280"))


def status_pill(status: str) -> str:
    return pill(status.replace("_", " ").title(), STATUS_COLOR.get(status, "#6b7280"))


def conf_bar(score: float, bucket: str) -> str:
    c = BUCKET_COLOR.get(bucket, "#6b7280")
    return (f'<div class="bar"><div style="width:{max(0, min(1, score)) * 100:.0f}%;background:{c}"></div></div>'
            f'<div class="meta">Confidence {score:.2f} · {esc(bucket)}</div>')


def card(inner_html: str) -> None:
    st.markdown(f'<div class="card">{inner_html}</div>', unsafe_allow_html=True)


def path_ribbon(trace) -> str:
    """One-line summary of the route a request took, built from audit_trace."""
    agents = (trace or {}).get("agents", {})
    routed = [str(getattr(d, "value", d)) for d in ((trace or {}).get("routing") or {}).get("domains", [])]
    arrow = '<span class="arrow">&rarr;</span>'
    mid = "".join(
        f'<span class="node"><span class="dot" style="background:{STATUS_COLOR.get(agents.get(d, {}).get("status", ""), "#6b7280")}"></span>'
        f'{esc(DOMAIN_LABEL.get(d, d))}</span>' for d in routed)
    return ('<div class="ribbon"><span class="node">Customer</span>' + arrow + '<span class="node">Manager</span>' + arrow
            + f'<span style="display:inline-flex;gap:6px;flex-wrap:wrap">{mid}</span>' + arrow
            + '<span class="node">Synthesizer</span>' + arrow + '<span class="node">Report</span></div>')


def tile(label: str, value: str, sub: str = "", color: str = "") -> None:
    dot = f'<span class="dot" style="background:{color}"></span>' if color else ""
    st.markdown(f'<div class="tile"><div class="lab">{esc(label)}</div><div class="val">{esc(value)}</div>'
                f'<div class="sub">{dot}{esc(sub)}</div></div>', unsafe_allow_html=True)


def highlight(text: str, terms) -> str:
    """HTML-escape `text` and wrap query terms in <mark>."""
    import re
    out = esc(text)
    for t in sorted({t for t in terms if len(t) > 3}, key=len, reverse=True):
        out = re.sub(rf"(?i)\b({re.escape(esc(t))})", r"<mark>\1</mark>", out)
    return out


def query_terms(query: str):
    import re
    stop = {"which", "should", "would", "could", "about", "their", "there", "what", "from", "with", "that", "this", "have", "does"}
    return [w for w in re.findall(r"[A-Za-z0-9\-]+", query) if len(w) > 3 and w.lower() not in stop]
