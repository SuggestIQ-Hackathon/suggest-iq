"""Turn a scorecard into the 3 worst queries per metric and (optionally) question files for the owners. Owner: P4.

    python -m p4_eval_ui.evaluation.findings                  # writes p4_eval_ui/presentation/eval_findings.md
    python -m p4_eval_ui.evaluation.findings --post-questions # also drops one question file per owner in questions/to-pN/
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from p4_eval_ui.evaluation.benchmark import EVAL_DIR, REPO_ROOT

OUT = Path(__file__).resolve().parents[1] / "presentation" / "eval_findings.md"
OWNER = {"technology": "p2", "clinical": "p2", "sec": "p3", "corporate_responsibility": "p3"}


def worst(res: Dict[str, Any], n: int = 3) -> Dict[str, List[Tuple[str, str, str]]]:
    """metric -> [(owner, query id, detail)] for the n worst queries."""
    pq = res["per_query"]
    out: Dict[str, List[Tuple[str, str, str]]] = {}
    out["Routing"] = [("p1", r["id"], f"expected {r['expected_domains']} got {r['predicted_domains']}: {r['query'][:70]}")
                      for r in pq if not r.get("routing_exact")][:n]
    ret = [(OWNER.get(d, "p2"), r["id"], f"no expected source in top-{res['k']} for {d}: {r['query'][:60]}")
           for r in pq for d, v in r.get("retrieval", {}).items() if v.get("hit") is False]
    out["Retrieval"] = ret[:n]
    rec = sorted((r for r in pq if "ndcg_at_3" in r), key=lambda r: r["ndcg_at_3"])
    out["Recommendation relevance"] = [(OWNER.get(r["expected_domains"][0], "p2"), r["id"], f"NDCG@3={r['ndcg_at_3']:.2f}: {r['query'][:60]}")
                                       for r in rec[:n] if r["ndcg_at_3"] < 1.0]
    faith = sorted((r for r in pq if r.get("faithfulness") is not None), key=lambda r: r["faithfulness"])
    out["Faithfulness"] = [(OWNER.get((r.get("unsupported") or [{"domain": r["expected_domains"][0]}])[0]["domain"], "p2"), r["id"],
                            f"faithfulness={r['faithfulness']:.2f}, {len(r.get('unsupported', []))} unsupported statement(s)")
                           for r in faith[:n] if r["faithfulness"] < 1.0]
    out["Diagnostic gate"] = [("p2", r["id"], f"asked for diagnostics and withheld parts: NO ({r['query'][:60]})")
                              for r in pq if r.get("gate_compliant") is False][:n]
    return out


def render(res: Dict[str, Any]) -> str:
    mocks = [d for d, s in res["agents_real"].items() if s != "real"]
    lines = [f"# Evaluation findings ({res['generated_at']})", "",
             f"{res['n_queries']} queries, llm_mode={res['llm_mode']}, agents: " + ", ".join(f"{d}={s}" for d, s in res["agents_real"].items())]
    if mocks:
        lines += ["", f"> **Partial run.** Mock agents for: {', '.join(mocks)}. Retrieval, recommendation and faithfulness findings below are artefacts of the mocks, not defects. Re-run `make eval` with `REAL_DOMAINS=all` after integration."]
    for metric, items in worst(res).items():
        lines += ["", f"## {metric}: worst queries"]
        lines += [f"- `{qid}` (owner {owner}): {detail}" for owner, qid, detail in items] or ["- none"]
    return "\n".join(lines) + "\n"


def post_questions(res: Dict[str, Any]) -> List[Path]:
    by_owner: Dict[str, List[str]] = {}
    for metric, items in worst(res).items():
        for owner, qid, detail in items:
            by_owner.setdefault(owner, []).append(f"- **{metric}** `{qid}`: {detail}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    paths = []
    for owner, rows in sorted(by_owner.items()):
        d = REPO_ROOT / "questions" / f"to-{owner}"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{stamp}_from-p4_eval-findings.md"
        path.write_text(
            f"---\nfrom: p4\nto: {owner}\ntype: FINDING\nstatus: open\nrelated_todo: P4-07\ncreated: {datetime.now():%Y-%m-%d %H:%M}\n---\n"
            f"# Benchmark found weak queries in your area\n\n## Question\nThe benchmark (data/eval/scorecard.json, run {res['generated_at']}) "
            f"shows the weakest queries for your module. Please investigate and fix within your TODO scope; re-run with `make eval`.\n\n"
            + "\n".join(rows) + "\n\n## Proposed answer / workaround I am using meanwhile\nNone needed; evaluation continues with current behaviour.\n\n## Answer\n")
        paths.append(path)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorecard", type=Path, default=EVAL_DIR / "scorecard.json")
    ap.add_argument("--post-questions", action="store_true")
    args = ap.parse_args()
    res = json.loads(args.scorecard.read_text())
    OUT.write_text(render(res))
    print(f"Wrote {OUT}")
    if args.post_questions:
        for p in post_questions(res):
            print("Posted", p.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
