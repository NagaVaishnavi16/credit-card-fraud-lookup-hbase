"""
load_data.py
------------
Reads creditcard.csv, assigns synthetic CardHash IDs, builds
RowKey = CardHash_PaddedTime, and inserts records into HBase.

Usage:
    python scripts/load_data.py --input data/creditcard.csv --limit 5000
"""

import argparse
import hashlib
import random
import sys
import pandas as pd
import happybase

HBASE_HOST  = "localhost"
TABLE_NAME  = "FraudTxn"
BATCH_SIZE  = 200
NUM_CARDS   = 20   # synthetic card pool size


def generate_card_pool(n: int) -> list:
    """Create n synthetic card hashes to simulate real card IDs."""
    random.seed(42)
    return [
        hashlib.md5(f"CARD_{i}".encode()).hexdigest()[:8]
        for i in range(n)
    ]


def build_row_key(card_hash: str, time_offset: float) -> bytes:
    """
    RowKey = <CardHash>_<PaddedTimestamp>

    Zero-padding the timestamp to 10 digits ensures lexicographic
    sort == chronological sort within each card's row range.
    This lets HBase prefix scans retrieve a card's full history
    in one sequential read rather than scattered random I/O.

    Example: 'a3f9c21b_0000086400'
    """
    padded_time = str(int(time_offset)).zfill(10)
    return f"{card_hash}_{padded_time}".encode()


def load(csv_path: str, limit: int):
    print(f"[INFO] Reading {csv_path} ...")
    df = pd.read_csv(csv_path)
    if limit:
        df = df.head(limit)
    print(f"[INFO] Loaded {len(df)} rows  |  Fraud rows: {df['Class'].sum()}")

    # Assign a synthetic CardHash to each row
    card_pool = generate_card_pool(NUM_CARDS)
    random.seed(0)
    df["CardHash"] = [random.choice(card_pool) for _ in range(len(df))]

    # Connect to HBase
    try:
        conn = happybase.Connection(HBASE_HOST)
        conn.open()
    except Exception as e:
        print(f"[ERROR] Cannot connect to HBase: {e}")
        print("[HINT]  Is HBase running? Check: docker ps | grep hbase")
        sys.exit(1)

    # Create table if it doesn't exist
    existing = [t.decode() for t in conn.tables()]
    if TABLE_NAME not in existing:
        print(f"[INFO] Creating table '{TABLE_NAME}' ...")
        conn.create_table(
            TABLE_NAME,
            {"TxnDetails": dict()}
        )
    else:
        print(f"[INFO] Table '{TABLE_NAME}' already exists — inserting records.")

    table  = conn.table(TABLE_NAME)
    total  = 0
    errors = 0

    # Batch insert
    with table.batch(batch_size=BATCH_SIZE) as batch:
        for _, row in df.iterrows():
            row_key = build_row_key(row["CardHash"], row["Time"])

            data = {
                b"TxnDetails:amount":      str(round(row["Amount"], 4)).encode(),
                b"TxnDetails:time_offset": str(int(row["Time"])).encode(),
                b"TxnDetails:label":       str(int(row["Class"])).encode(),
                b"TxnDetails:card_hash":   row["CardHash"].encode(),
            }

            # Store a few PCA features for completeness
            for v in ["V1", "V2", "V3", "V4", "V5"]:
                data[f"TxnDetails:{v.lower()}".encode()] = str(round(row[v], 6)).encode()

            try:
                batch.put(row_key, data)
                total += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"[WARN] Insert failed for {row_key}: {e}")

    print(f"\n[DONE] Inserted {total} records  |  Errors: {errors}")

    # Quick verification scan
    print("\n[VERIFY] Sample rows from HBase:")
    for key, data in table.scan(limit=3):
        print(f"  RowKey : {key.decode()}")
        print(f"  Amount : {data[b'TxnDetails:amount'].decode()}")
        print(f"  Label  : {data[b'TxnDetails:label'].decode()}")
        print()

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/creditcard.csv")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Rows to load (default 5000; use 0 for all)")
    args = parser.parse_args()
    load(args.input, args.limit or None)
