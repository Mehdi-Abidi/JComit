"""The page renders without errors on the committed demo snapshot."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_page_renders_demo_snapshot():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=30).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Nemotron's review" in text
    assert all(label in text for label in ("Very large charge", "Charged twice", "New shop abroad"))
    assert [m.value for m in at.metric][2:] == ["3", "4"]  # alerts, stopped by the sandbox
    # The "Try it" box (last code block) redacts its default sentence.
    tried = at.code[-1].value
    assert "[NAME_" in tried and "[ACCT_" in tried and "[CARD_" in tried
    assert not any(s in tried for s in ("Omar Khan", "Sara Ahmed", "4421", "5521"))
