# Private details to hide

All values are fake. `redact.py` must replace each one with a label before anything is sent to the model.

## Must hide

| Detail | Where it appears | Label |
|---|---|---|
| `Sara Ahmed` | `account_holder` column (every row), receipts | `[NAME_1]` |
| `Omar Khan` | `ZELLE TO OMAR KHAN` | `[NAME_2]` |
| `Hina Raza` | `ZELLE FROM HINA RAZA` | `[NAME_3]` |
| `4421 9987` | `account_number` column (every row), `TRANSFER TO SAVINGS ACCT 4421 9987 0012` | `[ACCT_1]` |
| `4421 9987 0012` | the savings transfer description (a longer account number that starts with the one above) | `[ACCT_2]` |
| `5521` (card last 4) | `card_last4` column, "card ending 5521" in receipts | `[CARD_1]` |
| `sara.ahmed@example.com` | receipts | `[EMAIL_1]` |
| `(512) 555-0142` | receipts | `[PHONE_1]` |
| `1207 Rainey St Apt 5B, Austin TX 78701` | receipts, "Deliver to" line | `[ADDRESS_1]` |

Same value, same label, everywhere. Names appear in any case and with spaces or dashes inside account numbers (Day 3 tests).

## Must stay visible

| Detail | Why it's a trap |
|---|---|
| Shop names (`NETFLIX.COM`, `STARBUCKS #1234`, `IRONWORKS GYM`, `SQ *BLUE DOOR LLC`...) | The model needs them to categorize |
| `AMC THEATRES 4421 AUSTIN TX` | `4421` is a store number, not the account. Redact `4421 9987`, not every `4421` |
| `SOUTHWEST AIR 5262345678901` | A long digit run that is not a card number |
| `ONLINE TRANSFER TO LANDLORD REF 7781`, `HEB #482`, `AMZN MKTP US*2K4LQ8` | Reference and store numbers |
| Amounts, dates, city and state in shop names | Needed for the finders |
| Receipt store addresses, order numbers (`#111-2204518-7731`) | Not about Sara |
