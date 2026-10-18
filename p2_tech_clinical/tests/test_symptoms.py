from core.schemas import DomainType

from p2_tech_clinical.agents.symptoms import (
    CLINICAL_DIAGNOSTICS,
    TECH_DIAGNOSTICS,
    diagnostics_gate_passes,
    missing_diagnostics,
    parse,
    required_diagnostics,
)


def test_parse_technology_query_detects_vendor_model_and_symptoms():
    parsed = parse("Cisco Catalyst 8200 has intermittent connectivity failures and packet loss")
    assert parsed.vendor == "Cisco"
    assert parsed.product_model == "Catalyst 8200"
    assert "intermittent connectivity failures" in parsed.symptoms
    assert "packet loss" in parsed.symptoms
    assert parsed.diagnostics_present == set()


def test_technology_diagnostics_are_canonicalized_from_context():
    diagnostics = """
    show tech-support output
    show logging recent messages
    show interfaces GigabitEthernet0/0 counters: CRC and input errors are zero
    show environment: power and temperature normal
    show platform hardware status
    show version: software version 17.x
    optic DOM readings collected from the transceiver
    """
    parsed = parse("Cisco Catalyst 8200 connectivity issue", {"diagnostics": diagnostics})
    assert parsed.diagnostics_present == set(TECH_DIAGNOSTICS)
    assert not missing_diagnostics(DomainType.TECHNOLOGY, parsed)
    assert diagnostics_gate_passes(DomainType.TECHNOLOGY, parsed)


def test_missing_technology_diagnostics_keep_gate_closed():
    parsed = parse("Our Cisco router has intermittent connectivity failures")
    missing = missing_diagnostics(DomainType.TECHNOLOGY, parsed)
    assert set(missing) == set(TECH_DIAGNOSTICS)
    assert not diagnostics_gate_passes("technology", parsed)
    assert required_diagnostics("technology", parsed) == list(TECH_DIAGNOSTICS)


def test_parse_clinical_query_and_diagnostics():
    parsed = parse(
        "Our Agilent Seahorse analyzer gives inconsistent readings",
        {
            "diagnostics": (
                "instrument error code E42; last calibration date 2026-10-01; "
                "consumable lot L123 age 3 days; firmware/software version 4.2"
            )
        },
    )
    assert parsed.vendor == "Agilent"
    assert parsed.product_model == "Seahorse"
    assert "inconsistent readings" in parsed.symptoms
    assert parsed.diagnostics_present == set(CLINICAL_DIAGNOSTICS)
    assert diagnostics_gate_passes(DomainType.CLINICAL, parsed)


def test_empty_and_unknown_input_is_safe():
    parsed = parse("", None)
    assert parsed.vendor is None
    assert parsed.product_model is None
    assert parsed.symptoms == []
    assert parsed.diagnostics_present == set()
    assert required_diagnostics("unknown", parsed) == []
