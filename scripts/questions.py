"""List questions in questions/. Owner: P1.

  make questions MEMBER=p2             open questions addressed TO p2 (what you must answer)
  make questions MEMBER=p2 FROM=1      questions SENT BY p2 and their status
  make questions                       every open question
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "questions"


def parse(path: Path) -> dict:
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.split("#")[0].strip()
    title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), path.stem)
    return {**meta, "title": title, "path": path.relative_to(ROOT.parent)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--member")
    ap.add_argument("--sent", action="store_true", help="show questions sent by --member")
    args = ap.parse_args()
    items = [parse(p) for p in sorted(ROOT.glob("to-*/*.md"))]
    if args.member and args.sent:
        items = [i for i in items if i.get("from") == args.member]
        label = f"sent by {args.member}"
    elif args.member:
        items = [i for i in items if i.get("to") == args.member and i.get("status", "open") == "open"]
        label = f"OPEN, addressed to {args.member}"
    else:
        items = [i for i in items if i.get("status", "open") == "open" and i.get("to") != "all"]
        label = "OPEN, all members"
    print(f"== questions {label}: {len(items)}")
    for i in items:
        print(f"- [{i.get('status','open')}] {i.get('type','QUESTION')} from {i.get('from','?')} to {i.get('to','?')} "
              f"({i.get('related_todo','-')}): {i['title']}\n    {i['path']}")


if __name__ == "__main__":
    main()
