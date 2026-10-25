"""The page renders without errors on the committed demo snapshot."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_page_renders_demo_snapshot():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=30).run()
    assert not at.exception
    assert any("Nemotron's review" in i.value for i in at.info)
    assert len(at.warning) == 3  # large, double, new abroad
    assert any("BLOCKED" in e.value for e in at.error)
    # The "Try it" box (last code block) redacts its default sentence.
    tried = at.code[-1].value
    assert "[NAME_" in tried and "[ACCT_" in tried and "[CARD_" in tried
    assert not any(s in tried for s in ("Omar Khan", "Sara Ahmed", "4421", "5521"))
