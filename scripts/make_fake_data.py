"""Make the fake bank statements and receipts. All data is synthetic.

Usage: python scripts/make_fake_data.py
Writes data/statement.csv, data/statement_2026-10.csv and data/receipts/*.txt.
The seed is fixed, so everyone gets identical files.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
COLUMNS = ["date", "description", "amount", "account_number", "card_last4", "account_holder"]
HOLDER, ACCOUNT, CARD = "Sara Ahmed", "4421 9987", "5521"

rng = random.Random(2026)
_used = set()


def amt(desc, lo, hi):
    """Random amount, never repeated for the same description (no accidental subscriptions)."""
    while True:
        a = round(rng.uniform(lo, hi), 2)
        if (desc, a) not in _used:
            _used.add((desc, a))
            return -a


def row(day, desc, amount, card=False):
    return [day.isoformat(), desc, f"{amount:.2f}", ACCOUNT, CARD if card else "", HOLDER]


def rand_days(n, start, end):
    span = (end - start).days
    return sorted(start + timedelta(days=rng.randint(0, span)) for _ in range(n))


def monthly(months, day_of_month, desc, amount=None, lo=0, hi=0, card=False):
    return [row(date(2026, m, day_of_month), desc, amount if amount is not None else amt(desc, lo, hi), card) for m in months]


def common(months):
    """Rows shared by the summer statement and the October one."""
    rows = []
    rows += monthly(months, 1, "ONLINE TRANSFER TO LANDLORD REF 7781", -1450.00)
    for m in months:
        for d in (1, 15):
            rows.append(row(date(2026, m, d), "PAYROLL DEPOSIT ACME CORP", 2100.00))
    return rows


def summer():
    start, end = date(2026, 7, 1), date(2026, 9, 30)
    months = (7, 8, 9)
    rows = common(months)

    # A. Subscriptions
    rows += monthly(months, 3, "NETFLIX.COM LOS GATOS CA", -15.49, card=True)
    rows += monthly(months, 12, "SPOTIFY USA NEW YORK NY", -11.99, card=True)
    rows += monthly(months, 1, "IRONWORKS GYM AUSTIN TX", -39.00, card=True)
    rows += monthly(months, 21, "CLOUDVAULT STORAGE SAN JOSE CA", -2.99, card=True)

    # B. Strange charges
    rows.append(row(date(2026, 9, 14), "BESTBUY 00012345 AUSTIN TX", -1899.00, True))
    rows += [row(date(2026, 8, 19), "AMZN MKTP US*2K4LQ8", -84.37, True)] * 2
    rows.append(row(date(2026, 9, 26), "HOTEL ALFAMA LISBOA PRT", -312.40, True))
    rows.append(row(date(2026, 9, 26), "FOREIGN TRANSACTION FEE", -9.37))
    rows.append(row(date(2026, 9, 26), "STARBUCKS #1234 AUSTIN TX", -5.15, True))
    _used.add(("STARBUCKS #1234 AUSTIN TX", -5.15))

    # C. Look-alikes
    for d in rand_days(9, start, end):
        if d != date(2026, 9, 26):
            rows.append(row(d, "STARBUCKS #1234 AUSTIN TX", amt("STARBUCKS #1234 AUSTIN TX", 4.25, 7.80), True))
    for d in rand_days(8, start, end):
        rows.append(row(d, "UBER *TRIP HELP.UBER.COM", amt("UBER", 8, 42), True))
    rows += monthly(months, 18, "AUSTIN ENERGY BILL PAY", lo=78, hi=121)
    rows += monthly(months, 25, "AT&T BILL PAY", lo=62, hi=88)
    d = date(2026, 7, 4)
    for i in range(13):
        shop = "HEB #482 AUSTIN TX" if i % 2 == 0 else "WHOLEFDS AUS 10233"
        rows.append(row(d, shop, amt(shop, 35, 180), True))
        d += timedelta(days=7)

    # D. Fill
    dining = ["TORCHYS TACOS AUSTIN TX", "FRANKLIN BARBECUE AUSTIN TX", "CHIPOTLE 1842 AUSTIN TX",
              "JUSTINES CAFE AUSTIN TX", "DOORDASH*PAD THAI HOUSE", "DOORDASH*SLICE PIZZA", "DOORDASH*TACO DELI"]
    for day in rand_days(40, start, end):
        shop = rng.choice(dining)
        rows.append(row(day, shop, amt(shop, 9, 64), True))
    for day in rand_days(2, start, end):
        rows.append(row(day, "SHELL OIL 5741 AUSTIN TX", amt("SHELL", 28, 55), True))
    for day in rand_days(10, start, end):
        code = "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", k=6))
        shop = f"AMZN MKTP US*{code}"
        rows.append(row(day, shop, amt(shop, 9, 140), True))
    for day in rand_days(8, start, end):
        rows.append(row(day, "TARGET 00023 AUSTIN TX", amt("TARGET", 14, 120), True))
    for day in rand_days(4, start, end):
        rows.append(row(day, "CVS/PHARMACY #0912 AUSTIN TX", amt("CVS", 6, 48), True))
    for day in rand_days(3, start, end):
        rows.append(row(day, "AMC THEATRES 4421 AUSTIN TX", amt("AMC", 12, 38), True))
    for day in rand_days(2, start, end):
        shop = "AUSTIN360 TICKETS AUSTIN TX"
        rows.append(row(day, shop, amt(shop, 45, 140), True))
    rows.append(row(date(2026, 9, 10), "SOUTHWEST AIR 5262345678901", -284.00, True))
    one_offs = ["BOOK PEOPLE AUSTIN TX", "ZILKER HARDWARE AUSTIN TX", "TECOVAS BOOTS AUSTIN TX",
                "AUSTIN PET SUPPLY AUSTIN TX", "BARTON SPRINGS CAFE AUSTIN TX", "LAMAR FLORIST AUSTIN TX",
                "SOUTH CONGRESS BIKES AUSTIN TX", "TERRA TOYS AUSTIN TX"]
    for shop, day in zip(one_offs, rand_days(len(one_offs), start, end)):
        rows.append(row(day, shop, amt(shop, 12, 95), True))

    # E. Private details
    rows.append(row(date(2026, 7, 9), "ZELLE TO OMAR KHAN", -60.00))
    rows.append(row(date(2026, 8, 7), "ZELLE FROM HINA RAZA", 45.00))
    rows.append(row(date(2026, 8, 28), "TRANSFER TO SAVINGS ACCT 4421 9987 0012", -300.00))
    rows.append(row(date(2026, 9, 5), "SQ *BLUE DOOR LLC", -23.50, True))

    return sorted(rows, key=lambda r: r[0])


def october():
    start, end = date(2026, 10, 1), date(2026, 10, 20)
    rows = common((10,))
    rows += monthly((10,), 1, "IRONWORKS GYM AUSTIN TX", -39.00, card=True)
    rows += monthly((10,), 3, "NETFLIX.COM LOS GATOS CA", -15.49, card=True)
    rows += monthly((10,), 12, "SPOTIFY USA NEW YORK NY", -11.99, card=True)
    rows += monthly((10,), 18, "AUSTIN ENERGY BILL PAY", lo=78, hi=121)
    for d in (date(2026, 10, 6), date(2026, 10, 13), date(2026, 10, 19)):
        rows.append(row(d, "STARBUCKS #1234 AUSTIN TX", amt("STARBUCKS #1234 AUSTIN TX", 4.25, 7.80), True))
    for d, shop in zip((date(2026, 10, 3), date(2026, 10, 10), date(2026, 10, 17)),
                       ("HEB #482 AUSTIN TX", "WHOLEFDS AUS 10233", "HEB #482 AUSTIN TX")):
        rows.append(row(d, shop, amt(shop, 35, 180), True))
    for d in (date(2026, 10, 8), date(2026, 10, 16)):
        rows.append(row(d, "UBER *TRIP HELP.UBER.COM", amt("UBER", 8, 42), True))
    rows.append(row(date(2026, 10, 9), "SHELL OIL 5741 AUSTIN TX", amt("SHELL", 28, 55), True))
    for d, shop in zip((date(2026, 10, 5), date(2026, 10, 11), date(2026, 10, 18)),
                       ("TORCHYS TACOS AUSTIN TX", "DOORDASH*SLICE PIZZA", "CHIPOTLE 1842 AUSTIN TX")):
        rows.append(row(d, shop, amt(shop, 9, 64), True))
    rows.append(row(date(2026, 10, 14), "TARGET 00023 AUSTIN TX", amt("TARGET", 14, 120), True))
    return sorted(rows, key=lambda r: r[0])


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)


RECEIPT_HEADER = """{store}
{address}

Customer: Sara Ahmed
Email: sara.ahmed@example.com
Phone: (512) 555-0142
Deliver to: 1207 Rainey St Apt 5B, Austin TX 78701
"""

RECEIPTS = {
    "receipt_amazon_2026-08-19.txt": ("AMAZON.COM", "Order #111-2204518-7731 | 2026-08-19", [("USB-C hub, 7-port", 84.37)]),
    "receipt_bestbuy_2026-09-14.txt": ("BEST BUY #123", "Austin TX | 2026-09-14", [("4K monitor 32in", 1899.00)]),
    "receipt_heb_2026-07-11.txt": ("H-E-B #482", "Austin TX | 2026-07-11", [("Groceries", 112.64)]),
    "receipt_torchys_2026-08-02.txt": ("TORCHYS TACOS", "Austin TX | 2026-08-02", [("Tacos x3", 21.50), ("Queso", 6.25)]),
    "receipt_target_2026-08-23.txt": ("TARGET #00023", "Austin TX | 2026-08-23", [("Home goods", 58.10)]),
    "receipt_cvs_2026-09-02.txt": ("CVS/PHARMACY #0912", "Austin TX | 2026-09-02", [("Pharmacy", 27.34)]),
}


def write_receipts(folder):
    folder.mkdir(exist_ok=True)
    for name, (store, where, items) in RECEIPTS.items():
        lines = RECEIPT_HEADER.format(store=store, address=where).splitlines()
        lines.append("")
        lines += [f"  {item:<28}{price:>10.2f}" for item, price in items]
        lines += ["", f"  {'TOTAL':<28}{sum(p for _, p in items):>10.2f}", "", f"Paid with card ending {CARD}", ""]
        (folder / name).write_text("\n".join(lines))


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    write_csv(DATA / "statement.csv", summer())
    write_csv(DATA / "statement_2026-10.csv", october())
    write_receipts(DATA / "receipts")
    print("wrote data/statement.csv, data/statement_2026-10.csv, data/receipts/")
