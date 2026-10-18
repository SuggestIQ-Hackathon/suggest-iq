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
from retail_basket.icons import icon_svg
from retail_basket.model import evidence_level
from retail_basket.service import RecommenderService

esc = theme.esc


@st.cache_resource(show_spinner=False)
def get_service() -> RecommenderService:
    return RecommenderService()


PAGE = 12  # products per page: 4 columns x 3 rows
SORTS = ["Featured", "Most bought", "Name A to Z"]
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


def goto_page(n: int) -> None:
    st.session_state["retail_page"] = n


def reset_paging() -> None:
    st.session_state["retail_page"] = 1


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


def _product_card(item, in_cart: bool, bought: int) -> str:
    flag = '<div class="pflag">In cart</div>' if in_cart else ""
    return (f'<div class="pcard">{flag}<div class="pop">{bought} orders</div><div class="pimg">{icon_svg(item.category)}</div>'
            f'<div class="pbrand">{esc(item.brand)}</div><div class="pname">{esc(item.name)}</div>'
            f'<div class="pmeta">SKU {esc(item.sku)}</div><div class="pmeta" style="margin-top:1px">{esc(item.category)}</div></div>')


def _sorted(items, svc, how: str):
    if how == "Most bought":
        return sorted(items, key=lambda i: (-svc.model.item_count.get(i.sku, 0), i.name))
    if how == "Name A to Z":
        return sorted(items, key=lambda i: i.name.lower())
    return sorted(items, key=lambda i: (CATEGORIES.index(i.category) if i.category in CATEGORIES else 99, i.name))


def render_pager(total_pages: int, page: int) -> None:
    if total_pages <= 1:
        return
    nums = list(range(1, total_pages + 1))
    cols = st.columns([4, 2.3] + [0.9] * len(nums) + [2.3, 4], vertical_alignment="center")
    cols[1].button("Previous", key="pg_prev", icon=":material/chevron_left:", on_click=goto_page, args=(page - 1,), disabled=page <= 1, width="stretch")
    for col, n in zip(cols[2:2 + len(nums)], nums):
        col.button(str(n), key=f"pg_{n}", on_click=goto_page, args=(n,), type="primary" if n == page else "secondary", width="stretch")
    cols[2 + len(nums)].button("Next", key="pg_next", icon=":material/chevron_right:", icon_position="right", on_click=goto_page, args=(page + 1,),
                               disabled=page >= total_pages, width="stretch")


def render_browser(svc: RecommenderService) -> None:
    top = st.columns([2.2, 1], vertical_alignment="center")
    top[0].text_input("Search products", key="retail_search", placeholder="Search by name, brand or SKU", icon=":material/search:",
                      label_visibility="collapsed", on_change=reset_paging)
    how = top[1].selectbox("Sort", SORTS, key="retail_sort", label_visibility="collapsed", on_change=reset_paging)
    cats = ["All"] + [c for c in CATEGORIES if any(i.category == c for i in svc.catalog.values())]
    pick = st.pills("Category", cats, default="All", key="retail_cat", label_visibility="collapsed", on_change=reset_paging) or "All"
    q = (st.session_state.get("retail_search") or "").strip().lower()
    items = _sorted([i for i in svc.catalog.values()
                     if (pick == "All" or i.category == pick) and (not q or q in i.name.lower() or q in i.sku.lower() or q in i.brand.lower())], svc, how)
    total_pages = max(1, -(-len(items) // PAGE))
    page = min(max(1, st.session_state.get("retail_page", 1)), total_pages)
    st.session_state["retail_page"] = page
    first, last = (page - 1) * PAGE, min(page * PAGE, len(items))
    st.markdown(f'<div class="resultsbar"><span>{"Showing " + str(first + 1) + " to " + str(last) + " of " + str(len(items)) + " products" if items else "No products"}'
                f'{" in " + esc(pick) if pick != "All" else ""}</span><span>Page {page} of {total_pages}</span></div>', unsafe_allow_html=True)
    cart = _cart()
    if not items:
        st.markdown('<div class="card"><b>No products match.</b><div class="meta">Try a different search or category.</div></div>', unsafe_allow_html=True)
    page_items = items[first:last]
    for row in range(0, len(page_items), 4):
        cols = st.columns(4)
        for col, item in zip(cols, page_items[row:row + 4]):
            with col:
                st.markdown(_product_card(item, item.sku in cart, svc.model.item_count.get(item.sku, 0)), unsafe_allow_html=True)
                if item.sku in cart:
                    st.button("", key=f"add_{item.sku}", icon=":material/remove_shopping_cart:", help="Remove from cart", on_click=remove_item, args=(item.sku,))
                else:
                    st.button("", key=f"add_{item.sku}", icon=":material/add_shopping_cart:", help="Add to cart", on_click=add_item, args=(item.sku,), type="primary")
    render_pager(total_pages, page)


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
    left, right = st.columns([7.4, 3.6], gap="large")
    with left:
        render_browser(svc)
    with right:
        st.markdown('<div class="cart-anchor"></div>', unsafe_allow_html=True)
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
    st.markdown('<h3 style="margin:.2rem 0 .6rem!important">Monitoring and retraining</h3>', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        theme.tile("Requests served", str(m["requests"]), "since the app started")
    with cols[1]:
        theme.tile("No-pattern rate", f"{100 * m['no_pattern_rate']:.0f}%", "carts the model declined to answer")
    with cols[2]:
        theme.tile("Avg latency", f"{m['avg_latency_ms']:.2f} ms", "per recommendation")
    with cols[3]:
        theme.tile("Orders waiting", str(m["pending_orders"]), "placed at checkout, not yet learned", T.WARNING if m["pending_orders"] else T.SUCCESS)
    st.markdown('<div class="gap"></div>', unsafe_allow_html=True)
    st.button("Retrain now", key="retail_retrain", icon=":material/model_training:", on_click=_retrain, disabled=m["pending_orders"] == 0)
    done = st.session_state.pop("retail_retrained", None)
    if done:
        st.markdown(f'<div class="summary">Retrained: model v{done["model_version"]} now learns from {done["n_orders"]} orders.</div>', unsafe_allow_html=True)


def _bar_chart(df, value, title, ci=None):
    import altair as alt

    domain = [0, max(0.4, float(df[value].max()) * 1.3)]
    base = alt.Chart(df, title=title).encode(x=alt.X("Method:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelLimit=140)),
                                            color=alt.Color("Method:N", legend=None, scale=alt.Scale(domain=list(df["Method"]), range=[T.BRAND, T.MUTED, T.SUBTLE, T.SUBTLE][:len(df)])))
    bars = base.mark_bar(cornerRadiusEnd=6).encode(y=alt.Y(f"{value}:Q", scale=alt.Scale(domain=domain), title=None, axis=alt.Axis(format="%")),
                                                   tooltip=["Method", alt.Tooltip(f"{value}:Q", format=".1%")])
    text = base.mark_text(dy=-18, fontWeight="bold", color=T.INK).encode(y=f"{value}:Q", text=alt.Text(f"{value}:Q", format=".1%"))
    layers = bars + text
    if ci is not None:
        err = alt.Chart(ci).mark_errorbar(color=T.INK, thickness=2).encode(x=alt.X("Method:N", sort=None), y=alt.Y("low:Q", title=None), y2="high:Q")
        layers = layers + err
    return layers.properties(height=250)


def render_quality() -> None:
    import pandas as pd

    top = st.columns([4, 1.4], vertical_alignment="center")
    top[0].markdown('<h3 style="margin:0!important">Model quality</h3><div class="meta">Does "customers also bought" actually predict what people buy next? '
                    "5-fold cross-validation over past orders.</div>", unsafe_allow_html=True)
    if top[1].button("Run evaluation now", key="retail_eval_run", icon=":material/refresh:", width="stretch"):
        with st.spinner("Cross-validating..."):
            res = evaluate.run(do_sweep=False)
            evaluate.OUT.parent.mkdir(parents=True, exist_ok=True)
            evaluate.OUT.write_text(json.dumps(res, indent=2))
    res = _load_eval()
    if not res:
        st.info("No evaluation yet. Click **Run evaluation now** or run `make retail-eval`.")
        render_monitoring()
        return
    k, cv, sc = res["k"], res["cross_validation"], res.get("signal_check")
    m, pop, rnd = cv["model"], cv["popularity"], cv["random"]

    if sc:
        kind = "warn" if sc["looks_random"] else "good"
        st.markdown(f'<div class="qhero {kind}"><h3>{"Verdict: this dataset has no real bought-together pattern" if sc["looks_random"] else "Verdict: a real bought-together signal exists"}</h3>'
                    f'<div>{esc(sc["verdict"])}</div><div class="meta" style="margin-top:8px">Most frequent item pair: {sc["observed_max_pair_count"]} orders. '
                    f'The same baskets shuffled at random give {sc["shuffled_max_pair_count_range"][0]} to {sc["shuffled_max_pair_count_range"][1]}. '
                    f'Unusual pairs: {sc["pairs_with_z_gt_3"]} (chance alone predicts {sc["pairs_with_z_gt_3_expected_by_chance"]}).</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="gap"></div>', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        theme.tile("Market-basket model", f"{100 * m[f'hit@{k}']:.1f}%", f"hit@{k} on all carts", T.BRAND)
    with cols[1]:
        theme.tile("Most popular items", f"{100 * pop[f'hit@{k}']:.1f}%", f"hit@{k} on all carts", T.MUTED)
    with cols[2]:
        theme.tile("Random items", f"{100 * rnd[f'hit@{k}']:.1f}%", f"hit@{k} on all carts", T.SUBTLE)
    with cols[3]:
        theme.tile("Carts answered", f"{100 * m['coverage']:.0f}%", "the rest correctly show nothing")

    st.markdown('<div class="gap"></div>', unsafe_allow_html=True)
    names = {"model": "Market-basket", "popularity": "Popular", "random": "Random"}
    all_df = pd.DataFrame({"Method": [names[x] for x in names], "hit": [cv[x][f"hit@{k}"] for x in names]})
    ci = pd.DataFrame({"Method": [names[x] for x in names], "low": [cv[x][f"hit@{k}_ci95"][0] for x in names], "high": [cv[x][f"hit@{k}_ci95"][1] for x in names]})
    cov_names = {"model": "Market-basket", "popularity_on_model_covered_carts": "Popular (same carts)"}
    cov_df = pd.DataFrame({"Method": list(cov_names.values()), "hit": [cv[x][f"hit@{k}_covered"] if x == "model" else cv[x][f"hit@{k}"] for x in cov_names]})
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(_bar_chart(all_df, "hit", f"Hit@{k} on ALL carts (declining to answer counts as a miss)", ci), width="stretch")
    with c2:
        st.altair_chart(_bar_chart(cov_df, "hit", f"Hit@{k} on the carts the model DID answer", None), width="stretch")
    lo, hi = m[f"hit@{k}_ci95"]
    st.caption(f"A hit means a recommended item is bought later in the same order. Error bars are 95% confidence intervals (model: {100 * lo:.1f}% to {100 * hi:.1f}%). "
               "Bars that overlap mean the difference is not meaningful.")

    st.divider()
    render_monitoring()
    with st.expander("Detailed numbers and threshold sweep"):
        rows = []
        for key, label in {"model": "Market-basket model", "popularity": "Most popular items", "random": "Random items", "popularity_on_model_covered_carts": "Most popular (same carts the model answered)"}.items():
            r = cv[key]
            rows.append({"Method": label, "Coverage": r["coverage"], f"Hit@{k} (all carts)": r[f"hit@{k}"], f"Hit@{k} (answered carts)": r[f"hit@{k}_covered"],
                         f"Precision@{k}": r[f"precision@{k}"], f"NDCG@{k}": r[f"ndcg@{k}"]})
        fmt = {c: st.column_config.ProgressColumn(c, min_value=0, max_value=1, format="percent") for c in rows[0] if c not in ("Method", f"NDCG@{k}")}
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config=fmt)
        if res.get("sweep"):
            st.dataframe(pd.DataFrame(res["sweep"]), hide_index=True, width="stretch")


def render() -> None:
    from p4_eval_ui.ui import nav

    svc = get_service()
    st.markdown('<div class="retail-root"></div>', unsafe_allow_html=True)
    nav.render_navbar("retail", show_eval=False)
    st.markdown('<div class="meta" style="margin:-.2rem 0 .6rem">Retail checkout · market-basket recommendations</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Checkout", "Model quality"])
    with tabs[0]:
        render_checkout(svc)
    with tabs[1]:
        render_quality()
