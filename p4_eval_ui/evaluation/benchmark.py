"""Benchmark runner. Owner: P4.

    python -m p4_eval_ui.evaluation.benchmark          (or: make eval)

Metrics (None means "no data", never a fabricated number):
  routing_accuracy             exact-set match of detected vs expected domains over all benchmark queries
  retrieval_hit_rate           over (query, expected domain) pairs: does agent.retrieve(query, k) return a chunk whose
                               source_doc / model / vendor / company / section contains any `expected_sources` substring
  recommendation_ndcg_at_3     mean NDCG@3 of consolidated recommendations vs gold_relevance.json (queries with real gold only)
  precision_at_3               same queries, precision@3 (relevant = gain > 0)
  faithfulness                 mean claim-support score from faithfulness.judge (hallucination rate = 1 - score)
  diagnostic_gate_compliance   queries with expected_status=INFORMATION_REQUEST: share where the system asked for diagnostics
                               and recommended no Replacement Part
  out_of_scope_low_confidence_rate   edge_cases.json probes where the router confidence is below the threshold
Retrieval is measured on the original query so it is isolated from routing/decomposition quality.
"""
import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core import llm
from core.registry import REAL_DOMAIN_LIST, get_agents, load_manager
from core.schemas import ConsultingReport, DomainType
from p4_eval_ui.evaluation import faithfulness
from p4_eval_ui.evaluation.explain import calibration_table
from p4_eval_ui.evaluation.metrics import (
    confusion_matrix,
    hit_rate_at_k,
    ndcg_at_k,
    per_label_prf,
    precision_at_k,
    routing_accuracy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERIES = REPO_ROOT / "core" / "fixtures" / "benchmark_queries.json"
GOLD_PATH = Path(__file__).resolve().parent / "gold_relevance.json"
EDGE_PATH = Path(__file__).resolve().parent / "edge_cases.json"
EVAL_DIR = REPO_ROOT / "data" / "eval"
DOMAIN_VALUES = [d.value for d in REAL_DOMAIN_LIST]


def _mean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _source_match(hit, expected: List[str]) -> bool:
    m = hit.chunk.metadata
    hay = " ".join(str(m.get(key, "")) for key in ("source_doc", "model", "vendor", "company", "section", "doc_type")).lower()
    return any(e.lower() in hay for e in expected)


def _load_gold(path: Path) -> Dict[str, Dict[str, float]]:
    """Return {query_id: {item_id: gain}} keeping only queries with at least one non-placeholder id."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {qid: gains for qid, gains in raw.items() if not qid.startswith("_") and any(not i.startswith("TODO-") for i in gains)}


def _agents_of(manager):
    agents = getattr(manager, "agents", None)
    return agents if agents else get_agents()


def run_benchmark(
    manager,
    queries_path: Optional[Path] = None,
    k: int = 5,
    gold_path: Optional[Path] = None,
    edge_path: Optional[Path] = None,
) -> Dict[str, Any]:
    queries = json.loads(Path(queries_path or DEFAULT_QUERIES).read_text())
    gold = _load_gold(Path(gold_path or GOLD_PATH))
    agents = _agents_of(manager)

    per_query: List[Dict[str, Any]] = []
    predicted: List[Set[str]] = []
    expected: List[Set[str]] = []
    pair_retrieved: List[List[str]] = []
    pair_relevant: List[Set[str]] = []
    pair_domain: List[str] = []
    real_seen: Dict[str, Set[str]] = {}

    for item in queries:
        row: Dict[str, Any] = {"id": item["id"], "query": item["query"], "type": item.get("type"),
                               "expected_domains": item["expected_domains"], "error": None}
        report: Optional[ConsultingReport] = None
        try:
            report = manager.handle(item["query"], item.get("context"))
        except Exception as err:  # noqa: BLE001 - a crash is a data point, not a reason to stop the run
            row["error"] = f"{type(err).__name__}: {err}"

        trace = report.audit_trace if report else {}
        routing = trace.get("routing") or {}
        if not routing and report is None:
            try:
                routing = manager.classify(item["query"]).model_dump()
            except Exception:  # noqa: BLE001
                routing = {}
        pred = {d.value if hasattr(d, "value") else str(d) for d in routing.get("domains", [])}
        predicted.append(pred)
        expected.append(set(item["expected_domains"]))
        row.update(predicted_domains=sorted(pred), routing_exact=pred == set(item["expected_domains"]),
                   routing_confidence=routing.get("confidence"), latency_ms=trace.get("total_ms"))
        for d, a in (trace.get("agents") or {}).items():
            real_seen.setdefault(d, set()).add(a.get("real_or_mock", "?"))

        # --- retrieval (original query, per expected domain) ---
        row["retrieval"] = {}
        for dom in item["expected_domains"]:
            agent = agents.get(DomainType(dom))
            try:
                hits = agent.retrieve(item["query"], k) if agent else []
                hit = any(_source_match(h, item["expected_sources"]) for h in hits)
                ids = [h.chunk.metadata.get("source_doc", "") for h in hits if _source_match(h, item["expected_sources"])]
            except Exception as err:  # noqa: BLE001
                row["retrieval"][dom] = {"hit": None, "error": f"{type(err).__name__}: {err}"}
                continue
            row["retrieval"][dom] = {"hit": hit, "n_hits": len(hits)}
            pair_domain.append(dom)
            pair_retrieved.append(ids[:k] or [""])
            pair_relevant.append(set(ids) if hit else {"__none__"})

        if report is not None:
            ranked = [r.item_id for r in report.consolidated_recommendations]
            gains = gold.get(item["id"])
            if gains:
                row["ndcg_at_3"] = ndcg_at_k(ranked, gains, 3)
                row["precision_at_3"] = precision_at_k(ranked, {i for i, g in gains.items() if g > 0}, 3)
                if report.consolidated_recommendations:
                    top = report.consolidated_recommendations[0]
                    row["top_rec_confidence"] = top.confidence_score
                    row["top_rec_relevant"] = gains.get(top.item_id, 0) > 0
            f = faithfulness.judge(report)
            row["faithfulness"] = f["score"]
            row["n_statements"] = f["n_statements"]
            row["unsupported"] = f["unsupported"]
            statuses = {d: r.status for d, r in report.domain_findings.items()}
            row["statuses"] = statuses
            row["uncertainty"] = {d: r.uncertainty_level for d, r in report.domain_findings.items()}
            if item.get("expected_status") == "INFORMATION_REQUEST":
                asked = any(s == "INFORMATION_REQUEST" for s in statuses.values())
                no_parts = not any(r.category == "Replacement Part" for r in report.consolidated_recommendations)
                row["gate_compliant"] = asked and no_parts
        per_query.append(row)

    # --- out-of-scope robustness ---
    edge_file = Path(edge_path or EDGE_PATH)
    oos_rate = None
    if edge_file.exists():
        edge = json.loads(edge_file.read_text())
        flags = []
        for e in edge["queries"]:
            try:
                conf = manager.classify(e["query"]).confidence
                flags.append(conf < edge.get("low_confidence_threshold", 0.5))
            except Exception:  # noqa: BLE001
                flags.append(False)
        oos_rate = sum(flags) / len(flags) if flags else None

    # --- aggregate ---
    gate_rows = [r["gate_compliant"] for r in per_query if "gate_compliant" in r]
    latencies = sorted(r["latency_ms"] for r in per_query if r.get("latency_ms") is not None)
    unc: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for r in per_query:
        for v in (r.get("uncertainty") or {}).values():
            unc[v] = unc.get(v, 0) + 1
    by_domain = {}
    for d in DOMAIN_VALUES:
        flags = [rel != {"__none__"} for dom, rel in zip(pair_domain, pair_relevant) if dom == d]
        by_domain[d] = (sum(flags) / len(flags)) if flags else None
    skipped_todo = sum(1 for qid in json.loads(GOLD_PATH.read_text()) if not qid.startswith("_") and qid not in gold) if GOLD_PATH.exists() else 0
    agents_real = {d: ("real" if s == {"real"} else "mock" if s == {"mock"} else "mixed") for d, s in real_seen.items()}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_mode": llm.llm_mode(),
        "k": k,
        "n_queries": len(per_query),
        "agents_real": agents_real,
        "routing_accuracy": routing_accuracy(predicted, expected),
        "per_domain_routing": per_label_prf(predicted, expected, DOMAIN_VALUES),
        "confusion_matrix": confusion_matrix(predicted, expected, DOMAIN_VALUES),
        "retrieval_hit_rate": hit_rate_at_k(pair_retrieved, pair_relevant, k) if pair_retrieved else None,
        "retrieval_hit_rate_by_domain": by_domain,
        "recommendation_ndcg_at_3": _mean([r.get("ndcg_at_3") for r in per_query]),
        "precision_at_3": _mean([r.get("precision_at_3") for r in per_query]),
        "gold_coverage": {"queries_with_gold": sum(1 for r in per_query if "ndcg_at_3" in r), "skipped_placeholder_gold": skipped_todo},
        "faithfulness": _mean([r.get("faithfulness") for r in per_query]),
        "diagnostic_gate_compliance": (sum(gate_rows) / len(gate_rows)) if gate_rows else None,
        "out_of_scope_low_confidence_rate": oos_rate,
        "latency_ms_p50": statistics.median(latencies) if latencies else None,
        "latency_ms_p95": latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))] if latencies else None,
        "uncertainty_distribution": unc,
        "errors": sum(1 for r in per_query if r["error"]),
        "calibration": calibration_table(per_query),
        "per_query": per_query,
    }


def write_scorecard(result: Dict[str, Any], out_dir: Optional[Path] = None) -> Path:
    out = Path(out_dir or EVAL_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scorecard.json").write_text(json.dumps(result, indent=2, default=str))
    cols = ["id", "type", "expected_domains", "predicted_domains", "routing_exact", "routing_confidence", "retrieval",
            "ndcg_at_3", "precision_at_3", "faithfulness", "latency_ms", "error"]
    with open(out / "per_query.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in result["per_query"]:
            w.writerow({**r, "retrieval": json.dumps(r.get("retrieval"))})
    return out / "scorecard.json"


def format_scorecard(res: Dict[str, Any]) -> str:
    def pct(v):
        return "n/a" if v is None else f"{100 * v:.1f}%"

    real = ", ".join(f"{d}={s}" for d, s in sorted(res["agents_real"].items())) or "n/a"
    lines = [
        f"Scorecard  ({res['n_queries']} queries, llm_mode={res['llm_mode']}, k={res['k']})",
        f"  agents: {real}",
        f"  Routing accuracy (exact set)    {pct(res['routing_accuracy'])}",
        f"  Retrieval hit-rate@{res['k']}           {pct(res['retrieval_hit_rate'])}   by domain: "
        + ", ".join(f"{d}={pct(v)}" for d, v in res["retrieval_hit_rate_by_domain"].items()),
        f"  Recommendation NDCG@3           {pct(res['recommendation_ndcg_at_3'])}   P@3 {pct(res['precision_at_3'])}"
        f"   (gold on {res['gold_coverage']['queries_with_gold']} queries)",
        f"  Faithfulness                    {pct(res['faithfulness'])}",
        f"  Diagnostic-gate compliance      {pct(res['diagnostic_gate_compliance'])}",
        f"  Out-of-scope low confidence     {pct(res['out_of_scope_low_confidence_rate'])}",
        f"  Latency p50 / p95 (ms)          {res['latency_ms_p50']} / {res['latency_ms_p95']}",
        f"  Errors                          {res['errors']}",
    ]
    if any(s != "real" for s in res["agents_real"].values()):
        lines.append("  NOTE: some domain agents are MOCKS; retrieval/faithfulness/recommendation numbers are not meaningful yet.")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the evaluation benchmark and write data/eval/scorecard.json")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--queries", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    manager = load_manager()
    if manager is None:
        raise SystemExit("ManagerAgent (P1) is not available yet.")
    result = run_benchmark(manager, args.queries, k=args.k)
    path = write_scorecard(result, args.out)
    print(format_scorecard(result))
    print(f"\nWritten: {path}")


if __name__ == "__main__":
    main()
