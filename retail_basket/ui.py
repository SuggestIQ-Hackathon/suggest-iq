"""Streamlit checkout page for the market-basket recommender. Owner: retail_basket.

Reached from the Suggest IQ home page ("Retail checkout" button); st.session_state["app"] == "retail".
The cart updates the recommendations after every change, mirroring the brief's checkout portal.
"""
import json

import pandas as pd
import streamlit as st

from p4_eval_ui.ui import theme
from p4_eval_ui.ui import tokens as T
from retail_basket import evaluate
from retail_basket.data import CATEGORIES
from retail_basket.model import evidence_level
from retail_basket.service import RecommenderService

esc = theme.esc


@st.cache_resource(show_spinner=False)
def get_service() -> RecommenderService:
    return RecommenderService()


PAGE = 9  # products shown per "page" in the browser
LEVEL_COLOR = {"limited": T.WARNING, "moderate": T.INFO, "strong": T.SUCCESS}


def _cart() -> list:
    return st.session_state.setdefault("retail_cart", [])


def add_item(sku: str) -> None:
    cart = _cart()
    if sku and sku not in cart:
        cart.append(sku)
    st.session_state.pop("retail_flash", None)


def remove_item(sku: str) -> None:
    cart = _cart()
    if sku in cart:
        cart.remove(sku)


def clear_cart() -> None:
    st.session_state["retail_cart"] = []


def show_more() -> None:
    st.session_state["retail_show"] = st.session_state.get("retail_show", PAGE) + PAGE


def reset_paging() -> None:
    st.session_state["retail_show"] = PAGE


def place_order() -> None:
    """Demo checkout: log the order (learned at the next retrain), empty the cart and show a confirmation."""
    svc = get_service()
    cart = _cart()
    try:
        skus = svc.log_order(cart)
    except ValueError as err:
        st.session_state["retail_flash"] = ("warn", f"Not saved: {err}.")
        return
    st.session_state["retail_flash"] = ("ok", f"Order placed with {len(skus)} items. It is saved and will be learned from at the next retrain.")
    st.session_state["retail_cart"] = []


def _product_card(item, in_cart: bool) -> str:
    return (f'<div class="card" style="margin:0 0 6px;min-height:176px"><div class="rec-title" style="font-size:.98rem">{esc(item.name)}</div>'
            f'<div class="meta">SKU {esc(item.sku)} · {esc(item.brand)}</div>'
            f'<div style="margin-top:6px">{theme.pill(item.category, T.MUTED, square=True)}</div></div>')


def render_browser(svc: RecommenderService) -> None:
    st.subheader("Browse products")
    st.text_input("Search products", key="retail_search", placeholder="Search by name, brand or SKU", icon=":material/search:",
                  label_visibility="collapsed", on_change=reset_paging)
    cats = ["All"] + [c for c in CATEGORIES if any(i.category == c for i in svc.catalog.values())]
    pick = st.pills("Category", cats, default="All", key="retail_cat", label_visibility="collapsed", on_change=reset_paging) or "All"
    q = (st.session_state.get("retail_search") or "").strip().lower()
    items = [i for i in sorted(svc.catalog.values(), key=lambda i: (CATEGORIES.index(i.category) if i.category in CATEGORIES else 99, i.name))
             if (pick == "All" or i.category == pick) and (not q or q in i.name.lower() or q in i.sku.lower() or q in i.brand.lower())]
    limit = st.session_state.get("retail_show", PAGE)
    cart = _cart()
    if not items:
        st.markdown('<div class="card"><b>No products match.</b><div class="meta">Try a different search or category.</div></div>', unsafe_allow_html=True)
    for row in range(0, min(limit, len(items)), 3):
        cols = st.columns(3)
        for col, item in zip(cols, items[row:min(row + 3, limit)]):
            with col:
                st.markdown(_product_card(item, item.sku in cart), unsafe_allow_html=True)
                if item.sku in cart:
                    st.button("In cart", key=f"add_{item.sku}", icon=":material/check:", disabled=True, width="stretch")
                else:
                    st.button("Add to cart", key=f"add_{item.sku}", icon=":material/add_shopping_cart:", on_click=add_item, args=(item.sku,), width="stretch")
    if len(items) > limit:
        st.button(f"Show {min(PAGE, len(items) - limit)} more of {len(items) - limit} remaining", key="retail_more", on_click=show_more, type="tertiary")
    st.caption(f"{len(items)} of {len(svc.catalog)} products")


def render_cart(svc: RecommenderService) -> None:
    cart = _cart()
    st.subheader(f"Your cart ({len(cart)})")
    flash = st.session_state.pop("retail_flash", None)
    if flash:
        kind, msg = flash
        st.markdown(f'<div class="{"summary" if kind == "ok" else "need"}">{esc(msg)}</div>', unsafe_allow_html=True)
    if not cart:
        st.markdown('<div class="card"><b>Your cart is empty.</b><div class="meta">Add a product, and Suggest IQ shows what customers bought with it.</div></div>', unsafe_allow_html=True)
    for sku in cart:
        item = svc.catalog[sku]
        c = st.columns([7, 1.4], vertical_alignment="center")
        c[0].markdown(f'<div class="step" style="margin:4px 0"><div><b>{esc(item.name)}</b><div class="meta">SKU {esc(sku)} · {esc(item.category)}</div></div></div>', unsafe_allow_html=True)
        c[1].button("", key=f"rm_{sku}", icon=":material/delete:", help="Remove from cart", on_click=remove_item, args=(sku,), width="stretch")
    if cart:
        b = st.columns([1.6, 1])
        b[0].button("Place order (demo)", key="retail_order", type="primary", icon=":material/shopping_cart_checkout:", on_click=place_order, width="stretch",
                    disabled=len(cart) < 2, help="Needs at least 2 items. The order is saved and learned from at the next retrain." if len(cart) < 2 else None)
        b[1].button("Clear", key="retail_clear", icon=":material/remove_shopping_cart:", on_click=clear_cart, width="stretch")


def _rec_card(svc, rec, label: str):
    item = svc.catalog[rec.sku]
    c = st.columns([6, 1.6], vertical_alignment="center")
    c[0].markdown(
        f'<div class="card" style="margin:4px 0"><div class="rec-title" style="font-size:1rem">{esc(item.name)}</div>'
        f'<div class="meta">SKU {esc(rec.sku)} · {esc(item.brand)} · {esc(item.category)}</div>'
        f'<div class="why">{esc(label)}</div></div>', unsafe_allow_html=True)
    c[1].button("Add", key=f"rec_{rec.sku}", icon=":material/add:", on_click=add_item, args=(rec.sku,), width="stretch")


def render_recommendations(svc: RecommenderService) -> None:
    cart = _cart()
    result = svc.recommend(cart, 4)
    if result.status == "empty_cart":
        st.subheader("Customers often start with")
        for sku in svc.popular(3):
            item = svc.catalog[sku]
            c = st.columns([6, 1.6], vertical_alignment="center")
            c[0].markdown(f'<div class="card" style="margin:4px 0"><div class="rec-title" style="font-size:1rem">{esc(item.name)}</div>'
                          f'<div class="meta">SKU {esc(sku)} · {esc(item.category)} · among the most-bought items overall</div></div>', unsafe_allow_html=True)
            c[1].button("Add", key=f"pop_{sku}", icon=":material/add:", on_click=add_item, args=(sku,), width="stretch")
        return
    st.subheader("Customers also bought")
    if result.status == "no_pattern":
        st.markdown(f'<div class="need"><h4>No reliable pattern for this cart</h4><div class="meta">{esc(result.message)} '
                    'Suggest IQ shows nothing rather than guess.</div></div>', unsafe_allow_html=True)
    else:
        level = evidence_level(result.cart_support)
        st.markdown(f'<div style="margin:0 0 6px">{theme.pill(f"{level.title()} evidence: {result.cart_support} past orders contain this cart", LEVEL_COLOR[level])}</div>',
                    unsafe_allow_html=True)
        if level == "limited":
            st.caption("Small samples can show big lifts by chance. Treat these as hints, not proof.")
        if result.status == "partial":
            st.caption(result.message)
        for rec in result.recs:
            _rec_card(svc, rec, f"In {rec.count} of {rec.cart_support} of those orders ({100 * rec.confidence:.0f}%) · {rec.lift:.1f}x more often than average")
    with st.expander("How are these chosen?"):
        st.markdown("Suggest IQ looks only at past orders that contain **every** item in your cart, then ranks the other items by how often they appear in those orders "
                    "(*confidence*) and how much more often than average that is (*lift*). If the cart combination is too rare in history, it recommends nothing.")


def render_checkout(svc: RecommenderService) -> None:
    left, right = st.columns([6, 4.5], gap="large")
    with left:
        render_browser(svc)
    with right:
        render_cart(svc)
        render_recommendations(svc)
        info = svc.info()
        st.caption(f"Model v{info['model_version']} · {info['n_orders']} orders · recommends only when at least {info['config']['min_support']} past orders contain the cart.")


def _load_eval():
    p = evaluate.OUT
    return json.loads(p.read_text()) if p.exists() else None


def _retrain() -> None:
    st.session_state["retail_retrained"] = get_service().retrain()


def render_monitoring() -> None:
    svc = get_service()
    m = svc.metrics()
    st.subheader("Monitoring and retraining")
    cols = st.columns(4)
    with cols[0]:
        theme.tile("Requests served", str(m["requests"]), "since the app started")
    with cols[1]:
        theme.tile("No-pattern rate", f"{100 * m['no_pattern_rate']:.0f}%", "carts the model declined to answer")
    with cols[2]:
        theme.tile("Avg latency", f"{m['avg_latency_ms']:.2f} ms", "per recommendation")
    with cols[3]:
        theme.tile("Orders waiting", str(m["pending_orders"]), "placed at checkout, not yet learned", T.WARNING if m["pending_orders"] else T.SUCCESS)
    st.button("Retrain now", key="retail_retrain", icon=":material/model_training:", on_click=_retrain, disabled=m["pending_orders"] == 0)
    done = st.session_state.pop("retail_retrained", None)
    if done:
        st.markdown(f'<div class="summary">Retrained: model v{done["model_version"]} now learns from {done["n_orders"]} orders.</div>', unsafe_allow_html=True)
    st.divider()


def render_quality() -> None:
    st.subheader("Model quality")
    st.caption("5-fold cross-validation: for every held-out order we treat the first items as the cart and check whether a recommended item is bought later in the same order.")
    if st.button("Run evaluation now", key="retail_eval_run"):
        with st.spinner("Cross-validating..."):
            res = evaluate.run(do_sweep=False)
            evaluate.OUT.parent.mkdir(parents=True, exist_ok=True)
            evaluate.OUT.write_text(json.dumps(res, indent=2))
    render_monitoring()
    res = _load_eval()
    if not res:
        st.info("No evaluation yet. Click **Run evaluation now** or run `make retail-eval`.")
        return
    k = res["k"]
    cv = res["cross_validation"]
    sc = res.get("signal_check")
    if sc:
        box = "need" if sc["looks_random"] else "summary"
        st.markdown(f'<div class="{box}"><h4>What this data can and cannot show</h4><div>{esc(sc["verdict"])}</div>'
                    f'<div class="meta">Most frequent item pair: {sc["observed_max_pair_count"]} orders. The same baskets shuffled at random give '
                    f'{sc["shuffled_max_pair_count_range"][0]} to {sc["shuffled_max_pair_count_range"][1]}. Unusual pairs found: {sc["pairs_with_z_gt_3"]} '
                    f'(chance alone predicts {sc["pairs_with_z_gt_3_expected_by_chance"]}).</div></div>', unsafe_allow_html=True)
    rows = []
    names = {"model": "Market-basket model", "popularity": "Most popular items", "random": "Random items", "popularity_on_model_covered_carts": "Most popular (same carts the model answered)"}
    for key, label in names.items():
        r = cv[key]
        rows.append({"Method": label, "Coverage": r["coverage"], f"Hit@{k} (all carts)": r[f"hit@{k}"], f"Hit@{k} (answered carts)": r[f"hit@{k}_covered"],
                     f"Precision@{k}": r[f"precision@{k}"], f"NDCG@{k}": r[f"ndcg@{k}"]})
    fmt = {c: st.column_config.ProgressColumn(c, min_value=0, max_value=1, format="percent") for c in rows[0] if c not in ("Method", f"NDCG@{k}")}
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config=fmt)
    ci = cv["model"][f"hit@{k}_ci95"]
    st.caption(f"Model hit@{k} 95% confidence interval: {100 * ci[0]:.1f}% to {100 * ci[1]:.1f}%. Coverage is the share of carts the model was willing to answer; "
               "for the rest it correctly shows nothing, which counts as a miss in the 'all carts' column.")
    if res.get("sweep"):
        with st.expander("Threshold sweep"):
            st.dataframe(pd.DataFrame(res["sweep"]), hide_index=True, width="stretch")


def render() -> None:
    from p4_eval_ui.ui import nav

    svc = get_service()
    nav.render_navbar("retail", show_eval=False)
    st.markdown('<div class="meta" style="margin:-.2rem 0 .6rem">Retail checkout · market-basket recommendations</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Checkout", "Model quality"])
    with tabs[0]:
        render_checkout(svc)
    with tabs[1]:
        render_quality()
