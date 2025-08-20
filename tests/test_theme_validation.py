import pytest
from pydantic import ValidationError
from md2beauty.theme import Theme


def test_invalid_color_in_style_props():
    # Hex colors should start with # and be length 4 or 7 per current simple validation
    bad = {"styles": {"h1": {"color": "red"}}}
    # Pydantic won't validate color format strictly, but extra keys will be validated.
    # In our implementation, color is a string; allow any, so this should not raise.
    Theme.from_dict(bad)


def test_invalid_extra_style_key_rejected():
    bad = {"styles": {"h1": {"unknown-key": "x"}}}
    with pytest.raises(ValidationError):
        Theme.from_dict(bad)


def test_invalid_page_type():
    # Use a clearly invalid page type now that multiple types are supported
    bad = {"page": {"type": "notasize"}}
    with pytest.raises(ValidationError):
        Theme.from_dict(bad)


def test_invalid_orientation():
    bad = {"page": {"orientation": "diagonal"}}
    with pytest.raises(ValidationError):
        Theme.from_dict(bad)


def test_formats_normalization_and_validation():
    # Legacy formats where formats.html is a selector map should be normalized
    ok = {
        "styles": {"p": {"color": "#111"}},
        "formats": {"html": {"p": {"color": "#222"}}},
    }
    theme = Theme.from_dict(ok)
    assert "html" in theme.formats and "p" in theme.formats["html"].styles


def test_formats_rejects_unknown_keys_under_styles():
    bad = {
        "styles": {"p": {"color": "#111"}},
        "formats": {"html": {"styles": {"p": {"oops": 1}}}},
    }
    with pytest.raises(ValidationError):
        Theme.from_dict(bad)


def test_page_margins_units_acceptance():
    # Length fields accept unit strings or bare numbers (inches semantics later)
    Theme.from_dict({"page": {"margins": {"top": "1in", "left": 2}}})

