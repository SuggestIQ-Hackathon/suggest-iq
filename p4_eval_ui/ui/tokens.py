"""Single source of truth for every colour, radius and spacing value in the dashboard. Owner: P4.

The palette is four colours chosen by the team; everything else is derived from them (tints, or state/domain hues tuned to sit on cream).
Rules (enforced by p4_eval_ui/tests/test_theme_tokens.py):
  * No hex colour literal may appear in any other file in p4_eval_ui/ui/. Import from here, or use the CSS variables (--sd-*).
  * One brand hue (indigo) for actions, active states and the system nodes (Manager, Synthesizer).
  * Neutrals carry all structure (backgrounds, borders, text).
  * Semantic hues mean state only: success / warning / danger / info.
  * Domain hues (colour-blind-safe Okabe-Ito family, darkened to reach 3:1 on our surfaces) mean "which agent" only.
    Domain colour is used as a bar, square or outline next to a text label, never as the only signal.
  * Shape grammar: a CIRCLE marks a state (status, confidence), a SQUARE or BAR marks a domain. This keeps similar hues
    (e.g. the ochre domain vs the amber warning) from ever meaning the same thing.
"""

# --- the team palette (given) -----------------------------------------------------------------------------------
NAVY_950 = "#010736"
NAVY_900 = "#0D1C42"
NAVY_700 = "#22396F"
CREAM = "#FCF1D0"

# --- neutrals (lightest tint of the cream as the page, white cards, navy text) ------------------------------------
BG = "#FEF9EC"          # app background: the lightest tint of CREAM
BG_ALT = "#F9F1DA"      # secondary background (inputs, code): a light tint of CREAM
SURFACE = "#FFFFFF"     # cards
BORDER = "#E8DFC4"
INK = NAVY_950          # primary text
MUTED = "#46517A"       # secondary text (>= 4.5:1 on SURFACE and BG)
SUBTLE = "#9AA3BF"      # idle / disabled graphics only, never text
INK_ON_DARK = CREAM     # text on a dark host theme (diagram iframe only)

# --- brand ---------------------------------------------------------------------------------------------------
BRAND = NAVY_700          # actions, active states, step numbers
BRAND_STRONG = NAVY_900   # header band, sidebar, system nodes
ON_BRAND = CREAM

# --- semantic (state), tuned for cream ----------------------------------------------------------------------
SUCCESS = "#1B6E43"
WARNING = "#9A5B0B"
DANGER = "#A8231C"
INFO = "#2F55A4"

# --- domains (which agent), tuned for cream -----------------------------------------------------------------
DOMAIN_COLOR = {
    "technology": "#2F5FB8",
    "clinical": "#12806F",
    "sec": "#8A4F9E",
    "corporate_responsibility": "#A8700F",
}
DOMAIN_LABEL = {"technology": "Technology", "clinical": "Clinical", "sec": "SEC", "corporate_responsibility": "Corporate Responsibility"}

# --- derived maps --------------------------------------------------------------------------------------------
STATUS_COLOR = {"ANALYSIS_COMPLETE": SUCCESS, "HYPOTHESIS": INFO, "INFORMATION_REQUEST": WARNING, "CONFIRMED_FAULT": DANGER}
BUCKET_COLOR = {"High": SUCCESS, "Medium": WARNING, "Low": DANGER}
UNCERTAINTY_COLOR = {"LOW": SUCCESS, "MEDIUM": WARNING, "HIGH": DANGER}
SERIES = [BRAND, DOMAIN_COLOR["technology"], DOMAIN_COLOR["clinical"], DOMAIN_COLOR["sec"], DOMAIN_COLOR["corporate_responsibility"], MUTED]
HEATMAP = [CREAM, NAVY_700]  # confusion-matrix ramp (cream -> mid navy)

# --- shape / spacing -----------------------------------------------------------------------------------------
RADIUS_CARD = "12px"
RADIUS_CONTROL = "8px"
SPACE = {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px"}

# Streamlit theme options (passed by launch.py)
STREAMLIT_THEME = {
    "theme.base": "light",
    "theme.primaryColor": BRAND,
    "theme.backgroundColor": BG,
    "theme.secondaryBackgroundColor": BG_ALT,
    "theme.textColor": INK,
    "theme.sidebar.backgroundColor": NAVY_900,
    "theme.sidebar.secondaryBackgroundColor": NAVY_700,
    "theme.sidebar.textColor": CREAM,
    "theme.sidebar.primaryColor": CREAM,
}


def css_vars() -> str:
    """:root block exposing the tokens as --sd-* custom properties."""
    pairs = {
        "bg": BG, "bg-alt": BG_ALT, "surface": SURFACE, "border": BORDER, "ink": INK, "muted": MUTED, "subtle": SUBTLE,
        "brand": BRAND, "brand-strong": BRAND_STRONG, "on-brand": ON_BRAND,
        "success": SUCCESS, "warning": WARNING, "danger": DANGER, "info": INFO,
        "radius-card": RADIUS_CARD, "radius-control": RADIUS_CONTROL,
    }
    return ":root{" + ";".join(f"--sd-{k}:{v}" for k, v in pairs.items()) + "}"
