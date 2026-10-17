"""Build slides.pdf from slides.md and the latest scorecard. Owner: P4.   python p4_eval_ui/presentation/build_slides.py"""
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
SCORECARD = HERE.parents[1] / "data" / "eval" / "scorecard.json"
W, H = 960, 540
INK, MUTED, ACCENT, WARN = HexColor("#1b1f24"), HexColor("#5b6572"), HexColor("#1f6feb"), HexColor("#b35900")


def pct(v):
    return "n/a" if v is None else f"{100 * v:.1f}%"


def scorecard_lines():
    if not SCORECARD.exists():
        return ["(no scorecard yet: run `make eval`)"], True
    r = json.loads(SCORECARD.read_text())
    mocks = [d for d, s in r["agents_real"].items() if s != "real"]
    lines = [
        f"Routing accuracy (exact set): {pct(r['routing_accuracy'])}",
        f"Retrieval hit-rate@{r['k']}: {pct(r['retrieval_hit_rate'])}",
        f"Recommendation NDCG@3: {pct(r['recommendation_ndcg_at_3'])}   Precision@3: {pct(r['precision_at_3'])}",
        f"Faithfulness: {pct(r['faithfulness'])}",
        f"Diagnostic-gate compliance: {pct(r['diagnostic_gate_compliance'])}",
        f"Out-of-scope queries handled: {pct(r['out_of_scope_low_confidence_rate'])}",
        f"{r['n_queries']} queries, llm_mode={r['llm_mode']}, median latency {r['latency_ms_p50']} ms",
    ]
    if mocks:
        lines.append("PARTIAL RUN: mock agents for " + ", ".join(mocks) + ". Re-run `make eval` with REAL_DOMAINS=all before presenting.")
    return lines, bool(mocks)


def parse():
    slides = []
    for block in (HERE / "slides.md").read_text().split("\n---\n"):
        title, bullets = "", []
        for line in block.strip().splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("- "):
                bullets.append(line[2:].strip())
            elif line.strip() == "{{SCORECARD}}":
                bullets.extend(scorecard_lines()[0])
        slides.append((title, bullets))
    return slides


def main():
    out = HERE / "slides.pdf"
    c = canvas.Canvas(str(out), pagesize=(W, H))
    slides = parse()
    for n, (title, bullets) in enumerate(slides, 1):
        c.setFillColor(ACCENT)
        c.rect(0, H - 8, W, 8, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 34 if n > 1 else 40)
        for i, t in enumerate(simpleSplit(title, "Helvetica-Bold", 34, W - 120)):
            c.drawString(60, H - 90 - i * 40, t)
        fs, lh = (21, 29) if len(bullets) <= 6 else (16, 22)
        y = H - 170
        for b in bullets:
            warn = b.startswith("PARTIAL RUN")
            c.setFillColor(WARN if warn else INK)
            c.setFont("Helvetica", fs)
            lines = simpleSplit(b, "Helvetica", fs, W - 150)
            c.drawString(60, y, "•")
            for ln in lines:
                c.drawString(85, y, ln)
                y -= lh
            y -= 8
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 11)
        c.drawRightString(W - 40, 22, f"{n} / {len(slides)}")
        c.showPage()
    c.save()
    print(f"Wrote {out} ({len(slides)} slides)")


if __name__ == "__main__":
    main()
