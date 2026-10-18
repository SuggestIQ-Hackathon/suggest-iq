"""Small line illustrations used as product images (the dataset has no photos). Colour comes from the page theme (currentColor)."""
_SVG = '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>'
ICONS = {
    "Cameras": '<rect x="5" y="14" width="29" height="19" rx="4"/><circle cx="19.5" cy="23.5" r="5"/><path d="M34 21l9-5v16l-9-5"/>',
    "Recorders": '<rect x="4" y="15" width="40" height="18" rx="3"/><circle cx="12" cy="24" r="1.8"/><path d="M20 21h18M20 27h12"/>',
    "Detectors": '<circle cx="24" cy="24" r="5"/><path d="M13 24a11 11 0 0 1 22 0M13 24a11 11 0 0 0 22 0M7 24a17 17 0 0 1 34 0"/>',
    "Panels & kits": '<rect x="9" y="5" width="30" height="38" rx="4"/><rect x="14" y="10" width="20" height="9" rx="2"/><circle cx="17" cy="27" r="2"/><circle cx="24" cy="27" r="2"/><circle cx="31" cy="27" r="2"/><circle cx="17" cy="35" r="2"/><circle cx="24" cy="35" r="2"/><circle cx="31" cy="35" r="2"/>',
    "Accessories": '<rect x="8" y="8" width="32" height="32" rx="6"/><circle cx="17" cy="17" r="2"/><circle cx="24" cy="17" r="2"/><circle cx="31" cy="17" r="2"/><circle cx="17" cy="24" r="2"/><circle cx="24" cy="24" r="2"/><circle cx="31" cy="24" r="2"/><circle cx="17" cy="31" r="2"/><circle cx="24" cy="31" r="2"/><circle cx="31" cy="31" r="2"/>',
}


def icon_svg(category: str) -> str:
    return _SVG.format(ICONS.get(category, ICONS["Accessories"]))
