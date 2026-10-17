# Future scope (DO NOT BUILD NOW)

**Retail market-basket recommender for online checkout** (second task in `resources/SJSU_CMPE256_Hackathon_20261017_v7_Release.pdf`, data in `resources/Retail.zip`).

Summary: cart starts empty; each added item updates a ranked list of items frequently bought together (association rules / co-occurrence / item-based CF over `CMPE256_Hackathon_market_basket_analysis_Release.csv`, ~1000 transactions, up to 5 items each); if the cart combination has no historical pattern, show no recommendation instead of irrelevant ones; deployable as FastAPI; plan validation, monitoring, retraining.

Start only after the consulting platform passes `make test-all` and the evaluation is recorded. Idea: reuse it as another recommender behind `core.interfaces`.
