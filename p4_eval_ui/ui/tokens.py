"""Single source of truth for every colour, radius and spacing value in the dashboard. Owner: P4.

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

# --- neutrals -----------------------------------------------------------------------------------------------
BG = "#F6F7FB"          # app background
BG_ALT = "#ECEFF7"      # sidebar / secondary background
SURFACE = "#FFFFFF"     # cards
BORDER = "#E3E6EF"
INK = "#151A2D"         # primary text
MUTED = "#5B6478"       # secondary text (>= 4.5:1 on SURFACE and BG)
SUBTLE = "#9AA3B5"      # idle / disabled graphics only, never text
INK_ON_DARK = "#E6E8EB" # text on a dark host theme (diagram iframe only)

# --- brand ---------------------------------------------------------------------------------------------------
BRAND = "#4F46E5"
BRAND_STRONG = "#3730A3"  # header band, system nodes
ON_BRAND = "#FFFFFF"

# --- semantic (state) ----------------------------------------------------------------------------------------
SUCCESS = "#15803D"
WARNING = "#B45309"
DANGER = "#B91C1C"
INFO = "#1D4ED8"

# --- domains (which agent) -----------------------------------------------------------------------------------
DOMAIN_COLOR = {
    "technology": "#0072B2",
    "clinical": "#009E73",
    "sec": "#B5568F",
    "corporate_responsibility": "#B8770B",
}
DOMAIN_LABEL = {"technology": "Technology", "clinical": "Clinical", "sec": "SEC", "corporate_responsibility": "Corporate Responsibility"}

# --- derived maps --------------------------------------------------------------------------------------------
STATUS_COLOR = {"ANALYSIS_COMPLETE": SUCCESS, "HYPOTHESIS": INFO, "INFORMATION_REQUEST": WARNING, "CONFIRMED_FAULT": DANGER}
BUCKET_COLOR = {"High": SUCCESS, "Medium": WARNING, "Low": DANGER}
UNCERTAINTY_COLOR = {"LOW": SUCCESS, "MEDIUM": WARNING, "HIGH": DANGER}
SERIES = [BRAND, DOMAIN_COLOR["technology"], DOMAIN_COLOR["clinical"], DOMAIN_COLOR["sec"], DOMAIN_COLOR["corporate_responsibility"], MUTED]
HEATMAP = ["#E8E7FB", BRAND_STRONG]  # light brand tint -> strong brand (confusion-matrix ramp)

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
