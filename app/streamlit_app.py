"""JComit page: raw vs hidden data, results, action log. Run: streamlit run app/streamlit_app.py"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jcomit import statement  # noqa: E402
from jcomit.categorize import default_redactor  # noqa: E402

st.set_page_config(page_title="JComit", layout="wide")
st.title("JComit: private finance agent")
st.caption("Private details are hidden before anything leaves this machine. Only Token Factory is reachable.")

txns = statement.load(ROOT / "data" / "statement.csv")
redact = default_redactor(txns)
left, mid, right = st.columns(3)

with left:
    st.subheader("1. What we hide")
    rows = [{"raw": t.description, "sent to model": redact(t.description)} for t in txns[:30]]
    st.dataframe(rows, hide_index=True)

with mid:
    st.subheader("2. Results")
    # made-up until the page is wired to categorized.json / review_latest.json
    spent = {"Rent": 1450, "Groceries": 520, "Dining": 310, "Transport": 140, "Subscriptions": 95}
    st.bar_chart([{"category": k, "spent": v} for k, v in spent.items()], x="category", y="spent")
    st.write("**Subscriptions:** IRONWORKS GYM \\$39.00, NETFLIX \\$15.49")
    st.warning("Alert: very large charge, double charge, new shop abroad (example data)")
    st.info("Review (example): Dining is up this month; the gym is your steadiest charge.")

with right:
    st.subheader("3. Action log")
    log = json.loads((ROOT / "docs" / "sample_action_log.json").read_text())
    with st.container(height=480):
        for e in log:
            bad = e["result"] in ("denied", "blocked")
            what = e.get("action") or e.get("target") or e.get("detail", "")
            line = f"`{e['time'][11:19]}` {e['source']}: {what} ({e['result']})"
            (st.error if bad else st.success)(line)
