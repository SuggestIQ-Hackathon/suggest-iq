"""Prepare the local SEC and SOFI corpora and build their search indexes."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCES = REPO_ROOT / "resources"
RAW_ROOT = REPO_ROOT / "data" / "raw"

ARCHIVES = {
    "sec": RESOURCES / "UnitedStatesSecuritiesandExchangeCommission(SEC).zip",
    "csr": RESOURCES / "FoodSecurity.zip",
}


def _safe_extract(archive: Path, destination: Path) -> None:
    """Extract an archive without allowing members to escape the destination."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"Unsafe path in {archive.name}: {member.filename}")
        zf.extractall(destination)


def ensure_extracted(domain: str, *, force: bool = False) -> Path:
    """Return the raw-data directory, extracting its configured archive if needed."""
    if domain not in ARCHIVES:
        raise ValueError(
            f"Unknown domain {domain!r}; expected one of {sorted(ARCHIVES)}"
        )
    archive = ARCHIVES[domain]
    if not archive.exists():
        raise FileNotFoundError(
            f"Missing {archive}. This large local input is intentionally Git-ignored; "
            "place it in resources/ before ingestion."
        )
    destination = RAW_ROOT / domain
    marker = destination / f".{archive.name}.extracted"
    if force and destination.exists():
        shutil.rmtree(destination)
    if not marker.exists():
        _safe_extract(archive, destination)
        marker.touch()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=("sec", "csr"), help="Build only one corpus")
    parser.add_argument(
        "--force", action="store_true", help="Re-extract and rebuild indexes"
    )
    args = parser.parse_args()

    domains = (args.only,) if args.only else ("sec", "csr")
    if "sec" in domains:
        ensure_extracted("sec", force=args.force)
        from p3_sec_csr.knowledge.sec_kb import SECKB

        count = SECKB().build(force=args.force)
        print(f"SEC index ready: {count} chunks")
    if "csr" in domains:
        ensure_extracted("csr", force=args.force)
        from p3_sec_csr.knowledge.csr_kb import CSRKB

        count = CSRKB().build(force=args.force)
        print(f"CSR index ready: {count} chunks")


if __name__ == "__main__":
    main()
