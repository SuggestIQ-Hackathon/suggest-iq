"""Direct command-line access to the P2 Clinical Agent.

This module intentionally bypasses the P1 router, manager, synthesizer, and UI.
It prints the agent's raw ``DomainResponse`` as JSON so P2 retrieval and
abstention behavior can be tested independently.
"""

from __future__ import annotations

import argparse
import sys

from p2_tech_clinical.agents.clinical_agent import ClinicalAgent


def _print_response(agent: ClinicalAgent, query: str) -> None:
    response = agent.run(query)
    print(response.model_dump_json(indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a query directly against the P2 Clinical Agent."
    )
    parser.add_argument(
        "--query",
        help="One query to run. If omitted, read queries interactively from stdin.",
    )
    args = parser.parse_args(argv)
    agent = ClinicalAgent()

    if args.query is not None:
        query = args.query.strip()
        if not query:
            parser.error("--query must not be empty")
        _print_response(agent, query)
        return 0

    print("P2 Clinical Agent (direct mode). Enter a query, or Ctrl-D to exit.", file=sys.stderr)
    while True:
        try:
            query = input("clinical> ").strip()
        except EOFError:
            print(file=sys.stderr)
            break
        if not query:
            continue
        _print_response(agent, query)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
