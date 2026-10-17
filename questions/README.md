# questions/ — agent-to-agent mailbox

Each member's coding agent can ask a question to another member's agent. One question = one file. No shared file, so no merge conflicts.

```
questions/
  to-p1/  to-p2/  to-p3/  to-p4/     inbox of that member's agent (P1 also receives SCHEMA-CHANGE requests)
  to-all/                            broadcasts and findings (no answer required)
```

## Asking (any agent)
1. Create `questions/to-pN/<YYYYMMDD-HHMM>_from-pM_<short-slug>.md` (N = who should answer, M = you). Use the template below. Do not edit anyone else's question.
2. Ask only about **interfaces, data, ownership or contract mismatches**. First re-read `COMMON.md` and the other members' `TODO.md`; if they answer it, do not ask.
3. Put a **proposed answer** and a **workaround** (mock or assumption) in the file, then continue with your next TODO item. Never block on an answer.
4. Commit and push the question file on its own (`git add questions && git commit -m "question: ..." && git push`) so the recipient can pull it.

## Answering (recipient agent)
1. At the start of every session: `git pull`, then `make questions MEMBER=pN` (lists open questions addressed to you).
2. Answer inside the same file: fill `## Answer`, set `status: answered`, add `answered_by` and `answered_at`. Edit only files in your own `questions/to-pN/`.
3. If the answer needs a change in code you own, do it within your TODO scope and say what changed (file/commit). If it needs a change in someone else's code, set `status: redirected`, say to whom, and create a new question in their inbox.
4. If answering requires changing a locked contract (`core/`), only P1 can; ask P1 with `type: SCHEMA-CHANGE`.
5. Commit and push the answer so the asker can pull it. Askers check their own questions with `make questions MEMBER=pM FROM=1` (questions you sent).

## Template (copy exactly; keep the front matter keys)
```markdown
---
from: p2
to: p1
type: QUESTION            # QUESTION | SCHEMA-CHANGE | BLOCKED | FINDING
status: open              # open | answered | redirected | closed
related_todo: P2-08
created: 2026-10-17 14:05
---
# <one-line title>

## Question
<What exactly do you need? Quote the file/line or contract you are unsure about.>

## Proposed answer / workaround I am using meanwhile
<...>

## Answer
<recipient fills this in>
answered_by: pN
answered_at: <date time>
```

Statuses are updated by the recipient (`answered`, `redirected`) or the asker (`closed` once satisfied).
