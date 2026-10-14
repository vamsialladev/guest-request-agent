"""Load white-label branding from branding.toml, with safe defaults if a value is missing."""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from src.config import ROOT

BRANDING_FILE = ROOT / "branding.toml"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
DEMO_LABEL = "Demo · simulated data · nothing is ever sent"  # fixed: not part of branding


@dataclass(frozen=True)
class Branding:
    name: str = "Guest Request Agent"
    full_name: str = "Guest Request Agent"
    tagline: str = "Reads a guest email, checks the booking and policy, and drafts a cited reply for staff to approve."
    hotel_group: str = "Hotel Group"
    logo: str = "assets/logo.svg"
    icon: str = "assets/favicon.png"
    primary: str = "#1E4636"
    accent: str = "#94702C"
    primary_dark: str = "#8CC7AA"
    accent_dark: str = "#DDB874"
    links: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)

    def property_name(self, prop: str) -> str:
        return self.properties.get(prop, {}).get("name") or prop.replace("-", " ").title()

    def highlights(self, prop: str) -> str:
        return self.properties.get(prop, {}).get("highlights", "")

    def examples(self, prop: str) -> list[str]:
        return list(self.properties.get(prop, {}).get("examples", []))


def _color(value, default: str) -> str:
    return value if isinstance(value, str) and HEX.match(value) else default


def load_branding(path: Path = BRANDING_FILE) -> Branding:
    base = Branding()
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return base
    product, colors = data.get("product", {}), data.get("colors", {})
    return Branding(
        name=product.get("name", base.name),
        full_name=product.get("full_name", base.full_name),
        tagline=product.get("tagline", base.tagline),
        hotel_group=product.get("hotel_group", base.hotel_group),
        logo=product.get("logo", base.logo),
        icon=product.get("icon", base.icon),
        primary=_color(colors.get("primary"), base.primary),
        accent=_color(colors.get("accent"), base.accent),
        primary_dark=_color(colors.get("primary_dark"), base.primary_dark),
        accent_dark=_color(colors.get("accent_dark"), base.accent_dark),
        links=dict(data.get("links", {})),
        properties=dict(data.get("properties", {})),
    )
