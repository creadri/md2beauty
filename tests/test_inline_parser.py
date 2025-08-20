from md2beauty.mdparser import parse_inline_emphasis


def spans_to_flags(spans):
    return [(s.text, s.bold, s.italic, s.strike) for s in spans]


def test_parse_inline_basic():
    s = parse_inline_emphasis("Hello **bold** and *it* and ~~gone~~.")
    flags = spans_to_flags(s)
    # Expect markers toggling to produce styled spans for words
    assert ("bold", True, False, False) in flags
    assert ("it", False, True, False) in flags
    assert ("gone", False, False, True) in flags


def test_parse_inline_mixed_nesting():
    s = parse_inline_emphasis("**mix *both* styles**")
    # inner word 'both' should be bold+italic due to toggles
    assert any(sp.text.strip() == "both" and sp.bold and sp.italic for sp in s)


def test_parse_inline_underscores():
    s = parse_inline_emphasis("__strong__ and _em_")
    assert any(sp.text == "strong" and sp.bold for sp in s)
    assert any(sp.text == "em" and sp.italic for sp in s)
