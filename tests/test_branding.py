from src.branding import DEMO_LABEL, load_branding


def test_default_branding_file_loads():
    b = load_branding()
    assert b.primary == "#1E4636" and b.accent == "#94702C"
    assert b.property_name("beach-resort") == "Beach Resort"
    assert b.highlights("beach-resort") == "rooftop pool, valet, spa"
    assert len(b.examples("mountain-lodge")) >= 3


def test_rebranding_and_bad_values_fall_back_safely(tmp_path):
    path = tmp_path / "branding.toml"
    path.write_text(
        '[product]\nname = "Acme Concierge"\n[colors]\nprimary = "red"\naccent = "#123456"\n'
        '[properties.city-hotel]\nname = "City Hotel"\n',
        encoding="utf-8",
    )
    b = load_branding(path)
    assert b.name == "Acme Concierge" and b.accent == "#123456"
    assert b.primary == "#1E4636"  # "red" isn't a hex color: default kept
    assert b.property_name("city-hotel") == "City Hotel" and b.property_name("new-inn") == "New Inn"
    assert b.examples("unknown") == []


def test_missing_or_broken_file_uses_defaults(tmp_path):
    (tmp_path / "bad.toml").write_text("not = [valid", encoding="utf-8")
    assert load_branding(tmp_path / "bad.toml").name == "Guest Request Agent"
    assert load_branding(tmp_path / "missing.toml").name == "Guest Request Agent"


def test_demo_label_is_not_brandable():
    assert DEMO_LABEL == "Demo · simulated data · nothing is ever sent"
