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
    """One sticky bar: logo | segmented switch (Consulting / Retail / Evaluation) | status chip, cart badge and page action.

    active: 'consult' | 'eval' | 'retail'. The layout is identical on every page so nothing jumps between screens.
    """
    with st.container(key="topnav"):
        left, mid, right = st.columns([2.4, 5, 3.4], vertical_alignment="center")
        with left:
            theme.brand_small()
        with mid:
            with st.container(horizontal=True, horizontal_alignment="center", key="navgroup", gap="xxsmall"):
                st.button("Consulting", key="nav_consult", icon=":material/psychology_alt:", on_click=_go_consulting, width="content",
                          type="primary" if active == "consult" else "secondary")
                st.button("Retail", key="nav_retail", icon=":material/storefront:", on_click=_go_retail, width="content",
                          type="primary" if active == "retail" else "secondary")
                if show_eval:
                    st.button("Evaluation", key="nav_eval", icon=":material/monitoring:", on_click=_go_eval, width="content",
                              type="primary" if active == "eval" else "secondary")
        with right:
            with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", key="navright"):
                if active == "retail":
                    n = len(st.session_state.get("retail_cart", []))
                    st.markdown(f'<div class="navchip">{theme.pill(f"Cart: {n} item" + ("" if n == 1 else "s"), T.BRAND if n else T.MUTED)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="navchip">{status_chip()}</div>', unsafe_allow_html=True)
                if action:
                    label, icon, cb = action
                    st.button(label, key="nav_action", icon=icon, on_click=cb, width="content")
