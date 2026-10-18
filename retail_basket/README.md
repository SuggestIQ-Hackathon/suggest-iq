# Retail market-basket recommender

Second task in the hackathon brief: recommend items "frequently bought together" while a customer fills an online checkout cart.
Reached from the Suggest IQ home page with **Switch to Retail Checkout (market basket)**, or directly at `http://localhost:8501/?app=retail&cart=D7050`.

## How it works (`model.py`)
For a cart C, take the past orders that contain **every** item in C, then rank the other items by
`confidence = orders with C and item / orders with C`, filtered by `lift = confidence / overall popularity of the item >= 1`.
The cart changes after every click, so the ranking is recomputed each time.
**Unseen or rare combinations show nothing** (`status: no_pattern`) rather than irrelevant items: the cart combination needs >= 5 past orders
and the pairing >= 2. Optional `backoff` (off by default) tries the cart minus one item and labels the result "partial".

## Run it
| What | Command |
|---|---|
| App (toggle on the home page) | `python -m p4_eval_ui.ui.launch` |
| REST service | `make retail-api` -> `POST http://localhost:8001/recommend {"cart": ["D7050"], "k": 5}` |
| Evaluation | `make retail-eval` (writes `data/eval/retail.json`, shown in the app's **Model quality** tab) |
| Tests | `make test-retail` (also part of `make test-all`) |

API: `POST /recommend`, `GET /items`, `GET /health`, `GET /metrics` (requests, no-pattern rate, latency: monitoring), `POST /retrain` (reload the orders and refit: periodic retraining).
Items may be given as SKU (`D7050`) or full name. Unknown items return 422; an empty cart returns `empty_cart`.

## Evaluation (`evaluate.py`): what we found
5-fold cross-validation over the 1,000 orders; each held-out order is replayed as a checkout (first items = cart, the rest = what the customer buys next); a hit means a recommended item is bought later in the same order.
Result with k=5 (rounded):

| | coverage | hit@5 (all carts) | hit@5 (carts answered) |
|---|---|---|---|
| Market-basket model | 56% | 14% | 25% |
| Most popular items | 100% | 23% | 23% |
| Random items | 100% | 25% | 25% |

**The model does not beat the baselines on this dataset, and no model could.** The dataset has 40 products that are each bought about 100 times, and 778 of the 780 possible pairs occur.
The most frequent pair appears 16 times; the same baskets re-drawn at random give 13 to 18. Only 2 pairs are unusually frequent (chance predicts about 1), and there is no brand clustering.
So the orders are statistically indistinguishable from random baskets (`signal_check`). The pipeline is validated on synthetic data that does contain bundles (`tests/test_evaluate.py`: the model beats popularity by a wide margin there).
With real purchase data, `make retail-eval` will show the lift. Treat the recommendations on this data as a demonstration of the system, not as insight about these customers.
