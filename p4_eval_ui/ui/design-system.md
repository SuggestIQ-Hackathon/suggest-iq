# Design system: AI Management Consulting Platform (dashboard)

## Product context
A web dashboard for a hackathon demo (SJSU CMPE 256). A customer asks a business question; a **Manager Agent** classifies it, routes it in parallel to specialist agents (**Technology**: Cisco/Google docs; **Clinical**: Agilent instruments + clinical literature; **SEC**: Cisco/Agilent/Alphabet filings; **Corporate Responsibility**: FAO food-security reports) and a **Synthesizer** returns a consulting report: executive summary, ranked recommendations with confidence and citations, next steps, and KPIs.
Core principle shown in the UI: the system never guesses a fault. Without diagnostics it returns "More information needed" with a checklist and withholds parts; with diagnostics it ranks compatible parts.
Audience: hackathon judges and enterprise consultants. Must feel trustworthy, evidence-first, calm. NOT a marketing page.

## Pages (left navigation rail, not top tabs)
1. **Consult** (default): question composer, optional diagnostics, result report.
2. **Request flow**: animated diagram of how the question travelled between agents, plus per-agent execution table.
3. **Evidence**: per-domain findings with verbatim citations (source, page, section) and highlighted query terms.
4. **Evaluation**: benchmark scorecard (routing accuracy, retrieval hit-rate, recommendation NDCG@3, faithfulness, diagnostic-gate compliance, out-of-scope handling), targets, trend, per-domain precision/recall, confusion matrix, calibration, per-query table.

## Visual direction: calm enterprise analytics, LIGHT theme
- App shell: slim left rail (64px icons + labels at 232px), top bar with product name and a status chip "LLM: mock | agents: auto". Content max-width 1240px.
- Light only. Background `#F6F7FB`, surface `#FFFFFF`, subtle border `#E3E6EF`, ink `#151A2D`, muted ink `#5B6478`.
- Primary indigo `#4F46E5` (buttons, active nav, focus), hover `#4338CA`. One restrained gradient allowed ONLY on the primary button (`#4F46E5` to `#0EA5E9`). No hero banner, no decorative gradients elsewhere.
- Domain colours (always paired with a text label, never colour alone): Technology `#2563EB`, Clinical `#0D9488`, SEC `#D97706`, Corporate Responsibility `#16A34A`. Manager and Synthesizer use purple `#7C3AED`.
- Status colours: Analysis complete `#16A34A`, Hypothesis `#D97706`, Information request `#EA580C`, Confirmed fault `#2563EB`, Error `#DC2626`. Always a dot plus words.
- Typography: Inter. 28/36 page title 650; 18/26 section title 650; 14/22 body 450; 12/16 meta 500 muted. Tabular numerals for metrics.
- Shape: 12px card radius, 8px controls, 999px pills. Cards are white with 1px border and a very soft shadow `0 1px 2px rgba(21,26,45,.06)`. 8pt spacing grid; 24px between sections.
- Components: metric tile (label, big number, one-line sub with status dot and target), recommendation card (title, category, domain pill, confidence bar green/amber/red with High/Medium/Low label, "Why", evidence line, caveats), numbered step row, KPI chip (dashed border), citation block (left border, source and page meta, highlighted terms with soft yellow `#FEF08A`), callout "More information needed" (orange left border, `#FFF4EC` background).
- Motion: 150ms ease for hover/focus. The only continuous animation is small dots travelling along flow arrows; include a Pause/Replay control. Respect reduced motion.
- Accessibility: AA contrast on light surfaces for all text including diagram labels, 44px touch targets, visible focus rings.

## Content realism
Use real content from this product: the Cisco router example ("Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement parts should we order, and what actions should we take to prevent future outages?"), diagnostics checklist (show tech-support, error counters, software/firmware version), part families like "Catalyst 8200 power supply family", citations like "nb-06-cat8200-series-edge-plat-ds-cte-en.pdf p.4", SOFI 2023 report, benchmark figures. No lorem ipsum, no invented company logos.

## Superdesign project
project 57c8d16b-e866-4377-b2e5-deffbda87a50, Consult draft bcac6196-fb4f-4577-9f97-40a43553678e (model gemini-3.1-pro). Canvas: https://superdesign.dev/teams/e5bcf573-d2df-4f4d-ae48-0536ae762844/projects/57c8d16b-e866-4377-b2e5-deffbda87a50

## Implementation tokens (authoritative: `p4_eval_ui/ui/tokens.py`)
The Streamlit app implements this design system from one token file. The Superdesign palette above was exploratory; where the two differ, `tokens.py` wins:
neutrals (bg `#F6F7FB`, surface `#FFFFFF`, border `#E3E6EF`, ink `#151A2D`, muted `#5B6478`), one brand indigo `#4F46E5` (strong `#3730A3`),
semantic state colours (success/warning/danger/info), and Okabe-Ito-derived domain colours. Circles mean state, squares/bars mean domain.
A test (`test_theme_tokens.py`) fails if any other file hard-codes a colour or if contrast drops below AA (text) / 3:1 (graphics).

## Palette update
The team palette (`#010736`, `#0D1C42`, `#22396F`, `#FCF1D0`) now drives the whole UI: cream page, lighter-cream cards, navy text, navy header band and sidebar, mid-navy actions. State and domain hues are tuned to read on cream (see `tokens.py`).
