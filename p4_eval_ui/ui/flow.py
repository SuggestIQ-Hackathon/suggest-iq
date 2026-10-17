"""Animated request-flow diagram. Owner: P4.

build_flow_html(trace) -> a self-contained HTML document (inline SVG, SMIL packets) for st.components.v1.html.
`trace` is ConsultingReport.audit_trace (or None for the idle architecture view). Read-only over the trace.
Reads: routing.domains, agents[domain].{status, uncertainty, latency_ms, real_or_mock, error}, total_ms, mode.
"""
from html import escape
from typing import Any, Dict, Optional

from p4_eval_ui.ui import tokens as T

DOMAINS = [  # (value, label, knowledge sources, colour)
    ("technology", "Technology agent", "Cisco · Google", T.DOMAIN_COLOR["technology"]),
    ("clinical", "Clinical agent", "Agilent · papers · trials", T.DOMAIN_COLOR["clinical"]),
    ("sec", "SEC agent", "Cisco · Agilent · Alphabet filings", T.DOMAIN_COLOR["sec"]),
    ("corporate_responsibility", "Corp. Responsibility agent", "FAO food-security reports", T.DOMAIN_COLOR["corporate_responsibility"]),
]
STATUS_COLOR = T.STATUS_COLOR
PURPLE = T.BRAND_STRONG  # system nodes (Manager, Synthesizer) use the brand colour
SHORT_STATUS = {"ANALYSIS_COMPLETE": "Complete", "HYPOTHESIS": "Hypothesis", "INFORMATION_REQUEST": "Needs info", "CONFIRMED_FAULT": "Confirmed fault"}
CYCLE = 8  # seconds per loop

_AGENT_X, _AGENT_W, _AGENT_H = 520, 200, 74
_AGENT_Y = [24, 132, 240, 348]
_MGR_OUT = (410, 214)
_SYN_IN = (800, 190)


def _fan_path(i: int) -> str:
    cy = _AGENT_Y[i] + _AGENT_H / 2
    return f"M{_MGR_OUT[0]},{_MGR_OUT[1]} C465,{_MGR_OUT[1]} 465,{cy} {_AGENT_X},{cy}"


def _merge_path(i: int) -> str:
    cy = _AGENT_Y[i] + _AGENT_H / 2
    x = _AGENT_X + _AGENT_W
    return f"M{x},{cy} C760,{cy} 760,{_SYN_IN[1]} {_SYN_IN[0]},{_SYN_IN[1]}"


def _packet(path: str, color: str, t0: float, t1: float, r: int = 6) -> str:
    """A dot that travels `path` only during [t0, t1] of each cycle (fractions of CYCLE)."""
    e = 0.002
    return (
        f'<circle r="{r}" fill="{color}" stroke="{T.SURFACE}" stroke-width="1.5" opacity="0">'
        f'<animateMotion dur="{CYCLE}s" repeatCount="indefinite" path="{path}" calcMode="linear" '
        f'keyPoints="0;0;1;1" keyTimes="0;{t0};{t1};1"/>'
        f'<animate attributeName="opacity" dur="{CYCLE}s" repeatCount="indefinite" '
        f'values="0;0;1;1;0;0" keyTimes="0;{t0};{t0 + e};{t1};{t1 + e};1"/></circle>'
    )


def _node(x, y, w, h, stroke, dash=False, opacity=1.0, rx=10, fill_op=0.07, light=True) -> str:
    d = ' stroke-dasharray="6 4"' if dash else ""
    fill = f'fill="{T.SURFACE}"' if light else f'fill="currentColor" fill-opacity="{fill_op}"'
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" {fill} '
            f'stroke="{stroke}" stroke-width="2"{d} opacity="{opacity}"/>')


def _text(x, y, s, size=13, weight=400, anchor="start", opacity=1.0, fill="currentColor") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
            f'fill="{fill}" opacity="{opacity}">{escape(str(s))}</text>')


def build_flow_html(trace: Optional[Dict[str, Any]] = None, dark: Optional[bool] = None) -> str:
    def node(*a, **k):
        return _node(*a, light=(dark is not True), **k)

    idle = not trace
    trace = trace or {}
    routed = [str(getattr(d, "value", d)) for d in (trace.get("routing") or {}).get("domains", [])]
    agents = trace.get("agents") or {}
    parts = ['<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>']

    # ---- static structure: edges first so nodes sit on top ----
    parts.append(f'<line x1="150" y1="{_MGR_OUT[1]}" x2="198" y2="{_MGR_OUT[1]}" stroke="currentColor" stroke-width="2" marker-end="url(#arr)"/>')
    parts.append(_text(174, 200, "query", 11, anchor="middle", opacity=0.75))
    for i, (val, _label, _src, color) in enumerate(DOMAINS):
        active = idle or val in routed
        op = 1.0 if active else 0.22
        stroke = color if (active and not idle) else "currentColor"
        dash = "" if (active and not idle) else ' stroke-dasharray="5 5"'
        sw = 2.6 if (active and not idle) else 1.6
        parts.append(f'<path d="{_fan_path(i)}" fill="none" stroke="{stroke}" stroke-width="{sw}" opacity="{op if not idle else 0.35}"{dash} marker-end="url(#arr)"/>')
        parts.append(f'<path d="{_merge_path(i)}" fill="none" stroke="{stroke}" stroke-width="{sw}" opacity="{op if not idle else 0.35}"{dash} marker-end="url(#arr)"/>')
    parts.append(f'<line x1="890" y1="250" x2="890" y2="338" stroke="currentColor" stroke-width="2" marker-end="url(#arr)"/>')
    parts.append(_text(900, 298, "assemble report", 11, opacity=0.75))
    parts.append(_text(465, 8, "sub-queries, in parallel", 11, 600, "middle", opacity=0.8))
    parts.append(_text(760, 8, "DomainResponse + citations", 11, 600, "middle", opacity=0.8))

    # ---- nodes ----
    parts.append(node(20, 174, 130, 80, "currentColor", fill_op=0.1))
    parts += [_text(85, 208, "Customer", 14, 600, "middle"), _text(85, 227, "question", 14, 600, "middle"),
              _text(85, 244, "+ optional logs", 11, anchor="middle", opacity=0.7)]
    parts.append(node(200, 40, 210, 350, PURPLE, fill_op=0.05, rx=14))
    parts.append(_text(305, 62, "Manager Agent", 14, 700, "middle", fill=PURPLE))
    for k, (title, sub) in enumerate([("1  Intent router", "classify, multi-label"), ("2  Query decomposer", "one sub-query per domain"),
                                      ("3  Async dispatcher", "run agents concurrently")]):
        y = 92 + k * 96
        parts.append(node(214, y, 182, 76, PURPLE, fill_op=0.08, rx=8))
        parts += [_text(305, y + 32, title, 13, 600, "middle"), _text(305, y + 52, sub, 11, anchor="middle", opacity=0.7)]
    for k in range(2):  # arrows between manager steps
        y = 92 + k * 96 + 76
        parts.append(f'<line x1="305" y1="{y}" x2="305" y2="{y + 20}" stroke="{PURPLE}" stroke-width="2" marker-end="url(#arr)"/>')
    if trace.get("routing"):
        conf = trace["routing"].get("confidence")
        parts.append(_text(305, 372, f"router confidence {conf}" if conf is not None else "", 11, anchor="middle", opacity=0.8))

    for i, (val, label, src, color) in enumerate(DOMAINS):
        y = _AGENT_Y[i]
        a = agents.get(val, {})
        active = idle or val in routed
        mock = a.get("real_or_mock") == "mock"
        parts.append(f'<g opacity="{1.0 if active else 0.3}"><title>{escape(label)}: {escape(src)}</title>')
        parts.append(node(_AGENT_X, y, _AGENT_W, _AGENT_H, color, dash=mock, fill_op=0.1))
        parts.append(f'<rect x="{_AGENT_X}" y="{y}" width="6" height="{_AGENT_H}" rx="3" fill="{color}"/>')
        parts.append(_text(_AGENT_X + 16, y + 22, label.replace(" agent", ""), 13, 700))
        parts.append(_text(_AGENT_X + 16, y + 39, src, 10.5, opacity=0.75))
        if a:
            sc = STATUS_COLOR.get(a.get("status", ""), T.DANGER if a.get("error") else T.MUTED)
            parts.append(f'<circle cx="{_AGENT_X + 20}" cy="{y + 57}" r="4.5" fill="{sc}"/>')
            tag = f'{SHORT_STATUS.get(a.get("status", ""), a.get("status", "?"))} · {a.get("latency_ms", "?")} ms'
            parts.append(_text(_AGENT_X + 30, y + 61, tag, 10.5))
            if mock:
                parts.append(f'<rect x="{_AGENT_X + _AGENT_W - 44}" y="{y + 6}" width="38" height="16" rx="8" fill="currentColor" fill-opacity="0.15"/>')
                parts.append(_text(_AGENT_X + _AGENT_W - 25, y + 18, "MOCK", 9.5, 700, "middle"))
        elif idle:
            parts.append(_text(_AGENT_X + 16, y + 61, "retrieve · rank · cite", 10.5, opacity=0.6))
        parts.append("</g>")

    parts.append(node(_SYN_IN[0], 150, 180, 100, PURPLE, fill_op=0.1, rx=14))
    parts += [_text(890, 182, "Synthesizer", 14, 700, "middle", fill=PURPLE), _text(890, 202, "merge + rank", 11.5, anchor="middle", opacity=0.8),
              _text(890, 218, "trade-offs · next steps", 11.5, anchor="middle", opacity=0.8), _text(890, 234, "KPIs", 11.5, anchor="middle", opacity=0.8)]
    parts.append(node(_SYN_IN[0], 340, 180, 66, "currentColor", fill_op=0.1))
    parts += [_text(890, 368, "Consulting report", 14, 700, "middle"), _text(890, 387, "evidence · actions · KPIs", 11, anchor="middle", opacity=0.75)]

    # ---- packets (the request travelling) ----
    q_color = T.SUBTLE if idle else PURPLE
    parts.append(_packet(f"M150,{_MGR_OUT[1]} L198,{_MGR_OUT[1]}", q_color, 0.02, 0.10))
    for i, (val, _l, _s, color) in enumerate(DOMAINS):
        if idle:
            parts.append(_packet(_fan_path(i), T.SUBTLE, 0.22, 0.38))
            parts.append(_packet(_merge_path(i), T.SUBTLE, 0.52, 0.68))
        elif val in routed:
            parts.append(_packet(_fan_path(i), color, 0.22, 0.38))
            st = agents.get(val, {}).get("status", "")
            parts.append(_packet(_merge_path(i), STATUS_COLOR.get(st, color), 0.52, 0.68))
    parts.append(_packet("M890,250 L890,338", T.SUBTLE if idle else PURPLE, 0.74, 0.86))

    if idle:
        caption = "Idle view: every agent is shown. Run a consultation to see the real path your question took."
    else:
        names = ", ".join(d.replace("_", " ") for d in routed) or "no agent"
        caption = (f"Your question went to {names} in parallel (total {trace.get('total_ms', '?')} ms, mode {trace.get('mode', '?')}); "
                   "dot colour on the way back = that agent's status. Dashed boxes are mock agents.")
    legend = "".join(f'<span class="k"><i style="background:{c}"></i>{escape(s.replace("_", " ").title())}</span>' for s, c in STATUS_COLOR.items())
    aria = escape(caption)
    media = "@media (prefers-color-scheme: dark){html,body{color:" + T.INK_ON_DARK + "}}" if dark is None else ""
    ink = T.INK_ON_DARK if dark else T.INK
    if dark is None:  # follow the browser when the host theme is unknown
        ink = T.INK
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{{margin:0;background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:{ink}}}
{media}
figure{{margin:0;padding:8px 4px}}
.wrap{{overflow-x:auto}}
svg{{width:100%;min-width:760px;max-width:1000px;height:auto;display:block;margin:0 auto}}
.ctl{{display:flex;gap:8px;justify-content:flex-end;padding:0 8px}}
.ctl button{{font:inherit;font-size:12px;border:1px solid rgba(128,128,128,.5);background:transparent;color:inherit;border-radius:8px;padding:3px 12px;cursor:pointer}}
figcaption{{font-size:13px;opacity:.85;padding:6px 8px 0}}
.legend{{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;opacity:.85;padding:4px 8px}}
.k i{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}}
</style></head><body><figure>
<div class="ctl"><button id="pp" type="button">Pause</button><button id="rp" type="button">Replay</button></div>
<div class="wrap"><svg id="flow" viewBox="0 -14 1000 454" role="img" aria-label="{aria}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif">
{''.join(parts)}
</svg></div>
<div class="legend">{legend}</div>
<figcaption>{escape(caption)}</figcaption></figure>
<script>
var svg=document.getElementById("flow"),pp=document.getElementById("pp"),paused=false;
pp.onclick=function(){{paused=!paused;paused?svg.pauseAnimations():svg.unpauseAnimations();pp.textContent=paused?"Play":"Pause";}};
document.getElementById("rp").onclick=function(){{svg.setCurrentTime(0);if(paused){{svg.unpauseAnimations();paused=false;pp.textContent="Pause";}}}};
</script></body></html>"""
