"""Look and feel helpers for the dashboard. Owner: P4. All colours come from tokens.py (see its rules)."""
import re
from html import escape as esc

import streamlit as st

from p4_eval_ui.ui import tokens as T

DOMAIN_COLOR, DOMAIN_LABEL = T.DOMAIN_COLOR, T.DOMAIN_LABEL
BUCKET_COLOR, STATUS_COLOR = T.BUCKET_COLOR, T.STATUS_COLOR

CSS = T.css_vars() + """
.block-container{max-width:1240px;padding-top:1.4rem;padding-bottom:3rem}
header[data-testid="stHeader"]{background:transparent}
h1,h2,h3{color:var(--sd-ink)}
.hero{background:var(--sd-brand-strong);border-radius:var(--sd-radius-card);padding:24px 28px;color:var(--sd-on-brand);margin-bottom:18px}
.hero h1{margin:0;font-size:1.85rem;line-height:1.15;color:var(--sd-on-brand);padding:0;font-weight:700;letter-spacing:-.01em}
.hero p{margin:.4rem 0 .9rem;font-size:1rem;opacity:.92;color:var(--sd-on-brand)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:color-mix(in srgb,var(--sd-on-brand) 16%,transparent);border:1px solid color-mix(in srgb,var(--sd-on-brand) 35%,transparent);border-radius:999px;padding:3px 12px;font-size:.82rem;color:var(--sd-on-brand)}
.card{border:1px solid var(--sd-border);border-radius:var(--sd-radius-card);padding:16px 18px;background:var(--sd-surface);box-shadow:0 1px 2px color-mix(in srgb,var(--sd-ink) 7%,transparent);margin:8px 0 12px}
.card h4{margin:0 0 6px;font-size:1.02rem}
.summary{margin-bottom:14px;border-left:4px solid var(--sd-brand);border-radius:var(--sd-radius-control);padding:14px 18px;background:color-mix(in srgb,var(--sd-brand) 7%,var(--sd-surface));font-size:1.02rem;line-height:1.55}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--sd-border);background:var(--sd-surface);border-radius:999px;padding:1px 10px;font-size:.78rem;font-weight:600;white-space:nowrap}
.pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
.pill i.sq{border-radius:2px}
.rec-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.rec-title{font-weight:700;font-size:1.05rem}
.meta{color:var(--sd-muted);font-size:.84rem}
.bar{height:8px;border-radius:99px;background:var(--sd-border);overflow:hidden;margin:8px 0 4px}
.bar>div{height:100%;border-radius:99px}
.why{margin:.35rem 0 .2rem;line-height:1.5}
.caveat{font-size:.84rem;color:var(--sd-muted);margin-top:3px}
.step{display:flex;gap:14px;align-items:flex-start;padding:10px 14px;border:1px solid var(--sd-border);border-radius:var(--sd-radius-card);margin:8px 0;background:var(--sd-surface)}
.step .n{flex:0 0 28px;height:28px;border-radius:50%;background:var(--sd-brand);color:var(--sd-on-brand);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem}
.kpi{display:inline-block;margin:4px 8px 4px 0;padding:6px 12px;border-radius:var(--sd-radius-control);border:1px dashed var(--sd-muted);font-size:.9rem;background:var(--sd-surface)}
.cite{border-left:3px solid var(--sd-border);padding:2px 12px;margin:6px 0;font-size:.92rem}
mark{background:color-mix(in srgb,var(--sd-warning) 25%,var(--sd-surface));color:inherit;border-radius:3px;padding:0 2px}
.ribbon{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 14px;border:1px solid var(--sd-border);border-radius:var(--sd-radius-card);background:var(--sd-surface);margin:6px 0 14px}
.ribbon .node{border:1px solid var(--sd-border);border-radius:var(--sd-radius-control);padding:2px 10px;font-size:.84rem;font-weight:600}
.ribbon .arrow{color:var(--sd-muted)}
.need{border:1px solid var(--sd-border);border-left:5px solid var(--sd-warning);border-radius:var(--sd-radius-card);padding:14px 18px;background:color-mix(in srgb,var(--sd-warning) 8%,var(--sd-surface));margin:8px 0 6px}
.need h4{margin:0 0 6px}
.need ul{margin:6px 0 0;padding-left:22px}
.need li{margin:2px 0}
.tile{border:1px solid var(--sd-border);border-radius:var(--sd-radius-card);padding:12px 16px;background:var(--sd-surface);height:100%;box-shadow:0 1px 2px color-mix(in srgb,var(--sd-ink) 7%,transparent)}
.tile .lab{color:var(--sd-muted);font-size:.85rem}
.tile .val{font-size:1.9rem;font-weight:700;line-height:1.2}
.tile .sub{font-size:.8rem;color:var(--sd-muted);margin-top:2px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.group-h{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--sd-muted);margin:10px 0 2px}
[data-testid="stMetric"]{border:1px solid var(--sd-border);border-radius:var(--sd-radius-card);padding:12px 16px;background:var(--sd-surface)}
div.stButton>button[kind="primary"]{background:var(--sd-brand);border:0;color:var(--sd-on-brand);font-weight:650;border-radius:var(--sd-radius-control);padding:.55rem 1.3rem}
div.stButton>button[kind="primary"]:hover{background:var(--sd-brand-strong)}
section[data-testid="stSidebar"] div.stButton>button{border-radius:var(--sd-radius-control);text-align:left;justify-content:flex-start}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:10px 14px}
textarea{border-radius:var(--sd-radius-control)!important}
"""
CSS = f"<style>{CSS}</style>"


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


def pill(text: str, color: str, square: bool = False) -> str:
    """Shape grammar: a circle marks a STATE, a square marks a DOMAIN (so shared hues never mean two things)."""
    return f'<span class="pill"><i class="{"sq" if square else ""}" style="background:{color}"></i>{esc(text)}</span>'


def domain_pill(domain: str) -> str:
    return pill(DOMAIN_LABEL.get(domain, domain), DOMAIN_COLOR.get(domain, T.MUTED), square=True)


def status_pill(status: str) -> str:
    return pill(status.replace("_", " ").title(), STATUS_COLOR.get(status, T.MUTED))


def conf_bar(score: float, bucket: str) -> str:
    c = BUCKET_COLOR.get(bucket, T.MUTED)
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
        f'<span class="node"><span class="dot" style="background:{STATUS_COLOR.get(agents.get(d, {}).get("status", ""), T.MUTED)}"></span>'
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
    out = esc(text)
    for t in sorted({t for t in terms if len(t) > 3}, key=len, reverse=True):
        out = re.sub(rf"(?i)\b({re.escape(esc(t))})", r"<mark>\1</mark>", out)
    return out


def query_terms(query: str):
    stop = {"which", "should", "would", "could", "about", "their", "there", "what", "from", "with", "that", "this", "have", "does"}
    return [w for w in re.findall(r"[A-Za-z0-9\-]+", query) if len(w) > 3 and w.lower() not in stop]
