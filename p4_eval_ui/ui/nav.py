"""Top navigation bar shared by every screen. Owner: P4.

Left: Suggest IQ wordmark. Middle: the app switch (Consulting / Retail) and, inside Consulting, Evaluation. Right: model status chip and an
optional page action (e.g. "New question"). The active destination is the filled button.
"""
import os
from typing import Callable, Optional, Tuple

import streamlit as st

from core import llm
from p4_eval_ui.ui import theme
from p4_eval_ui.ui import tokens as T

Action = Tuple[str, str, Callable[[], None]]  # (label, material icon, on_click)


def _go_consulting() -> None:
    st.session_state["app"] = "consult"
    if st.session_state.get("view") == "eval":  # leave the evaluation page, back to wherever the user was
        st.session_state["view"] = "result" if st.session_state.get("report") is not None else "home"


def _go_retail() -> None:
    st.session_state["app"] = "retail"


def _go_eval() -> None:
    st.session_state["app"] = "consult"
    st.session_state["view"] = "eval"


def status_chip() -> str:
    mode = llm.llm_mode()
    color = T.SUCCESS if mode == "live" else T.WARNING
    return theme.pill(f"LLM {mode}", color)


def render_navbar(active: str, show_eval: bool = True, action: Optional[Action] = None) -> None:
    """active: 'consult' | 'eval' | 'retail'. The column layout is identical on every page so the buttons never jump."""
    cols = st.columns([2.2, 1.55, 1.35, 1.55, 2.9], vertical_alignment="center")
    with cols[0]:
        theme.brand_small()
    cols[1].button("Consulting", key="nav_consult", icon=":material/psychology_alt:", on_click=_go_consulting, width="stretch",
                   type="primary" if active == "consult" else "secondary")
    cols[2].button("Retail", key="nav_retail", icon=":material/storefront:", on_click=_go_retail, width="stretch",
                   type="primary" if active == "retail" else "secondary")
    if show_eval:
        cols[3].button("Evaluation", key="nav_eval", icon=":material/monitoring:", on_click=_go_eval, width="stretch",
                       type="primary" if active == "eval" else "secondary")
    with cols[4]:
        if action:
            sub = st.columns([1, 1.25], vertical_alignment="center")
            sub[0].markdown(f'<div class="navchip">{status_chip()}</div>', unsafe_allow_html=True)
            label, icon, cb = action
            sub[1].button(label, key="nav_action", icon=icon, on_click=cb, width="stretch")
        else:
            st.markdown(f'<div class="navchip">{status_chip()}</div>', unsafe_allow_html=True)
