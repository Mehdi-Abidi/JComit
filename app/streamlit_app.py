"""JComit page. Run: streamlit run app/streamlit_app.py

Results come from data/ when the skills have run next to this page (live), and
from demo/ otherwise: a snapshot of a real run inside the OpenShell sandbox.
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import altair as alt
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jcomit import statement  # noqa: E402
from jcomit.categorize import default_redactor  # noqa: E402
from jcomit.skills import SKILLS  # noqa: E402

st.set_page_config(page_title="JComit", page_icon=":material/lock:", layout="wide")

ALERT_LABELS = {"large": "Very large charge", "double": "Charged twice", "new_abroad": "New shop abroad"}


# --- data -------------------------------------------------------------------------

def results_dir() -> tuple[Path, bool]:
    live = ROOT / "data"
    if (live / "categorized.json").exists() and (live / "review_latest.json").exists():
        return live, True
    return ROOT / "demo", False


def load_json(folder: Path, name: str, default):
    path = folder / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def money(x: float, cents: bool = True) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.{2 if cents else 0}f}"


def esc(text: str) -> str:
    """Markdown reads text between two $ signs as maths; show them as plain dollars."""
    return text.replace("$", "\\$")


def is_routine(e: dict) -> bool:
    """Allowed model calls: expected, and they bury the interesting events."""
    return e["result"] == "allowed" and "tokenfactory" in e.get("target", "")


folder, live = results_dir()
categorized = load_json(folder, "categorized.json", {"items": [], "sent_to_model": []})
review = load_json(folder, "review_latest.json", {})
log = load_json(folder, "action_log.json", None) or load_json(ROOT / "docs", "sample_action_log.json", [])

txns = statement.load(ROOT / "data" / "statement.csv")
redact = default_redactor(txns)
stopped = [e for e in log if e["result"] in ("denied", "blocked")]
subs = review.get("subscriptions", [])
alerts = review.get("alerts", [])
month = review.get("month", "")
month_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y") if month else ""

# --- header -----------------------------------------------------------------------

st.title("JComit")
st.markdown("##### Your money, sorted by an AI that never learns who you are.")
st.markdown(
    ":green-badge[:material/memory: Nemotron 3 Super on Nebius Token Factory] "
    ":blue-badge[:material/shield: NVIDIA OpenShell sandbox] "
    ":gray-badge[:material/science: All data is fake]"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Spent in {month_name}", money(review.get("spending_total", 0), cents=False), border=True)
k2.metric("Subscriptions", f"{money(-sum(s['amount'] for s in subs))}/mo", border=True)
k3.metric("Alerts", len(alerts), border=True)
k4.metric("Stopped by the sandbox", len(stopped), border=True)

money_tab, privacy_tab, sandbox_tab = st.tabs([
    ":material/bar_chart: Money review",
    ":material/visibility_off: Privacy",
    ":material/shield: Sandbox",
])

# --- money review -----------------------------------------------------------------

with money_tab:
    left, right = st.columns([5, 4], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Nemotron's review**")
            st.markdown(esc(review.get("review", "No review yet.")))
            st.caption("Only category totals, subscriptions and alerts were sent to the model.")
        if alerts:
            st.markdown("**Worth a look**")
            for a in alerts:
                st.markdown(esc(
                    f":orange[:material/warning:] **{ALERT_LABELS.get(a['type'], a['type'])}**: "
                    f"{a['merchant']}, {money(-a['amount'])} on {a['date']}"
                ))
    with right:
        spend = review.get("spending_by_category", {})
        if spend:
            st.markdown(f"**Where the money went in {month_name}**")
            st.altair_chart(
                alt.Chart(alt.Data(values=[{"category": k, "spent": v} for k, v in spend.items()]))
                .mark_bar(cornerRadiusEnd=3, color="#76B900")
                .encode(
                    x=alt.X("spent:Q", title=None, axis=alt.Axis(format="$,.0f")),
                    y=alt.Y("category:N", sort="-x", title=None),
                    tooltip=["category:N", alt.Tooltip("spent:Q", format="$,.2f")],
                )
                .properties(height=26 * len(spend) + 20),
                use_container_width=True,
            )
        if subs:
            total = -sum(s["amount"] for s in subs)
            st.markdown(esc(f"**Subscriptions** · {money(total)} a month, {money(total * 12)} a year"))
            st.dataframe(
                [{"Shop": s["merchant"], "Monthly": money(-s["amount"])} for s in subs],
                hide_index=True, use_container_width=True,
            )

    items = categorized["items"]
    if items:
        decided = Counter(i["source"] for i in items)
        with st.expander(f"All {len(items)} transactions · " + ", ".join(f"{v} by {k}" for k, v in decided.most_common())):
            st.dataframe(
                [{"Date": i["date"], "Shop": i["description"], "Amount": i["amount"],
                  "Category": i["category"], "Decided by": i["source"]} for i in items],
                hide_index=True, use_container_width=True,
                column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")},
            )

# --- privacy ----------------------------------------------------------------------

with privacy_tab:
    steps = st.columns(4)
    for col, (title, text) in zip(steps, [
        ("1. Your statement", "Stays on this machine."),
        ("2. Redaction", "Names, accounts, cards, emails, phones and addresses become labels."),
        ("3. Leak guard", "Refuses to send anything that still holds a private value."),
        ("4. Nemotron", "Sees labels and shop names only."),
    ]):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)

    rows_tab, receipts_tab, model_tab, try_tab = st.tabs(["Statement", "Receipts", "What Nemotron saw", "Try it"])

    receipts = sorted((ROOT / "data" / "receipts").glob("*.txt"))
    for p in receipts:  # so their emails, phones and addresses appear in the label table
        redact(p.read_text(encoding="utf-8"))

    with rows_tab:
        changed = []
        for t in txns:
            red = redact(t.description)
            if red != t.description and t.description not in {c["Raw"] for c in changed}:
                changed.append({"Raw": t.description, "After redaction": red})
        a, b = st.columns([2, 3], gap="large")
        with a:
            st.markdown("**Private values and their labels**")
            kinds = ["NAME", "ACCT", "CARD", "EMAIL", "PHONE", "ADDRESS"]

            def label_order(label: str):
                kind, _, n = label.strip("[]").rpartition("_")
                return (kinds.index(kind) if kind in kinds else len(kinds), int(n) if n.isdigit() else 0)

            st.dataframe(
                [{"Label": k, "Real value (stays here)": redact.mapping[k]}
                 for k in sorted(redact.mapping, key=label_order)],
                hide_index=True, use_container_width=True,
            )
        with b:
            st.markdown("**Rows that mention people or accounts**")
            st.dataframe(changed, hide_index=True, use_container_width=True)
            st.caption("Every row also carries the holder's name, account and card. They are replaced the same way.")

    with receipts_tab:
        if receipts:
            pick = st.selectbox("Receipt", receipts, format_func=lambda p: p.stem.replace("receipt_", "").replace("_", " "))
            raw = pick.read_text(encoding="utf-8")
            a, b = st.columns(2)
            a.caption("Raw")
            a.code(raw, language=None)
            b.caption("After redaction")
            b.code(redact(raw), language=None)

    with model_tab:
        st.caption("Rules sort the common shops. Only the ones they don't know go to Nemotron, once each.")
        st.dataframe(
            [{"Original": s["original"], "Sent to Nemotron": s["redacted"]} for s in categorized["sent_to_model"]],
            hide_index=True, use_container_width=True,
        )

    with try_tab:
        text = st.text_area("Type or paste anything",
                            "Zelle payment to Omar Khan from Sara Ahmed, acct 4421-9987, card ending 5521")
        st.code(redact(text), language=None)

# --- sandbox ----------------------------------------------------------------------

with sandbox_tab:
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("**What each skill may reach**")
        st.dataframe(
            [{"Skill": s.name,
              "Status": "Approved" if s.approved else "Not approved",
              "Network": ", ".join(f"{a.method} {a.host}{a.path}" for a in s.network)}
             for s in SKILLS.values()],
            hide_index=True, use_container_width=True,
        )
        st.caption("The sandbox policy is generated from these declarations. "
                   "Files: code is read-only, only data/ is writable.")
    with right:
        st.markdown("**One policy line, live**")
        shares = [e for e in log if e.get("skill") == "share_report"][-3:]
        cards = st.columns(max(len(shares), 1))
        for col, (e, label) in zip(cards, zip(shares, ["Default policy", "share_report approved", "Approval removed"])):
            ok = e["result"] == "sent"
            with col.container(border=True):
                st.caption(label)
                st.markdown(":green[:material/check_circle: **Sent**]" if ok
                            else ":red[:material/block: **Blocked**]")
                st.caption(e.get("detail", ""))

    st.markdown("**Action log**")
    show_routine = st.toggle("Show routine model calls", value=False)
    shown = [e for e in reversed(log) if show_routine or not is_routine(e)]
    st.dataframe(
        [{
            "Time": e["time"][11:19],
            "Result": ("🔴 " if e["result"] in ("denied", "blocked") else "🟢 ") + e["result"].upper(),
            "Who": e.get("skill") or e.get("program") or e["source"],
            "What": e.get("action") or e.get("target") or "",
            "Why": e.get("reason") or e.get("detail") or (f"policy {e['policy']}" if e.get("policy") else ""),
        } for e in shown],
        hide_index=True, use_container_width=True,
        column_config={"Result": st.column_config.TextColumn(width="small"),
                       "Time": st.column_config.TextColumn(width="small")},
    )

st.divider()
st.caption(
    ("Live results from this machine." if live else
     "Results are a snapshot of a real run inside the NVIDIA OpenShell sandbox.")
    + " Source: [github.com/Mehdi-Abidi/JComit](https://github.com/Mehdi-Abidi/JComit)"
)
