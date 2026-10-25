"""JComit page: what we hide, results, action log. Run: streamlit run app/streamlit_app.py

Results come from data/ when the skills have run next to this page (live), and
from demo/ otherwise: a snapshot of a real run inside the OpenShell sandbox.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import altair as alt
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jcomit import statement  # noqa: E402
from jcomit.categorize import default_redactor  # noqa: E402

st.set_page_config(page_title="JComit", page_icon="🔒", layout="wide")


def results_dir() -> tuple[Path, str]:
    live = ROOT / "data"
    if (live / "categorized.json").exists() and (live / "review_latest.json").exists():
        return live, "live results from data/"
    return ROOT / "demo", "snapshot of a real run inside the OpenShell sandbox (demo/)"


def load_json(folder: Path, name: str, default):
    path = folder / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def money(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def esc(text: str) -> str:
    """Markdown reads text between two $ signs as maths; show them as plain dollars."""
    return text.replace("$", "\\$")


folder, source = results_dir()
categorized = load_json(folder, "categorized.json", {"items": [], "sent_to_model": []})
review = load_json(folder, "review_latest.json", {})
log = load_json(folder, "action_log.json", None) or load_json(ROOT / "docs", "sample_action_log.json", [])

txns = statement.load(ROOT / "data" / "statement.csv")
redact = default_redactor(txns)

st.title("JComit: private finance agent")
st.caption(
    "Private details are hidden before anything leaves the machine. The agent runs in an NVIDIA "
    "OpenShell sandbox that can reach Nebius Token Factory (Nemotron 3 Super) and nothing else. "
    f"All data is fake. Showing: {source}."
)

hide, results, actions = st.columns([1.1, 1.2, 1])

# --- 1. What we hide ------------------------------------------------------------
with hide:
    st.subheader("1. What we hide")
    rows_tab, receipts_tab, model_tab, try_tab = st.tabs(["Statement", "Receipts", "What Nemotron saw", "Try it"])

    with rows_tab:
        def full_row(t):
            card = f" · card {t.card_last4}" if t.card_last4 else ""
            return f"{t.description} · {t.account_holder} · {t.account_number}{card}"

        # Rows with private details in the description first: they show the most.
        seen, examples = set(), []
        for t in sorted(txns, key=lambda t: redact(t.description) == t.description):
            if t.description not in seen:
                seen.add(t.description)
                examples.append(t)
        st.caption("Every row carries the holder's name and account number. None of it reaches the model.")
        st.table([{"raw": full_row(t), "after redaction": redact(full_row(t))} for t in examples[:12]])

    with receipts_tab:
        receipts = sorted((ROOT / "data" / "receipts").glob("*.txt"))
        if receipts:
            pick = st.selectbox("Receipt", receipts, format_func=lambda p: p.stem.replace("receipt_", ""))
            raw = pick.read_text(encoding="utf-8")
            a, b = st.columns(2)
            a.caption("Raw")
            a.code(raw, language=None)
            b.caption("After redaction")
            b.code(redact(raw), language=None)

    with model_tab:
        st.caption(
            "Rules sort the common shops. Only the shops they don't know go to Nemotron, "
            "after redaction and a final leak check."
        )
        st.dataframe(
            [{"original": s["original"], "sent to Nemotron": s["redacted"]} for s in categorized["sent_to_model"]],
            hide_index=True, use_container_width=True,
        )

    with try_tab:
        text = st.text_area("Type or paste anything", "Zelle payment to Omar Khan from Sara Ahmed, acct 4421-9987, card ending 5521")
        st.code(redact(text), language=None)

# --- 2. Results -----------------------------------------------------------------
with results:
    month = review.get("month", "")
    st.subheader(f"2. Results{f' for {month}' if month else ''}")
    if review:
        m1, m2, m3 = st.columns(3)
        m1.metric("Income", money(review["income"]))
        m2.metric("Spent", money(review["spending_total"]))
        m3.metric("Difference", money(review["income"] - review["spending_total"]))

        st.info(esc(f"**Nemotron's review.** {review['review']}"))

        spend = review["spending_by_category"]
        st.altair_chart(
            alt.Chart(alt.Data(values=[{"category": k, "spent": v} for k, v in spend.items()]))
            .mark_bar()
            .encode(
                x=alt.X("spent:Q", title="Spent ($)"),
                y=alt.Y("category:N", sort="-x", title=None),
                tooltip=["category:N", alt.Tooltip("spent:Q", format="$,.2f")],
            )
            .properties(height=28 * len(spend) + 40),
            use_container_width=True,
        )

        subs = review.get("subscriptions", [])
        if subs:
            total = sum(-s["amount"] for s in subs)
            st.markdown(esc(f"**Subscriptions:** {money(total)} a month, {money(total * 12)} a year"))
            st.table([{"shop": s["merchant"], "monthly": money(-s["amount"])} for s in subs])

        labels = {"large": "Very large charge", "double": "Charged twice", "new_abroad": "New shop abroad"}
        for a in review.get("alerts", []):
            st.warning(esc(f"**{labels.get(a['type'], a['type'])}:** {a['merchant']}, "
                           f"{money(-a['amount'])} on {a['date']}"))

    items = categorized["items"]
    if items:
        decided = Counter(i["source"] for i in items)
        st.caption("Who decided each category: " + ", ".join(f"{k} {v}" for k, v in decided.most_common()))
        with st.expander(f"All {len(items)} transactions"):
            st.dataframe(
                [{"date": i["date"], "shop": i["description"], "amount": i["amount"],
                  "category": i["category"], "decided by": i["source"]} for i in items],
                hide_index=True, use_container_width=True,
            )

# --- 3. Action log --------------------------------------------------------------
with actions:
    st.subheader("3. Action log")
    bad = sum(1 for e in log if e["result"] in ("denied", "blocked"))
    st.caption(f"{len(log)} events, {bad} blocked or denied, newest first. "
               "Green: allowed. Red: stopped by the sandbox.")
    with st.container(height=760):
        for e in reversed(log):
            who = e.get("skill") or e.get("program") or ""
            what = e.get("action") or e.get("target") or ""
            why = e.get("reason") or e.get("detail") or (f"policy: {e['policy']}" if e.get("policy") else "")
            line = f"`{e['time'][11:19]}` **{e['result'].upper()}** {e['source']} {who}  \n{what}"
            if why:
                line += f"  \n_{why}_"
            (st.error if e["result"] in ("denied", "blocked") else st.success)(esc(line))
