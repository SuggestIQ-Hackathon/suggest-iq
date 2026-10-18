"""Look and feel helpers for the dashboard. Owner: P4. All colours come from tokens.py (see its rules)."""
import re
from html import escape as esc

import streamlit as st

from p4_eval_ui.ui import tokens as T

DOMAIN_COLOR, DOMAIN_LABEL = T.DOMAIN_COLOR, T.DOMAIN_LABEL
BUCKET_COLOR, STATUS_COLOR = T.BUCKET_COLOR, T.STATUS_COLOR

CSS = T.css_vars() + """
:root{--sd-font:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--sd-shadow-sm:0 1px 2px color-mix(in srgb,var(--sd-ink) 6%,transparent),0 1px 1px color-mix(in srgb,var(--sd-ink) 4%,transparent);
--sd-shadow-lg:0 12px 40px color-mix(in srgb,var(--sd-brand-strong) 14%,transparent),0 2px 6px color-mix(in srgb,var(--sd-ink) 6%,transparent);
--sd-radius-lg:20px}
html,body,.stApp,.stApp button,.stApp textarea,.stApp input{font-family:var(--sd-font)!important}
.stApp{background:radial-gradient(1100px 520px at 50% -8%,color-mix(in srgb,var(--sd-brand) 10%,transparent),transparent 70%),var(--sd-bg)!important}
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],#MainMenu,footer{display:none!important}
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stSidebarCollapseButton"]{display:none}
.block-container{max-width:1180px;padding-top:1.2rem;padding-bottom:4rem}
h1,h2,h3,h4{color:var(--sd-ink);letter-spacing:-.015em}
h3{font-size:1.15rem!important;font-weight:700!important;margin-top:1.4rem!important}
@keyframes sd-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.card,.tile,.step,.need,.summary,.ribbon,.ask{animation:sd-in .35s ease both}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}

/* brand + home */
.brand{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:-.03em;color:var(--sd-ink)}
.brand .mark{background:var(--sd-brand-strong);color:var(--sd-on-brand);border-radius:12px;padding:0 12px;font-weight:800}
.brand.big{justify-content:center;font-size:3.6rem;margin-top:11vh;line-height:1.1}
.brand.big .mark{padding:0 18px;border-radius:18px;box-shadow:var(--sd-shadow-lg)}
.brand.small{font-size:1.3rem}
.brand.small .mark{border-radius:9px;padding:0 9px}
.tagline{text-align:center;color:var(--sd-muted);font-size:1.12rem;font-weight:450;margin:.5rem 0 2rem}

/* composer */
div[data-testid="stForm"]{background:var(--sd-surface);border:1px solid var(--sd-border);border-radius:var(--sd-radius-lg);padding:18px 20px 12px;box-shadow:var(--sd-shadow-lg);transition:border-color .15s,box-shadow .15s}
div[data-testid="stForm"]:focus-within{border-color:color-mix(in srgb,var(--sd-brand) 55%,var(--sd-border));box-shadow:0 0 0 4px color-mix(in srgb,var(--sd-brand) 14%,transparent),var(--sd-shadow-lg)}
div[data-testid="stForm"] [data-baseweb="textarea"],div[data-testid="stForm"] [data-baseweb="textarea"] *,div[data-testid="stForm"] [data-baseweb="base-input"],div[data-testid="stForm"] textarea{background:transparent!important;border:0!important;box-shadow:none!important}
div[data-testid="stForm"] textarea{font-size:1.12rem;line-height:1.55;color:var(--sd-ink)}
div[data-testid="stForm"] details{border:0!important;background:transparent!important}
div[data-testid="stForm"] details summary{color:var(--sd-muted);font-size:.9rem;padding-left:0}
div[data-testid="stForm"] [data-testid="stFormSubmitButton"]{display:flex;justify-content:flex-end}
div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button{background:var(--sd-brand-strong);color:var(--sd-on-brand);border:0;border-radius:999px;padding:.55rem 1.5rem;font-weight:650;transition:transform .12s,background .12s}
div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover{background:var(--sd-brand);transform:translateY(-1px)}
div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button::after{content:" \\2192"}
.chiprow div.stButton>button{border-radius:999px;border:1px solid var(--sd-border);background:color-mix(in srgb,var(--sd-surface) 75%,transparent);color:var(--sd-ink);font-size:.86rem;font-weight:500;padding:.4rem .9rem;box-shadow:var(--sd-shadow-sm);transition:transform .12s,border-color .12s,color .12s}
.chiprow div.stButton>button:hover{border-color:var(--sd-brand);color:var(--sd-brand);transform:translateY(-1px)}
.foot{text-align:center;color:var(--sd-muted);font-size:.82rem;margin-top:2.4rem}

/* results */
.ask{display:inline-block;background:var(--sd-brand-strong);color:var(--sd-on-brand);border-radius:20px 20px 20px 6px;padding:11px 18px;margin:8px 0 12px;max-width:88%;line-height:1.5;box-shadow:var(--sd-shadow-sm)}
[role="tablist"],[data-baseweb="tab-list"]{gap:4px!important;background:color-mix(in srgb,var(--sd-ink) 6%,transparent)!important;padding:4px!important;border-radius:999px!important;width:fit-content!important;border:0!important}
[role="tab"]{height:auto!important;padding:7px 18px!important;border-radius:999px!important;font-weight:600!important;color:var(--sd-muted)!important;background:transparent!important;margin:0!important}
[role="tab"][aria-selected="true"]{background:var(--sd-surface)!important;color:var(--sd-ink)!important;box-shadow:var(--sd-shadow-sm)}
[role="tab"] p{color:inherit!important;font-weight:600}
[role="tablist"]>:not([role="tab"]),[data-baseweb="tab-highlight"],[data-baseweb="tab-border"],[data-testid="stTabs"] [role="tablist"]+div[aria-hidden="true"]{display:none!important}
.card{border:1px solid var(--sd-border);border-radius:16px;padding:18px 20px;background:var(--sd-surface);box-shadow:var(--sd-shadow-sm);margin:8px 0 12px}
.card.accent{border-left:4px solid var(--accent,var(--sd-brand))}
.summary{border:1px solid var(--sd-border);border-radius:16px;padding:18px 22px;background:var(--sd-surface);box-shadow:var(--sd-shadow-sm);font-size:1.06rem;line-height:1.6;margin-bottom:14px}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--sd-border);background:var(--sd-surface);border-radius:999px;padding:2px 11px;font-size:.78rem;font-weight:600;white-space:nowrap}
.pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
.pill i.sq{border-radius:2px}
.rec-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.rec-title{font-weight:700;font-size:1.06rem}
.meta{color:var(--sd-muted);font-size:.84rem}
.bar{height:8px;border-radius:99px;background:color-mix(in srgb,var(--sd-ink) 8%,transparent);overflow:hidden;margin:10px 0 4px}
.bar>div{height:100%;border-radius:99px}
.why{margin:.4rem 0 .2rem;line-height:1.55}
.caveat{font-size:.84rem;color:var(--sd-muted);margin-top:3px}
.step{display:flex;gap:14px;align-items:center;padding:12px 16px;border:1px solid var(--sd-border);border-radius:14px;margin:8px 0;background:var(--sd-surface);box-shadow:var(--sd-shadow-sm)}
.step .n{flex:0 0 28px;height:28px;border-radius:50%;background:var(--sd-brand-strong);color:var(--sd-on-brand);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.82rem}
.kpi{display:inline-block;margin:4px 8px 4px 0;padding:7px 14px;border-radius:999px;border:1px solid var(--sd-border);font-size:.88rem;background:var(--sd-surface);box-shadow:var(--sd-shadow-sm)}
.cite{border-left:3px solid var(--sd-border);padding:2px 12px;margin:6px 0;font-size:.92rem}
mark{background:color-mix(in srgb,var(--sd-warning) 22%,var(--sd-surface));color:inherit;border-radius:4px;padding:0 3px}
.ribbon{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px 14px;border:1px solid var(--sd-border);border-radius:999px;background:var(--sd-surface);box-shadow:var(--sd-shadow-sm);margin:10px 0 16px;width:fit-content;max-width:100%}
.ribbon .node{border-radius:999px;padding:2px 11px;font-size:.84rem;font-weight:600;background:color-mix(in srgb,var(--sd-ink) 5%,transparent)}
.ribbon .arrow{color:var(--sd-muted)}
.need{border:1px solid var(--sd-border);border-left:5px solid var(--sd-warning);border-radius:16px;padding:16px 20px;background:color-mix(in srgb,var(--sd-warning) 7%,var(--sd-surface));margin:8px 0 8px;box-shadow:var(--sd-shadow-sm)}
.need h4{margin:0 0 6px;font-size:1.1rem}
.need ul{margin:6px 0 0;padding-left:22px}
.need li{margin:3px 0}
.tile{border:1px solid var(--sd-border);border-radius:16px;padding:14px 18px;background:var(--sd-surface);height:100%;box-shadow:var(--sd-shadow-sm)}
.tile .lab{color:var(--sd-muted);font-size:.8rem;font-weight:600;letter-spacing:.02em;text-transform:uppercase}
.tile .val{font-size:1.85rem;font-weight:750;line-height:1.25;letter-spacing:-.02em}
.tile .sub{font-size:.8rem;color:var(--sd-muted);margin-top:2px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.group-h{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--sd-muted);margin:10px 0 2px}
[data-testid="stMetric"]{border:1px solid var(--sd-border);border-radius:16px;padding:14px 18px;background:var(--sd-surface);box-shadow:var(--sd-shadow-sm)}
div.stButton>button[kind="primary"]{background:var(--sd-brand-strong);border:0;color:var(--sd-on-brand);font-weight:650;border-radius:999px;padding:.55rem 1.4rem;transition:transform .12s,background .12s}
div.stButton>button[kind="primary"]:hover{background:var(--sd-brand);transform:translateY(-1px)}
div.stButton>button[kind="secondary"]{border-radius:999px;border:1px solid var(--sd-border);background:var(--sd-surface)}
div.stButton>button[kind="tertiary"]{color:var(--sd-muted)}
div[data-testid="stExpander"]{border:1px solid var(--sd-border);border-radius:14px;background:var(--sd-surface)}
div[data-baseweb="textarea"],[data-testid="stTextAreaRootElement"]{background:var(--sd-surface)!important;border:1px solid var(--sd-border)!important;border-radius:12px!important}
div[data-baseweb="textarea"] textarea{background:transparent!important}
div[data-testid="stForm"] div[data-baseweb="textarea"],div[data-testid="stForm"] [data-testid="stTextAreaRootElement"],div[data-testid="stForm"] [data-testid="stTextAreaRootElement"] *{background:transparent!important;border:0!important;box-shadow:none!important}
[data-testid="stDataFrame"]{border:1px solid var(--sd-border);border-radius:14px;overflow:hidden}
"""
CSS = f"<style>{CSS}</style>"


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def brand_home() -> None:
    st.markdown('<div class="brand big"><span>Suggest</span><span class="mark">IQ</span></div>'
                '<div class="tagline">Guiding enterprises from questions to decisions</div>', unsafe_allow_html=True)


def brand_small() -> None:
    st.markdown('<div class="brand small"><span>Suggest</span><span class="mark">IQ</span></div>', unsafe_allow_html=True)


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
