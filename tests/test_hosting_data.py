"""The data-preparation script that the Docker build relies on."""
import importlib.util
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_data.py"


@pytest.fixture(scope="module")
def prep():
    spec = importlib.util.spec_from_file_location("prepare_data", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _zip(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, "<html><body>text</body></html>")


def test_p2_zip_is_flattened_into_the_folders_the_knowledge_bases_read(prep, tmp_path, monkeypatch):
    z = tmp_path / "p2.zip"
    _zip(z, ["Manali Data/cisco/datasheet-1.pdf", "Manali Data/cisco/page.html", "Manali Data/gcp/rag.html",
             "Manali Data/agilent/seahorse/analyzer.html", "Manali Data/agilent/special-stains/artisan.html",
             "Manali Data/.DS_Store", "__MACOSX/Manali Data/cisco/._datasheet-1.pdf", "Manali Data/agilent/notes.docx"])
    monkeypatch.setattr(prep, "RAW", tmp_path / "raw")
    counts = prep._flat_copy_from_zip(z, force=False)
    assert counts == {"cisco": 2, "gcp": 1, "agilent": 2}
    assert sorted(p.name for p in (tmp_path / "raw" / "agilent").iterdir()) == ["analyzer.html", "artisan.html"]  # sub-folders flattened
    assert not list((tmp_path / "raw").rglob(".DS_Store")) and not list((tmp_path / "raw").rglob("._*"))  # macOS junk skipped
    assert not list((tmp_path / "raw").rglob("*.docx"))  # only document types the knowledge bases read


def test_existing_files_are_kept_unless_forced(prep, tmp_path, monkeypatch):
    z = tmp_path / "p2.zip"
    _zip(z, ["Manali Data/gcp/rag.html"])
    monkeypatch.setattr(prep, "RAW", tmp_path / "raw")
    prep._flat_copy_from_zip(z, force=False)
    target = tmp_path / "raw" / "gcp" / "rag.html"
    target.write_text("edited by hand")
    prep._flat_copy_from_zip(z, force=False)
    assert target.read_text() == "edited by hand"
    prep._flat_copy_from_zip(z, force=True)
    assert "text" in target.read_text()


def test_real_p2_zip_contains_the_agilent_corpus(prep, tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "RAW", tmp_path / "raw")
    counts = prep._flat_copy_from_zip(prep.P2_ZIP, force=False)
    assert counts["agilent"] >= 15 and counts["cisco"] >= 8 and counts["gcp"] >= 3


def test_data_check_passes_on_a_prepared_checkout(prep):
    if not (prep.REPO_ROOT / "data" / "index" / "tech" / "chunks.json").exists():
        pytest.skip("run `make data` first")
    assert prep.check() == []
