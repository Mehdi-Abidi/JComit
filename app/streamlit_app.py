"""JComit page. Run: streamlit run app/streamlit_app.py

The Run tab runs the agent live. The other tabs read data/ when the skills have run
next to this page, and demo/ otherwise: a recorded run inside the OpenShell sandbox.
"""
import json
import os
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

# Load pyarrow fully before anything else. Streamlit imports it lazily on another
# thread, and Altair's data check reads it from sys.modules; on a cold start it can
# see the half-imported module and fail with "module 'pyarrow' has no attribute
# 'Table'" (seen on Streamlit Cloud).
import pyarrow  # noqa: F401, I001

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jcomit import live as agent  # noqa: E402
from jcomit import statement  # noqa: E402
from jcomit.categorize import CATEGORIES, default_redactor  # noqa: E402
from jcomit.skills import SKILLS  # noqa: E402

st.set_page_config(page_title="JComit", page_icon=":material/lock:", layout="wide")

for key in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
    try:
        if not os.environ.get(key) and key in st.secrets:
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass

RUNS_PER_VISITOR = 5
RUNS_PER_DAY = 300
MAX_UPLOAD_BYTES = 200_000
GREEN = "#76B900"
ALERT_LABELS = {"large": "Very large charge", "double": "Charged twice", "new_abroad": "New shop abroad"}
STOPPED = ("denied", "blocked")


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
    return text.replace("$", "\\$")


def month_label(month: str) -> str:
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y") if month else ""


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def show_review(rv: dict, note: str) -> None:
    with st.container(border=True):
        st.markdown(f"**Nemotron's review of {month_label(rv['month'])}**")
        st.markdown(esc(rv.get("review") or "No review yet."))
        st.caption(note)
    alerts = rv.get("alerts", [])
    if alerts:
        st.markdown("**Worth a look**")
        for a in alerts:
            st.markdown(esc(f":orange[:material/warning:] **{ALERT_LABELS.get(a['type'], a['type'])}** · "
                            f"{a['merchant']} · {money(-a['amount'])} on {a['date']}"))


def show_spending(rv: dict) -> None:
    spend = rv.get("spending_by_category", {})
    if spend:
        st.markdown(f"**Where the money went in {month_label(rv['month'])}**")
        st.altair_chart(
            alt.Chart(alt.Data(values=[{"category": k, "spent": v} for k, v in spend.items()]))
            .mark_bar(cornerRadiusEnd=3, color=GREEN)
            .encode(
                x=alt.X("spent:Q", title=None, axis=alt.Axis(format="$,.0f")),
                y=alt.Y("category:N", sort="-x", title=None),
                tooltip=["category:N", alt.Tooltip("spent:Q", format="$,.2f")],
            )
            .properties(height=26 * len(spend) + 20),
            width="stretch",
        )
    subs = rv.get("subscriptions", [])
    if subs:
        total = -sum(s["amount"] for s in subs)
        st.markdown(esc(f"**Subscriptions** · {money(total)} a month, {money(total * 12)} a year"))
        st.dataframe([{"Shop": s["merchant"], "Monthly": money(-s["amount"])} for s in subs],
                     hide_index=True, width="stretch")


def show_transactions(items: list[dict]) -> None:
    decided = Counter(i["source"] for i in items)
    with st.expander(f"All {len(items)} transactions · " + ", ".join(f"{v} by {k}" for k, v in decided.most_common())):
        st.dataframe(
            [{"Date": i["date"], "Shop": i["description"], "Amount": i["amount"],
              "Category": i["category"], "Decided by": i["source"]} for i in items],
            hide_index=True, width="stretch",
            column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")},
        )


def is_routine(e: dict) -> bool:
    return e["result"] == "allowed" and "tokenfactory" in e.get("target", "")


@st.cache_resource
def daily_runs() -> dict:
    return {"day": "", "runs": 0}


@st.cache_data(ttl=3600, show_spinner=False, max_entries=50)
def run_cached(csv_text: str, corrections: tuple) -> dict:
    return agent.run_agent(csv_text, dict(corrections))


def take_run() -> str | None:
    counter = daily_runs()
    today = date.today().isoformat()
    if counter["day"] != today:
        counter.update(day=today, runs=0)
    if st.session_state.runs >= RUNS_PER_VISITOR:
        return f"You have used your {RUNS_PER_VISITOR} live runs for this visit. Reload the page to start a new visit."
    if counter["runs"] >= RUNS_PER_DAY:
        return "Today's live runs are used up. The other tabs show a recorded run."
    counter["runs"] += 1
    st.session_state.runs += 1
    return None


folder, local_results = results_dir()
categorized = load_json(folder, "categorized.json", {"items": [], "sent_to_model": []})
review = load_json(folder, "review_latest.json", {})
log = load_json(folder, "action_log.json", None) or load_json(ROOT / "docs", "sample_action_log.json", [])
txns = statement.load(ROOT / "data" / "statement.csv")
redact = default_redactor(txns)
st.session_state.setdefault("runs", 0)
st.session_state.setdefault("corrections", {})

st.title("JComit")
st.markdown("##### Your money, sorted by an AI that never learns who you are.")
st.markdown(
    ":green-badge[:material/memory: Nemotron 3 Super on Nebius Token Factory] "
    ":violet-badge[:material/travel_explore: Tavily search] "
    ":blue-badge[:material/shield: NVIDIA OpenShell sandbox] "
    ":gray-badge[:material/science: All data is fake]"
)

run_tab, money_tab, privacy_tab, sandbox_tab = st.tabs([
    ":material/play_circle: Run the agent",
    ":material/bar_chart: Money review",
    ":material/visibility_off: Privacy",
    ":material/shield: Sandbox",
])

with run_tab:
    can_run = bool(os.environ.get("NEBIUS_API_KEY"))
    with st.container(border=True):
        left, right = st.columns([3, 1], gap="large", vertical_alignment="center")
        with left:
            st.markdown("**Run the agent on a bank statement**")
            st.caption("Hides private details, sorts spending with rules and Nemotron, looks up unknown shops "
                       "with Tavily, finds subscriptions and odd charges, and writes a monthly review.")
            source = st.radio("Statement", ["Sample statement", "Upload a CSV"], horizontal=True,
                              label_visibility="collapsed")
            csv_text = None
            if source == "Upload a CSV":
                upload = st.file_uploader("Statement CSV", type="csv", label_visibility="collapsed")
                st.caption("Columns: " + ", ".join(statement.COLUMNS) + ". Use fake data; uploads are not "
                           "stored, and only redacted text and shop names leave this page.")
                if upload is not None:
                    if upload.size > MAX_UPLOAD_BYTES:
                        st.error("That file is over 200 KB. Please upload a smaller statement.")
                    else:
                        csv_text = upload.getvalue().decode("utf-8", errors="replace")
            else:
                csv_text = (ROOT / "data" / "statement.csv").read_text(encoding="utf-8")
        with right:
            taught = st.session_state.corrections
            label = "Run again" if st.session_state.get("live") else "Run the agent"
            clicked = st.button(label, type="primary", icon=":material/play_arrow:", width="stretch",
                                disabled=not (can_run and csv_text), key="run")
            st.caption(f"{RUNS_PER_VISITOR} runs per visit"
                       + (f" · {plural(len(taught), 'saved correction')}" if taught else ""))

    if not can_run:
        st.info("Live runs are switched off on this copy of the page. The other tabs show a recorded run.")

    if clicked:
        problem = take_run()
        if problem:
            st.warning(problem)
        else:
            with st.spinner("Running the agent with Nemotron and Tavily..."):
                try:
                    st.session_state.live = run_cached(csv_text, tuple(sorted(taught.items())))
                except Exception as e:
                    st.session_state.live = {"error": str(e)}

    res = st.session_state.get("live")
    if res and res.get("error"):
        st.error(f"The run did not finish: {res['error']}")
    elif res:
        d = res["decided_by"]
        local = d.get("rule", 0) + d.get("memory", 0)
        looked = len(res["searched"])
        placed = sum(1 for s in res["searched"] if s["category"] != "Other")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Private values hidden", res["hidden"], border=True)
        m2.metric("Sorted on this machine", f"{local} of {res['rows']}", border=True)
        m3.metric("Model calls / tokens", f"{res['usage']['calls']} / {res['usage']['tokens']:,}", border=True)
        m4.metric(f"Run time (at {res['ran_at']})", f"{res['seconds']} s", border=True)

        if res["web"] and looked:
            web_step = (f"Tavily searched {plural(looked, 'shop name')} Nemotron couldn't place; "
                        f"{placed} recategorised, {looked - placed} left as Other (unclear results)")
        elif res["web"]:
            web_step = "Tavily search not needed: Nemotron placed every shop"
        else:
            web_step = "Tavily search is off on this copy of the page"
        steps = [
            (True, f"{res['hidden']} private values replaced with labels"),
            (True, f"{local} of {res['rows']} sorted by rules and memory"
                   + (f" ({d['memory']} from memory)" if d.get("memory") else "")),
            (not res["blocked"], "Leak guard passed" if not res["blocked"] else "Leak guard blocked the request"),
            (True, f"{plural(len(res['sent']), 'unknown shop')} sorted by Nemotron 3 Super in one request"),
            (res["web"], web_step),
            (bool(res["review"]), "Monthly review written from totals only"),
        ]
        with st.container(border=True):
            st.markdown("**How this run went**")
            for n, (ok, text) in enumerate(steps, 1):
                icon = ":green[:material/check_circle:]" if ok else ":gray[:material/remove_circle_outline:]"
                st.markdown(f"{icon} {n}. {text}")
            st.caption("This live run uses the agent's own code outside the sandbox; the Sandbox tab and the "
                       "demo video show it inside NVIDIA OpenShell. Results for the same statement are reused "
                       "for an hour.")

        if res["review"]:
            left, right = st.columns([5, 4], gap="large")
            with left:
                show_review(res["review"], "Generated just now from category totals, subscriptions and alerts.")
            with right:
                show_spending(res["review"])

        with st.expander("What left this machine"):
            st.markdown("**Sent to Nemotron**")
            st.dataframe([{"Original": s["original"], "Sent": s["redacted"]} for s in res["sent"]],
                         hide_index=True, width="stretch")
            st.caption("Only shop names the rules didn't know, plus the amount. Rows that name people, like "
                       "Zelle transfers, are sorted by rules and never sent; any that were would go out redacted.")
            if res["searched"]:
                st.markdown("**Searched with Tavily**")
                st.dataframe([{"Searched": s["query"], "Result": s["category"],
                               "Found": s["hint"][:90] + ("..." if len(s["hint"]) > 90 else "")}
                              for s in res["searched"]], hide_index=True, width="stretch")

        with st.container(border=True):
            st.markdown("**Teach it**")
            st.caption("Pick a shop and the category it should be, then run again. Those rows are decided "
                       "by memory instead of the model.")
            shops = sorted({i["description"] for i in res["items"]})
            default = shops.index("SQ *BLUE DOOR LLC") if "SQ *BLUE DOOR LLC" in shops else 0
            a, b, c = st.columns([3, 2, 1], vertical_alignment="bottom")
            shop = a.selectbox("Shop", shops, index=default)
            category = b.selectbox("Category", CATEGORIES, index=CATEGORIES.index("Dining"))
            if c.button("Remember", key="remember", width="stretch"):
                taught[shop] = category
                st.success(f"Saved: {shop} is {category}. Press Run again.")
            if taught:
                st.caption("Saved this visit: " + "; ".join(f"{k} = {v}" for k, v in taught.items()))

        show_transactions(res["items"])

with money_tab:
    subs = review.get("subscriptions", [])
    stopped = [e for e in log if e["result"] in STOPPED]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"Spent in {month_label(review.get('month', ''))}", money(review.get("spending_total", 0), cents=False),
              border=True)
    k2.metric("Subscriptions", f"{money(-sum(s['amount'] for s in subs))}/mo", border=True)
    k3.metric("Alerts", len(review.get("alerts", [])), border=True)
    k4.metric("Stopped by the sandbox", len(stopped), border=True)
    if review:
        left, right = st.columns([5, 4], gap="large")
        with left:
            show_review(review, "Recorded inside the sandbox. Only category totals, subscriptions and alerts "
                                "were sent to the model.")
        with right:
            show_spending(review)
    if categorized["items"]:
        show_transactions(categorized["items"])

with privacy_tab:
    cols = st.columns(4)
    for col, (title, text) in zip(cols, [
        ("1. Your statement", "Stays on this machine."),
        ("2. Redaction", "Names, accounts, cards, IDs and contact details become labels."),
        ("3. Leak guard", "Refuses to send anything that still holds a private value."),
        ("4. Nemotron and Tavily", "See labels and shop names only."),
    ]):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)

    rows_tab, receipts_tab, model_tab, try_tab = st.tabs(["Statement", "Receipts", "What Nemotron saw", "Try it"])

    receipts = sorted((ROOT / "data" / "receipts").glob("*.txt"))
    for p in receipts:
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
                hide_index=True, width="stretch",
            )
        with b:
            st.markdown("**Rows that mention people or accounts**")
            st.dataframe(changed, hide_index=True, width="stretch")
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
            hide_index=True, width="stretch",
        )

    with try_tab:
        text = st.text_area("Type or paste anything",
                            "Zelle payment to Omar Khan from Sara Ahmed, acct 4421-9987, card ending 5521")
        st.code(redact(text), language=None)

with sandbox_tab:
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("**What each skill may reach**")
        st.dataframe(
            [{"Skill": s.name,
              "Status": "Approved" if s.approved else "Not approved",
              "Network": ", ".join(f"{a.method} {a.host}{a.path}" for a in s.network)}
             for s in SKILLS.values()],
            hide_index=True, width="stretch",
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
    table = pd.DataFrame([{
        "Time": e["time"][11:19],
        "Result": e["result"].upper(),
        "Who": e.get("skill") or e.get("program") or e["source"],
        "What": e.get("action") or e.get("target") or "",
        "Why": e.get("reason") or e.get("detail") or (f"policy {e['policy']}" if e.get("policy") else ""),
    } for e in shown])
    if not table.empty:
        st.dataframe(
            table.style.map(lambda v: f"color: {'#ff6b6b' if v.lower() in STOPPED else GREEN}; font-weight: 600",
                            subset=["Result"]),
            hide_index=True, width="stretch",
        )

st.divider()
st.caption(
    ("Money review, Privacy and Sandbox show results from this machine." if local_results else
     "Money review, Privacy and Sandbox show a recorded run inside the NVIDIA OpenShell sandbox.")
    + " Source: [github.com/Mehdi-Abidi/JComit](https://github.com/Mehdi-Abidi/JComit)"
)
