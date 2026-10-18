"""Faithfulness / hallucination check. Owner: P4.

For each domain finding, every statement (summary sentences + recommendation rationales) is checked against
the citation snippets that the SAME domain response attached.
  live  (LLM_MODE=live): LLM judge via core.llm.complete_json, falls back to lexical on any error.
  mock  (default):       lexical overlap of content words with the snippets (deterministic, offline).
Verdict values: supported = 1.0, partial = 0.5, unsupported = 0.0. score = mean verdict; hallucination rate = 1 - score.
Lexical thresholds: overlap >= SUPPORTED_THRESHOLD -> supported; >= PARTIAL_THRESHOLD -> partial.
"""
import re
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel

from core import llm
from core.schemas import ConsultingReport, DomainResponse

SUPPORTED_THRESHOLD = 0.50
PARTIAL_THRESHOLD = 0.25
_STOP = set(
    "the a an and or of to in on for with from by at as is are was were be been this that these those it its "
    "their our your we you they not no can may will should would could also than then into over under about "
    "which what who whom whose when where why how has have had more most less any all some such per via".split()
)
_VALUE = {"supported": 1.0, "partial": 0.5, "unsupported": 0.0}


class _Verdicts(BaseModel):
    verdicts: List[str]  # one of supported|partial|unsupported per statement, same order


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-\.]*", text.lower()) if len(w) > 3 and w not in _STOP}


_CITE_TAG = re.compile(r"\[[^\]]*\]")  # inline markers such as "[Cisco_10-K.pdf · p. 24]"; they are citations, not claims
# Abstentions and requests are not factual claims, so they cannot be hallucinations.
_ABSTAIN = re.compile(r"^\s*(no relevant|insufficient|not enough|cannot|can't|unable|hypothesis:|more (information|diagnostics)|please provide|information request)", re.I)


def _sentences(text: str) -> List[str]:
    text = _CITE_TAG.sub(" ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
            if len(s.strip()) > 15 and not _ABSTAIN.match(s)]


def statements_of(resp: DomainResponse) -> List[str]:
    out = _sentences(resp.findings_summary)
    out += [x for r in resp.recommendations for x in _sentences(r.rationale)]
    return out


def _lexical(statements: List[str], snippets: List[str]) -> List[Tuple[str, float]]:
    support = set()
    for s in snippets:
        support |= _words(s)
    results = []
    for st in statements:
        ws = _words(st)
        overlap = len(ws & support) / len(ws) if ws else 1.0
        verdict = "supported" if overlap >= SUPPORTED_THRESHOLD else "partial" if overlap >= PARTIAL_THRESHOLD else "unsupported"
        results.append((verdict, overlap))
    return results


def _llm_verdicts(statements: List[str], snippets: List[str]) -> List[str]:
    prompt = (
        "You are a strict fact-checker. For each numbered STATEMENT decide whether the EVIDENCE supports it: "
        "'supported' (fully backed), 'partial' (partly backed), 'unsupported' (not backed or contradicted).\n\n"
        "EVIDENCE:\n" + "\n---\n".join(snippets) + "\n\nSTATEMENTS:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(statements))
        + "\n\nReturn one verdict per statement in order."
    )
    res = llm.complete_json(prompt, _Verdicts)
    if len(res.verdicts) != len(statements) or any(v not in _VALUE for v in res.verdicts):
        raise ValueError("judge returned malformed verdicts")
    return res.verdicts


def judge(report: ConsultingReport) -> Dict[str, Any]:
    """Return {score, hallucination_rate, n_statements, unsupported, method}. score is None when nothing to judge."""
    values: List[float] = []
    unsupported: List[Dict[str, str]] = []
    methods = set()
    for domain, resp in report.domain_findings.items():
        statements = statements_of(resp)
        if not statements:
            continue
        snippets = [c.snippet for c in resp.citations]
        if not snippets:  # nothing cited: every statement is unsupported
            verdicts, methods_used = ["unsupported"] * len(statements), "no-citations"
        else:
            try:
                if llm.is_mock():
                    raise llm.LLMMockMode()
                verdicts, methods_used = _llm_verdicts(statements, snippets), "llm-judge"
            except Exception:  # noqa: BLE001 - any judge failure -> deterministic lexical fallback
                verdicts, methods_used = [v for v, _ in _lexical(statements, snippets)], "lexical"
        methods.add(methods_used)
        for st, v in zip(statements, verdicts):
            values.append(_VALUE[v])
            if v == "unsupported":
                unsupported.append({"domain": domain, "statement": st})
    score = sum(values) / len(values) if values else None
    return {
        "score": score,
        "hallucination_rate": None if score is None else 1.0 - score,
        "n_statements": len(values),
        "unsupported": unsupported,
        "method": "+".join(sorted(methods)) or "n/a",
    }
