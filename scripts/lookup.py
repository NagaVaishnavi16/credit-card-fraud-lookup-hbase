"""
lookup.py
---------
Retrieves the last N transactions for a given CardHash from HBase,
applies the fraud rule engine, and prints a risk assessment.

Usage:
    # Look up a specific card:
    python scripts/lookup.py --card a3f9c21b

    # Run against a random sample of cards loaded in HBase:
    python scripts/lookup.py --sample 10

How the HBase lookup works
--------------------------
RowKey format: <CardHash>_<PaddedTimestamp>

Because all rows for a card share the same CardHash prefix and timestamps
are zero-padded, HBase stores them contiguously in sorted order.

A prefix scan:
    STARTROW = 'a3f9c21b_'
    STOPROW  = 'a3f9c21b`'   ← backtick is ASCII 96, one above '_' (95)

...performs a single seek + sequential read to fetch all card rows.
We then tail the list for the N most recent transactions.
"""
from fraud_rules import evaluate
import sys
import argparse
import random
import time
import happybase

HBASE_HOST  = "localhost"
TABLE_NAME  = "FraudTxn"
HISTORY_N   = 5     # how many past transactions to consider


# ---------------------------------------------------------------------------
# HBase retrieval
# ---------------------------------------------------------------------------

def get_card_transactions(table: happybase.Table, card_hash: str, limit: int = 20) -> list:
    """
    Prefix scan to fetch up to `limit` rows for a given card.
    Returns list of transaction dicts sorted by time ascending.

    The STOPROW trick: '_' is ASCII 95; '`' is ASCII 96.
    So STOPROW = card_hash + '`' ends the scan exactly after the card's rows.
    """
    start_row = f"{card_hash}_".encode()
    stop_row  = f"{card_hash}`".encode()

    txns = []
    for _key, data in table.scan(row_start=start_row, row_stop=stop_row, limit=limit):
        try:
            txns.append({
                "card_hash":   data[b"TxnDetails:card_hash"].decode(),
                "amount":      float(data[b"TxnDetails:amount"].decode()),
                "time_offset": int(data[b"TxnDetails:time_offset"].decode()),
                "label":       int(data[b"TxnDetails:label"].decode()),
            })
        except KeyError:
            continue  # skip malformed rows

    # sort by time ascending (should already be sorted by RowKey, but be safe)
    txns.sort(key=lambda t: t["time_offset"])
    return txns


def get_all_card_hashes(table: happybase.Table, sample_size: int = 10) -> list:
    """Scan a small portion of the table to collect distinct CardHash values."""
    seen    = set()
    hashes  = []
    for key, _ in table.scan(limit=5000):
        card_hash = key.decode().split("_")[0]
        if card_hash not in seen:
            seen.add(card_hash)
            hashes.append(card_hash)
    random.shuffle(hashes)
    return hashes[:sample_size]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
def print_assessment(card_hash, current_txn, history, result, lookup_ms):
    sep = "─" * 56

    print(f"\n{sep}")
    print(f"  Card       : {card_hash}")
    print(f"  Lookup Time: {lookup_ms:.2f} ms")
    print(f"  Amount     : ${current_txn['amount']:.2f}")
    print(f"  Time       : {current_txn['time_offset']}s")
    print(f"  GT Label   : {'FRAUD' if current_txn['label'] == 1 else 'legit'}")
    print(f"  History    : {len(history)} prior transaction(s)")
    print(sep)

    if history:
        print("\n  Last Transactions:")
        for txn in history:
            print(
                f"    Time={txn['time_offset']}s "
                f"Amount=${txn['amount']:.2f}"
            )

    print(f"\n  Risk Score : {result['risk_score']:.2f} / 1.00")
    print(f"  Risk Level : {result['risk_level']}")
    print(f"  Decision   : {result['recommendation']}")

    if result["triggered"]:
        print(f"\n  Rules Triggered ({len(result['triggered'])}):")
        for rule in result["triggered"]:
            print(f"    ✗ {rule}")
            print(f"      {result['details'][rule]}")
    else:
        print("\n  No rules triggered.")

    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_lookup(card_hash: str, table: happybase.Table):

    start = time.perf_counter()

    all_txns = get_card_transactions(
        table,
        card_hash,
        limit=HISTORY_N + 1
    )

    lookup_ms = (time.perf_counter() - start) * 1000

    if not all_txns:
        print(f"[WARN] No transactions found for card: {card_hash}")
        return

    current_txn = all_txns[-1]
    history = all_txns[:-1]

    result = evaluate(current_txn, history)

    print_assessment(
        card_hash,
        current_txn,
        history,
        result,
        lookup_ms
    )


def main():
    parser = argparse.ArgumentParser(
        description="Fraud rule lookup against HBase FraudTxn table"
    )
    parser.add_argument("--card",   type=str, help="CardHash to look up (8 hex chars)")
    parser.add_argument("--sample", type=int, default=0,
                        help="Assess N random cards from HBase")
    args = parser.parse_args()

    if not args.card and not args.sample:
        parser.print_help()
        sys.exit(1)

    try:
        conn = happybase.Connection(HBASE_HOST)
        conn.open()
    except Exception as e:
        print(f"[ERROR] Cannot connect to HBase at {HBASE_HOST}: {e}")
        print("[HINT]  Run: docker ps | grep hbase")
        sys.exit(1)

    table = conn.table(TABLE_NAME)

    if args.card:
        run_lookup(args.card, table)

    elif args.sample:
        print(f"[INFO] Sampling {args.sample} cards from HBase ...")
        cards = get_all_card_hashes(table, sample_size=args.sample)
        if not cards:
            print("[ERROR] No cards found. Did you run load_data.py first?")
        for card_hash in cards:
            run_lookup(card_hash, table)

    conn.close()


if __name__ == "__main__":
    main()
