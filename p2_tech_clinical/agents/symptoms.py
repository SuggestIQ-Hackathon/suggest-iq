"""Rule-based symptom extraction and diagnostic gating for P2 agents."""

from __future__ import annotations

import re
from typing import Any, Iterable, List, Mapping, Optional, Set

from pydantic import BaseModel, Field


TECH_DIAGNOSTICS = (
    "show tech-support",
    "show logging",
    "show interfaces counters",
    "show environment",
    "show platform hardware status",
    "software version",
    "optic or DOM readings",
)

CLINICAL_DIAGNOSTICS = (
    "instrument error codes",
    "calibration or maintenance date",
    "consumable lot or age",
    "firmware/software version",
)


class ParsedSymptoms(BaseModel):
    """Structured, conservative interpretation of a troubleshooting request."""

    vendor: Optional[str] = None
    product_model: Optional[str] = None
    symptoms: List[str] = Field(default_factory=list)
    diagnostics_present: Set[str] = Field(default_factory=set)


_VENDORS = (
    ("Cisco", re.compile(r"\bcisco\b", re.I)),
    ("Agilent", re.compile(r"\bagilent\b", re.I)),
    ("Google", re.compile(r"\b(?:google|gcp)\b", re.I)),
    ("IBM", re.compile(r"\bibm\b", re.I)),
)

_MODELS = (
    ("Catalyst 8300", re.compile(r"\bcatalyst\s*8300\b", re.I)),
    ("Catalyst 8200", re.compile(r"\bcatalyst\s*8200\b", re.I)),
    ("Catalyst 8000V", re.compile(r"\bcatalyst\s*8000\s*v\b", re.I)),
    ("ISR 4000", re.compile(r"\b(?:cisco\s+)?(?:isr\s*)?4000\b|\bisr\s*4000\b", re.I)),
    ("ASR 1000", re.compile(r"\basr\s*1000\b", re.I)),
    ("Seahorse", re.compile(r"\bseahorse\b", re.I)),
    ("NanoZoomer", re.compile(r"\bnanozoomer\b", re.I)),
    ("Artisan Link Pro", re.compile(r"\bartisan\s+link\s+pro\b", re.I)),
)


def _contains(patterns: Iterable[str], text: str) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def _diagnostics_present(text: str, vendor: str | None = None) -> set[str]:
    """Map command/output aliases to the canonical diagnostic labels."""
    lowered = text.lower()
    found: set[str] = set()
    if re.search(r"show\s+tech[- ]support|tech[- ]support\s+output", lowered):
        found.add("show tech-support")
    if re.search(r"show\s+logging|log(?:ging)?\s+(?:output|entries|messages|shows?)", lowered):
        found.add("show logging")
    if re.search(r"show\s+interfaces?(?:\s+\S+)*\s+(?:counters?|crc|input|output)\b|\b(?:crc|input\s+errors?|output\s+errors?)\b", lowered):
        found.add("show interfaces counters")
    if re.search(r"show\s+environment|(?:power|temperature|fan)(?:\s+|[-])?(?:status|reading|readings|alarm|failure)", lowered):
        found.add("show environment")
    if re.search(r"show\s+platform|platform\s+(?:hardware\s+)?status|hardware\s+status", lowered):
        found.add("show platform hardware status")
    is_clinical = vendor == "Agilent"
    if not is_clinical and re.search(r"(?:show\s+version|software\s+version|firmware\s+version|ios\s+version)", lowered):
        found.add("software version")
    if re.search(r"\b(?:optic|optics|dom|transceiver)\b", lowered):
        found.add("optic or DOM readings")

    if re.search(r"(?:instrument|device|analyzer)\s+(?:error|fault)\s*code|error\s+codes?\b|instrument\s+log", lowered):
        found.add("instrument error codes")
    if re.search(r"(?:last\s+)?(?:calibration|maintenance)\s+(?:date|记录|record|history)|calibrat(?:e|ion)|maintenance\s+date", lowered):
        found.add("calibration or maintenance date")
    if re.search(r"consumable\s+(?:lot|age|expiry|expiration)|lot\s+(?:number|age)|(?:age|expiry|expiration)\s+of\s+(?:the\s+)?consumable", lowered):
        found.add("consumable lot or age")
    if is_clinical and re.search(r"firmware\s+(?:or|/)\s+software\s+version|software\s+(?:or|/)\s+firmware\s+version|firmware\s+version|software\s+version", lowered):
        found.add("firmware/software version")
    return found


_SYMPTOM_PATTERNS = (
    ("intermittent connectivity failures", ("intermittent connectivity", "intermittent connection", "connectivity failures")),
    ("packet loss", ("packet loss", "dropped packets")),
    ("link flaps", ("link flap", "link flaps", "interface flap")),
    ("CRC errors", ("crc error", "crc errors")),
    ("input/output errors", ("input error", "output error", "input/output error")),
    ("crashes", ("crash", "crashes", "unexpected restart")),
    ("overheating or temperature alarms", ("overheating", "overheat", "temperature alarm", "high temperature")),
    ("power or fan fault", ("power failure", "power fault", "fan failure", "fan fault")),
    ("inconsistent readings", ("inconsistent readings", "inconsistent result", "variable readings")),
    ("instrument error", ("instrument error", "analyzer error", "error code")),
    ("calibration drift", ("calibration drift", "needs calibration", "calibration issue")),
    ("imaging issue", ("imaging issue", "scanner issue", "slide scan")),
)


def _symptoms(text: str) -> list[str]:
    lowered = text.lower()
    return [label for label, aliases in _SYMPTOM_PATTERNS if any(alias in lowered for alias in aliases)]


def parse(query: str, context: Mapping[str, Any] | None = None) -> ParsedSymptoms:
    """Parse vendor, model, symptoms, and diagnostics without making a fault claim.

    Diagnostics are read from ``context['diagnostics']`` when present. Unknown
    context keys are ignored, and malformed/empty input returns a valid empty
    ``ParsedSymptoms`` object.
    """
    query_text = str(query or "")
    vendor = next((name for name, pattern in _VENDORS if pattern.search(query_text)), None)
    model = next((name for name, pattern in _MODELS if pattern.search(query_text)), None)
    diagnostics_text = ""
    if isinstance(context, Mapping):
        value = context.get("diagnostics", "")
        diagnostics_text = value if isinstance(value, str) else str(value or "")
    return ParsedSymptoms(
        vendor=vendor,
        product_model=model,
        symptoms=_symptoms(query_text),
        diagnostics_present=_diagnostics_present(diagnostics_text, vendor),
    )


def _domain_value(domain: Any) -> str:
    value = getattr(domain, "value", domain)
    return str(value or "").lower()


def required_diagnostics(domain: Any, symptoms: ParsedSymptoms | Iterable[str] | None) -> list[str]:
    """Return the diagnostics required before replacement-part recommendations.

    Technology troubleshooting uses the complete router diagnostic set because
    the symptom parser cannot safely rule out a power, platform, software, or
    optic cause from a short user query. Clinical troubleshooting likewise
    requires all four instrument evidence classes before recommending a part.
    The ``symptoms`` argument is accepted for interface compatibility and is
    intentionally not used to remove safety-critical checks.
    """
    del symptoms
    value = _domain_value(domain)
    if value in {"technology", "tech", "domainType.technology"}:
        return list(TECH_DIAGNOSTICS)
    if value in {"clinical", "domainType.clinical"}:
        return list(CLINICAL_DIAGNOSTICS)
    return []


def missing_diagnostics(domain: Any, parsed: ParsedSymptoms) -> list[str]:
    """Return required checks absent from a parsed request's diagnostics."""
    present = set(parsed.diagnostics_present)
    return [name for name in required_diagnostics(domain, parsed) if name not in present]


def diagnostics_gate_passes(domain: Any, parsed: ParsedSymptoms) -> bool:
    """Whether all domain-required diagnostics are present."""
    return not missing_diagnostics(domain, parsed)
