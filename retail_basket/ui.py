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
from retail_basket.service import RecommenderService

esc = theme.esc


@st.cache_resource(show_spinner=False)
def get_service() -> RecommenderService:
    return RecommenderService()


def _cart() -> list:
    return st.session_state.setdefault("retail_cart", [])


def add_item(sku: str) -> None:
    cart = _cart()
    if sku and sku not in cart:
        cart.append(sku)


def remove_item(sku: str) -> None:
    cart = _cart()
    if sku in cart:
        cart.remove(sku)


def clear_cart() -> None:
    st.session_state["retail_cart"] = []


def back_to_consulting() -> None:
    st.session_state["app"] = "consult"


def _add_selected(names_to_sku: dict) -> None:
    choice = st.session_state.get("retail_pick")
    if choice in names_to_sku:
        add_item(names_to_sku[choice])
        st.session_state["retail_pick"] = None


def _label(item) -> str:
    return f"{item.name} ({item.sku})"


def render_checkout(svc: RecommenderService) -> None:
    labels = {_label(i): sku for sku, i in sorted(svc.catalog.items(), key=lambda kv: kv[1].name)}
    left, right = st.columns([5, 4], gap="large")
    cart = _cart()

    with left:
        st.subheader("Your cart")
        with st.container(border=True):
            st.selectbox("Add a product", options=list(labels), index=None, key="retail_pick", placeholder="Search products by name or SKU...",
                         label_visibility="collapsed")
            st.button("Add to cart", type="primary", key="retail_add", on_click=_add_selected, args=(labels,), disabled=not st.session_state.get("retail_pick"))
        if not cart:
            st.markdown('<div class="card"><b>Your cart is empty.</b><div class="meta">Add a product to see what other customers bought with it.</div></div>', unsafe_allow_html=True)
        for sku in cart:
            item = svc.catalog[sku]
            c = st.columns([7, 2], vertical_alignment="center")
            c[0].markdown(f'<div class="step"><div><b>{esc(item.name)}</b><div class="meta">SKU {esc(sku)} · {esc(item.brand)}</div></div></div>', unsafe_allow_html=True)
            c[1].button("Remove", key=f"rm_{sku}", on_click=remove_item, args=(sku,), width="stretch")
        if cart:
            st.button("Clear cart", key="retail_clear", on_click=clear_cart, type="tertiary")

    with right:
        st.subheader("Recommended for this cart")
        result = svc.recommend(cart, 5)
        if result.status == "empty_cart":
            st.markdown(f'<div class="card"><div class="meta">{esc(result.message)}</div></div>', unsafe_allow_html=True)
        elif result.status == "no_pattern":
            st.markdown(f'<div class="need"><h4>No reliable pattern for this cart</h4><div class="meta">{esc(result.message)} '
                        'Suggest IQ shows nothing rather than guess.</div></div>', unsafe_allow_html=True)
        else:
            if result.status == "partial":
                st.caption(result.message)
            for rec in result.recs:
                item = svc.catalog[rec.sku]
                c = st.columns([6, 1.6], vertical_alignment="center")
                c[0].markdown(
                    f'<div class="card"><div class="rec-title">{esc(item.name)}</div><div class="meta">SKU {esc(rec.sku)} · {esc(item.brand)}</div>'
                    f'<div class="why">{esc(rec.reason())}</div>'
                    f'<div style="margin-top:6px">{theme.pill(f"{rec.lift:.1f}x lift", T.SUCCESS if rec.lift >= 1.2 else T.MUTED)}</div></div>', unsafe_allow_html=True)
                c[1].button("Add", key=f"rec_{rec.sku}", on_click=add_item, args=(rec.sku,), width="stretch")
        info = svc.info()
        st.caption(f"Model v{info['model_version']} · trained on {info['n_orders']} orders · needs at least {info['config']['min_support']} past orders "
                   "containing the cart before it will recommend.")


def _load_eval():
    p = evaluate.OUT
    return json.loads(p.read_text()) if p.exists() else None


def render_quality() -> None:
    st.subheader("Model quality")
    st.caption("5-fold cross-validation: for every held-out order we treat the first items as the cart and check whether a recommended item is bought later in the same order.")
    if st.button("Run evaluation now", key="retail_eval_run"):
        with st.spinner("Cross-validating..."):
            res = evaluate.run(do_sweep=False)
            evaluate.OUT.parent.mkdir(parents=True, exist_ok=True)
            evaluate.OUT.write_text(json.dumps(res, indent=2))
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
    svc = get_service()
    c = st.columns([5, 2])
    with c[0]:
        theme.brand_small()
        st.markdown('<div class="meta">Retail checkout · market-basket recommendations</div>', unsafe_allow_html=True)
    c[1].button("← Back to Suggest IQ", key="retail_back", on_click=back_to_consulting, width="stretch")
    tabs = st.tabs(["Checkout", "Model quality"])
    with tabs[0]:
        render_checkout(svc)
    with tabs[1]:
        render_quality()
