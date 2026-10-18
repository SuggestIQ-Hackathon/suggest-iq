"""Build everything the app needs in data/ from the files in resources/, offline and repeatably. Used by `make data` and the Dockerfile.

    python scripts/prepare_data.py            build whatever is missing
    python scripts/prepare_data.py --force    rebuild all indexes from scratch
    python scripts/prepare_data.py --check    only verify that data/ is complete (exit code 1 if not)

Inputs (resources/): P2-Data.zip (Cisco datasheets and pages, Agilent pages, GCP pages), Clinical.zip, FoodSecurity.zip,
UnitedStatesSecuritiesandExchangeCommission(SEC).zip, Retail.zip. No network access is needed.
Outputs: data/raw/<corpus>/..., data/index/<kb>/..., data/BUNDLE.json (what was built, chunk counts, embedding mode).
"""
import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("EMBEDDING_MODE", "hash")

RESOURCES = REPO_ROOT / "resources"
RAW = REPO_ROOT / "data" / "raw"
P2_ZIP = RESOURCES / "P2-Data.zip"
WANTED = {".pdf", ".html", ".htm", ".txt"}
SKIP_PARTS = {"__MACOSX"}


def _flat_copy_from_zip(zip_path: Path, force: bool) -> dict:
    """P2-Data.zip -> data/raw/{cisco,gcp,agilent}/<file>. The knowledge bases read these folders flat (no sub-folders), so Agilent's
    seahorse/, digital-pathology/ ... sub-folders are flattened. Existing files are kept unless --force."""
    if not zip_path.exists():
        raise FileNotFoundError(f"{zip_path} not found: place P2-Data.zip in resources/")
    counts = {"cisco": 0, "gcp": 0, "agilent": 0}
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            parts = Path(member.filename).parts
            if member.is_dir() or SKIP_PARTS & set(parts) or Path(member.filename).name.startswith(".") or Path(member.filename).suffix.lower() not in WANTED:
                continue
            group = next((g for g in counts if g in parts), None)
            if group is None:
                continue
            target = RAW / group / Path(member.filename).name
            if ".." in parts or (target.exists() and not force):
                counts[group] += 1 if target.exists() else 0
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            counts[group] += 1
    return counts


def _index_dir(name: str) -> Path:
    return REPO_ROOT / "data" / "index" / name


def prepare(force: bool) -> dict:
    summary = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "embedding_mode": os.environ["EMBEDDING_MODE"]}
    if force:
        for kb in ("tech", "clinical", "sec", "csr"):
            shutil.rmtree(_index_dir(kb), ignore_errors=True)
        shutil.rmtree(RAW / "cisco", ignore_errors=True)
        shutil.rmtree(RAW / "gcp", ignore_errors=True)
        shutil.rmtree(RAW / "agilent", ignore_errors=True)

    print("[1/5] P2 sources from P2-Data.zip (Cisco, Agilent, GCP)")
    summary["p2_files"] = _flat_copy_from_zip(P2_ZIP, force)
    print("     ", summary["p2_files"])

    print("[2/5] Clinical corpus (Clinical.zip)")
    clinical_raw = RAW / "clinical"
    if force or not any(clinical_raw.rglob("*.pdf")) if clinical_raw.exists() else True:
        from p2_tech_clinical.knowledge import ingest as p2_ingest

        p2_ingest.ingest(only="clinical")

    print("[3/5] Retail orders (Retail.zip)")
    from retail_basket.data import csv_path

    summary["retail_csv"] = str(csv_path().relative_to(REPO_ROOT))

    print("[4/5] SEC and food-security corpora (P3 ingest)")
    from p3_sec_csr.knowledge.sec_kb import SECKB
    from p3_sec_csr.knowledge.csr_kb import CSRKB
    from p3_sec_csr.knowledge.ingest import ensure_extracted

    ensure_extracted("sec")
    ensure_extracted("csr")

    print("[5/5] Building search indexes")
    from p2_tech_clinical.knowledge.clinical_kb import ClinicalKB
    from p2_tech_clinical.knowledge.tech_kb import TechKB

    chunks = {}
    for name, builder in (("tech", lambda: len(TechKB().build())), ("clinical", lambda: len(ClinicalKB().build())),
                          ("sec", lambda: SECKB().build(force=force)), ("csr", lambda: CSRKB().build(force=force))):
        idx = _index_dir(name)
        if idx.exists() and not force and (idx / "chunks.json").exists():
            chunks[name] = len(json.loads((idx / "chunks.json").read_text())["chunks"])
            print(f"      {name}: already built ({chunks[name]} chunks)")
        else:
            chunks[name] = builder()
            print(f"      {name}: built ({chunks[name]} chunks)")
    summary["chunks"] = chunks
    (REPO_ROOT / "data").mkdir(exist_ok=True)
    (REPO_ROOT / "data" / "BUNDLE.json").write_text(json.dumps(summary, indent=2))
    return summary


def check() -> list:
    """Return a list of problems (empty = data/ is complete and every index answers a test search)."""
    problems = []
    for kb in ("tech", "clinical", "sec", "csr"):
        if not (_index_dir(kb) / "chunks.json").exists():
            problems.append(f"missing index: data/index/{kb}")
    if problems:
        return problems
    from p2_tech_clinical.knowledge.clinical_kb import ClinicalKB
    from p2_tech_clinical.knowledge.tech_kb import TechKB
    from p3_sec_csr.knowledge.csr_kb import CSRKB
    from p3_sec_csr.knowledge.sec_kb import SECKB

    probes = [("tech", TechKB, "Catalyst 8200 power supply"), ("clinical", ClinicalKB, "Seahorse XF analyzer"),
              ("sec", SECKB, "Cisco supply chain risk"), ("csr", CSRKB, "food insecurity conflict")]
    for name, cls, query in probes:
        try:
            if not cls().search(query, 3):
                problems.append(f"{name}: search returned nothing for {query!r}")
        except Exception as err:  # noqa: BLE001
            problems.append(f"{name}: search failed ({type(err).__name__}: {err})")
    agilent = list((RAW / "agilent").glob("*")) if (RAW / "agilent").exists() else []
    if len(agilent) < 10:
        problems.append(f"agilent corpus looks incomplete ({len(agilent)} files; expected 20+)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="rebuild everything from scratch")
    ap.add_argument("--check", action="store_true", help="only verify data/ is complete")
    args = ap.parse_args()
    if not args.check:
        prepare(args.force)
    problems = check()
    if problems:
        print("\nDATA CHECK FAILED:\n  - " + "\n  - ".join(problems))
        return 1
    print("\nDATA CHECK OK: all four indexes answer test searches; Agilent corpus present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
