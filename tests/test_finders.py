import json
from datetime import date, timedelta
from pathlib import Path

from jcomit import statement
from jcomit.finders import find_alerts, find_subscriptions
from jcomit.statement import Transaction

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = json.loads((ROOT / "tests" / "expected_findings.json").read_text())


def txn(day, description, amount, card=True):
    d = date(2026, 7, 1) + timedelta(days=day) if isinstance(day, int) else day
    return Transaction(d, description, amount, "4421 9987", "5521" if card else "", "Sara Ahmed")


def without_ids(items):
    return sorted(({k: v for k, v in i.items() if k != "id"} for i in items), key=json.dumps)


# --- The real fake statement: exactly the planted items -----------------------

def test_finds_exactly_the_planted_subscriptions():
    txns = statement.load(ROOT / "data" / "statement.csv")
    assert without_ids(find_subscriptions(txns)) == without_ids(EXPECTED["subscriptions"])


def test_finds_exactly_the_planted_alerts():
    txns = statement.load(ROOT / "data" / "statement.csv")
    assert without_ids(find_alerts(txns)) == without_ids(EXPECTED["alerts"])


def test_subscriptions_cost_what_the_video_says():
    txns = statement.load(ROOT / "data" / "statement.csv")
    monthly = round(-sum(s["amount"] for s in find_subscriptions(txns)), 2)
    assert monthly == EXPECTED["subscriptions_total"]["monthly"]
    assert round(monthly * 12, 2) == EXPECTED["subscriptions_total"]["yearly"]


def test_still_correct_with_october_added():
    txns = statement.load(ROOT / "data" / "statement.csv", ROOT / "data" / "statement_2026-10.csv")
    names = {s["description"] for s in find_subscriptions(txns)}
    assert names == {s["description"] for s in EXPECTED["subscriptions"]}
    assert {a["type"] for a in find_alerts(txns)} == {"large", "double", "new_abroad"}
    assert len(find_alerts(txns)) == 3


# --- Subscriptions: look-alikes are not flagged -------------------------------

def test_monthly_card_charge_is_a_subscription():
    txns = [txn(0, "NETFLIX.COM", -15.49), txn(31, "NETFLIX.COM", -15.49), txn(62, "NETFLIX.COM", -15.49)]
    assert find_subscriptions(txns) == [
        {"description": "NETFLIX.COM", "amount": -15.49, "dates": ["2026-07-01", "2026-08-01", "2026-09-01"]},
    ]


def test_two_charges_are_not_enough():
    assert find_subscriptions([txn(0, "GYM", -39.0), txn(31, "GYM", -39.0)]) == []


def test_rent_by_transfer_is_not_a_subscription():
    txns = [txn(d, "ONLINE TRANSFER TO LANDLORD", -1450.0, card=False) for d in (0, 31, 62)]
    assert find_subscriptions(txns) == []


def test_coffee_at_random_amounts_is_not_a_subscription():
    txns = [txn(d, "STARBUCKS", a) for d, a in [(0, -4.25), (31, -6.10), (62, -7.80)]]
    assert find_subscriptions(txns) == []


def test_weekly_charge_is_not_monthly():
    txns = [txn(d, "HEB", -50.0) for d in (0, 7, 14, 21)]
    assert find_subscriptions(txns) == []


def test_small_price_change_still_counts():
    txns = [txn(0, "SPOTIFY", -11.99), txn(31, "SPOTIFY", -11.99), txn(62, "SPOTIFY", -12.29)]
    assert find_subscriptions(txns)[0]["amount"] == -12.29


def test_money_in_is_never_a_subscription():
    txns = [txn(d, "PAYROLL", 2100.0, card=False) for d in (0, 31, 62)]
    assert find_subscriptions(txns) == []


# --- Alerts -------------------------------------------------------------------

NORMAL = [txn(i, f"SHOP {i}", -30.0 - i) for i in range(20)]


def test_large_charge():
    alerts = find_alerts(NORMAL + [txn(30, "BESTBUY", -1899.0)])
    assert [a["type"] for a in alerts] == ["large"]


def test_big_but_normal_bill_is_not_large():
    assert find_alerts(NORMAL + [txn(30, "SOUTHWEST AIR", -284.0)]) == []


def test_rent_is_not_large():
    assert find_alerts(NORMAL + [txn(30, "ONLINE TRANSFER TO LANDLORD", -1450.0, card=False)]) == []


def test_double_charge_is_one_alert():
    alerts = find_alerts(NORMAL + [txn(30, "AMZN MKTP", -84.37), txn(30, "AMZN MKTP", -84.37)])
    assert alerts == [{"type": "double", "description": "AMZN MKTP", "amount": -84.37,
                       "date": "2026-07-31", "count": 2}]


def test_two_coffees_at_different_prices_are_not_double():
    assert find_alerts(NORMAL + [txn(30, "STARBUCKS", -4.75), txn(30, "STARBUCKS", -6.20)]) == []


def test_same_shop_same_amount_on_different_days_is_not_double():
    assert find_alerts(NORMAL + [txn(30, "AMZN MKTP", -20.0), txn(31, "AMZN MKTP", -20.0)]) == []


def test_new_shop_with_country_code_is_abroad():
    alerts = find_alerts(NORMAL + [txn(30, "HOTEL ALFAMA LISBOA PRT", -312.40)])
    assert [a["type"] for a in alerts] == ["new_abroad"]


def test_new_shop_with_matching_foreign_fee_is_abroad():
    alerts = find_alerts(NORMAL + [txn(30, "HOTEL ALFAMA LISBOA", -312.40),
                                   txn(30, "FOREIGN TRANSACTION FEE", -9.37, card=False)])
    assert [(a["type"], a["description"]) for a in alerts] == [("new_abroad", "HOTEL ALFAMA LISBOA")]


def test_local_shop_on_the_same_day_as_a_foreign_fee_is_not_abroad():
    alerts = find_alerts(NORMAL + [txn(30, "HOTEL ALFAMA LISBOA PRT", -312.40),
                                   txn(30, "FOREIGN TRANSACTION FEE", -9.37, card=False),
                                   txn(30, "TACO STAND AUSTIN TX", -12.00)])
    assert [a["description"] for a in alerts] == ["HOTEL ALFAMA LISBOA PRT"]


def test_web_address_ending_is_not_a_country():
    assert find_alerts(NORMAL + [txn(30, "UBER *TRIP HELP.UBER.COM", -18.0)]) == []


def test_shop_seen_before_is_not_new():
    alerts = find_alerts(NORMAL + [txn(0, "CAFE LISBOA PRT", -10.0), txn(30, "CAFE LISBOA PRT", -12.0)])
    assert [a["date"] for a in alerts] == ["2026-07-01"]


def test_empty_statement():
    assert find_subscriptions([]) == [] and find_alerts([]) == []
