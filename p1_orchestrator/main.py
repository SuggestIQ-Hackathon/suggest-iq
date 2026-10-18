"""CLI entry point for the Management Consulting Platform. Owner: P1.

Usage:
  python -m p1_orchestrator.main "<query>" [--json] [--context-file path.json]
"""
import argparse
import json
import sys

from core.registry import load_manager


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="SpartanConsult / SuggestIQ Management Consulting Platform")
    parser.add_argument("query", help="Enterprise customer query")
    parser.add_argument("--json", action="store_true", help="Output full ConsultingReport as JSON")
    parser.add_argument("--context-file", help="Path to JSON file containing context dict")

    args = parser.parse_args()

    context = None
    if args.context_file:
        try:
            with open(args.context_file, "r", encoding="utf-8") as f:
                context = json.load(f)
        except Exception as e:
            print(f"Error loading context file: {e}", file=sys.stderr)
            sys.exit(1)

    manager = load_manager()
    if manager is None:
        print("Error: ManagerAgent could not be loaded from p1_orchestrator.agents.manager", file=sys.stderr)
        sys.exit(1)

    report = manager.handle(args.query, context=context)

    if args.json:
        print(report.model_dump_json(indent=2))
        return

    print("=" * 80)
    print(" SPARTAN CONSULT AI - EXECUTIVE MANAGEMENT CONSULTING DELIVERABLE")
    print("=" * 80)
    print(f"\nQuery: {report.query}\n")
    print(f"Detected Domains: {', '.join([d.value for d in report.detected_domains])}")
    print("-" * 80)
    print("EXECUTIVE SUMMARY:")
    print(report.executive_summary)
    
    if report.cross_domain_synthesis:
        print("-" * 80)
        print("CROSS-DOMAIN STRATEGIC SYNTHESIS:")
        print(report.cross_domain_synthesis)

    print("-" * 80)
    print("DOMAIN FINDINGS:")
    for domain_name, resp in report.domain_findings.items():
        print(f"\n[{domain_name.upper()}] Status: {resp.status} | Uncertainty: {resp.uncertainty_level}")
        print(f"Findings: {resp.findings_summary}")
        if resp.missing_diagnostics_needed:
            print(f"Missing Diagnostics Needed: {', '.join(resp.missing_diagnostics_needed)}")
        if resp.citations:
            print("Citations:")
            for cite in resp.citations:
                page_str = f" p.{cite.page}" if cite.page else ""
                print(f"  • [{cite.source_doc}{page_str}] \"{cite.snippet[:80]}...\"")

    print("-" * 80)
    print("RECOMMENDED ACTIONS:")
    if report.consolidated_recommendations:
        for idx, rec in enumerate(report.consolidated_recommendations, 1):
            print(f"{idx}. [{rec.category}] {rec.title} (Confidence: {rec.confidence_score * 100:.0f}%)")
            print(f"   Rationale: {rec.rationale}")
            print(f"   Estimated Impact: {rec.estimated_impact}")
    else:
        print("No immediate hardware replacement recommended pending diagnostic confirmation.")

    print("-" * 80)
    print("NEXT STEPS:")
    for idx, step in enumerate(report.next_steps, 1):
        print(f"{idx}. {step}")

    print("-" * 80)
    print("MEASURABLE IMPACT KPIS:")
    for kpi in report.measuring_impact_kpis:
        print(f"• {kpi}")

    print("=" * 80)


if __name__ == "__main__":
    main()
