"""
Synthetic UPI Transaction Data Generator
=========================================

Generates a labeled dataset of simulated UPI transactions for use in
training and evaluating the fraud detection system, since real UPI
transaction data is not available for this project.

The generator works in two stages:

1. **Legitimate transaction simulation** — a pool of synthetic users is
   created, each with a stable "home" behavioral profile (typical bank,
   location, device, spending amount, active hours). Legitimate
   transactions are sampled around each user's own profile, so the
   resulting dataset has realistic per-user behavioral consistency for
   feature engineering to key off of later.

2. **Fraud injection** — for a configurable fraction of transactions,
   one of the fraud patterns defined in `docs/project_specification.md`
   (Section 3) is simulated by deliberately deviating from the sender's
   normal profile in the way that pattern implies (new device + new
   location, high-value outlier, transaction bursts, etc.).

Output columns match the schema defined in
`docs/project_specification.md` (Section 4), plus one additional
`fraud_type` column that records which fraud pattern was simulated
(empty for legitimate transactions). This column is not part of the
model's *output* schema — it exists only in this labeled training data
so later phases can evaluate performance per fraud type.

Usage:
    python src/data/generate_transactions.py \
        --n-transactions 50000 \
        --fraud-rate 0.04 \
        --seed 42 \
        --output data/raw/synthetic_transactions.csv
"""

from __future__ import annotations

import argparse
import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Reference data pools
# ---------------------------------------------------------------------------

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Kolkata", "Chennai", "Hyderabad",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Surat", "Nagpur",
    "Indore", "Bhopal", "Patna", "Kochi", "Chandigarh", "Guwahati",
]

BANKS = [
    "SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank",
    "Punjab National Bank", "Bank of Baroda", "Canara Bank",
    "IDFC First Bank", "Yes Bank", "Union Bank of India", "Indian Bank",
]

TRANSACTION_TYPES = ["P2P", "P2M", "COLLECT"]
TRANSACTION_TYPE_WEIGHTS = [0.55, 0.35, 0.10]

FRAUD_TYPES = [
    "account_takeover",
    "phishing_induced",
    "mule_account",
    "velocity_fraud",
    "micro_transaction_probing",
    "unusual_geo_device",
    "high_value_anomaly",
    "odd_hour_fraud",
]

DATE_RANGE_DAYS = 90
END_DATE = datetime(2026, 8, 28)
START_DATE = END_DATE - timedelta(days=DATE_RANGE_DAYS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rand_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _make_upi_id(name_hint: str) -> str:
    handle = random.choice(["okhdfcbank", "okicici", "oksbi", "okaxis", "ybl", "paytm"])
    return f"{name_hint.lower()}{random.randint(1, 999)}@{handle}"


def _make_device_id() -> str:
    return f"dev_{_rand_suffix(10)}"


def _make_ip() -> str:
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _random_timestamp_in_range(start: datetime, end: datetime) -> datetime:
    delta = end - start
    seconds_offset = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=seconds_offset)


def _sample_hour_from_profile(typical_hours: list[int]) -> int:
    """Sample an hour of day, weighted heavily toward a user's typical hours."""
    if random.random() < 0.85:
        return random.choice(typical_hours)
    return random.randint(0, 23)


# ---------------------------------------------------------------------------
# User profile model
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    user_id: int
    account_id: str
    upi_id: str
    home_bank: str
    home_location: str
    home_device: str
    avg_amount: float
    amount_std: float
    typical_hours: list[int]
    known_receivers: list[str] = field(default_factory=list)


def build_user_pool(n_users: int) -> list[UserProfile]:
    users = []
    for uid in range(n_users):
        avg_amount = float(np.random.lognormal(mean=6.5, sigma=0.9))  # ~ hundreds to a few thousand INR
        avg_amount = max(50.0, min(avg_amount, 50000.0))
        typical_hour_center = random.choices(
            population=[9, 13, 19, 21],  # morning / lunch / evening / night peaks
            weights=[0.25, 0.2, 0.35, 0.2],
        )[0]
        typical_hours = sorted({
            (typical_hour_center + offset) % 24 for offset in range(-2, 3)
        })
        name_hint = f"user{uid}"
        users.append(UserProfile(
            user_id=uid,
            account_id=f"ACC{100000 + uid}",
            upi_id=_make_upi_id(name_hint),
            home_bank=random.choice(BANKS),
            home_location=random.choice(CITIES),
            home_device=_make_device_id(),
            avg_amount=round(avg_amount, 2),
            amount_std=round(avg_amount * 0.35, 2),
            typical_hours=typical_hours,
        ))
    return users


def build_receiver_pool(n_receivers: int) -> list[str]:
    """A shared pool of receiver UPI IDs (merchants + individuals)."""
    receivers = []
    for i in range(n_receivers):
        prefix = random.choice(["merchant", "shop", "store", "biz", "person"])
        receivers.append(_make_upi_id(f"{prefix}{i}"))
    return receivers


# ---------------------------------------------------------------------------
# Legitimate transaction generation
# ---------------------------------------------------------------------------

def make_legit_transaction(user: UserProfile, receiver_pool: list[str]) -> dict:
    # Mostly transact with a known receiver; occasionally a new one
    if user.known_receivers and random.random() < 0.75:
        receiver_upi = random.choice(user.known_receivers)
        is_new_receiver = False
    else:
        receiver_upi = random.choice(receiver_pool)
        if receiver_upi not in user.known_receivers:
            user.known_receivers.append(receiver_upi)
        is_new_receiver = len(user.known_receivers) == 1 or random.random() < 0.3

    amount = max(10.0, np.random.normal(user.avg_amount, user.amount_std))
    ts_date = _random_timestamp_in_range(START_DATE, END_DATE)
    hour = _sample_hour_from_profile(user.typical_hours)
    timestamp = ts_date.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))

    return {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "sender_upi_id": user.upi_id,
        "receiver_upi_id": receiver_upi,
        "sender_account_id": user.account_id,
        "receiver_account_id": f"RCV{abs(hash(receiver_upi)) % 900000 + 100000}",
        "amount": round(amount, 2),
        "transaction_type": random.choices(TRANSACTION_TYPES, weights=TRANSACTION_TYPE_WEIGHTS)[0],
        "device_id": user.home_device,
        "ip_address": _make_ip(),
        "location": user.home_location,
        "sender_bank": user.home_bank,
        "receiver_bank": random.choice(BANKS),
        "is_new_device": False,
        "is_new_receiver": is_new_receiver,
        "transaction_status": random.choices(
            ["SUCCESS", "FAILED", "PENDING"], weights=[0.94, 0.04, 0.02]
        )[0],
        "label_is_fraud": False,
        "fraud_type": "",
    }


# ---------------------------------------------------------------------------
# Fraud transaction generation (one function per pattern, Section 3 of spec)
# ---------------------------------------------------------------------------

def _base_fraud_row(user: UserProfile, receiver_upi: str, amount: float,
                     timestamp: datetime, device: str, location: str,
                     fraud_type: str, is_new_receiver: bool = True,
                     is_new_device: bool = True) -> dict:
    return {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "sender_upi_id": user.upi_id,
        "receiver_upi_id": receiver_upi,
        "sender_account_id": user.account_id,
        "receiver_account_id": f"RCV{abs(hash(receiver_upi)) % 900000 + 100000}",
        "amount": round(amount, 2),
        "transaction_type": random.choices(TRANSACTION_TYPES, weights=TRANSACTION_TYPE_WEIGHTS)[0],
        "device_id": device,
        "ip_address": _make_ip(),
        "location": location,
        "sender_bank": user.home_bank,
        "receiver_bank": random.choice(BANKS),
        "is_new_device": is_new_device,
        "is_new_receiver": is_new_receiver,
        "transaction_status": random.choices(
            ["SUCCESS", "FAILED", "PENDING"], weights=[0.88, 0.08, 0.04]
        )[0],
        "label_is_fraud": True,
        "fraud_type": fraud_type,
    }


def fraud_account_takeover(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    new_device = _make_device_id()
    new_location = random.choice([c for c in CITIES if c != user.home_location])
    receiver = random.choice(receiver_pool)
    amount = max(500.0, np.random.normal(user.avg_amount * 3, user.amount_std))
    odd_hour = random.choice([1, 2, 3, 4, 23])
    ts = _random_timestamp_in_range(START_DATE, END_DATE).replace(hour=odd_hour, minute=random.randint(0, 59))
    return [_base_fraud_row(user, receiver, amount, ts, new_device, new_location, "account_takeover")]


def fraud_phishing_induced(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    receiver = random.choice(receiver_pool)
    amount = max(1000.0, np.random.normal(user.avg_amount * 4, user.amount_std * 1.5))
    hour = _sample_hour_from_profile(user.typical_hours)  # victim-authorized: normal-looking hour
    ts = _random_timestamp_in_range(START_DATE, END_DATE).replace(hour=hour, minute=random.randint(0, 59))
    return [_base_fraud_row(
        user, receiver, amount, ts, user.home_device, user.home_location,
        "phishing_induced", is_new_receiver=True, is_new_device=False,
    )]


def fraud_mule_account(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    """Rapid, large in/out transfers through a receiver acting as a mule."""
    receiver = random.choice(receiver_pool)
    base_ts = _random_timestamp_in_range(START_DATE, END_DATE)
    rows = []
    n_hops = random.randint(2, 4)
    for i in range(n_hops):
        amount = max(2000.0, np.random.normal(user.avg_amount * 5, user.amount_std * 2))
        ts = base_ts + timedelta(minutes=random.randint(1, 10) * (i + 1))
        rows.append(_base_fraud_row(
            user, receiver, amount, ts, user.home_device, user.home_location, "mule_account",
            is_new_device=False,
        ))
    return rows


def fraud_velocity(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    """A burst of many transactions in a short window."""
    base_ts = _random_timestamp_in_range(START_DATE, END_DATE)
    rows = []
    n_txns = random.randint(6, 12)
    for i in range(n_txns):
        receiver = random.choice(receiver_pool)
        amount = max(50.0, np.random.normal(user.avg_amount * 0.6, user.amount_std * 0.5))
        ts = base_ts + timedelta(seconds=random.randint(10, 90) * (i + 1))
        rows.append(_base_fraud_row(
            user, receiver, amount, ts, user.home_device, user.home_location, "velocity_fraud",
            is_new_device=False,
        ))
    return rows


def fraud_micro_probing(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    """Small test transactions followed by one larger one."""
    base_ts = _random_timestamp_in_range(START_DATE, END_DATE)
    receiver = random.choice(receiver_pool)
    rows = []
    n_probes = random.randint(2, 4)
    for i in range(n_probes):
        amount = round(random.uniform(1.0, 20.0), 2)
        ts = base_ts + timedelta(minutes=random.randint(1, 5) * (i + 1))
        rows.append(_base_fraud_row(
            user, receiver, amount, ts, user.home_device, user.home_location, "micro_transaction_probing",
            is_new_device=False,
        ))
    # Follow-up larger extraction attempt
    big_amount = max(1000.0, np.random.normal(user.avg_amount * 3, user.amount_std))
    big_ts = base_ts + timedelta(minutes=random.randint(10, 20))
    rows.append(_base_fraud_row(
        user, receiver, big_amount, big_ts, user.home_device, user.home_location, "micro_transaction_probing",
        is_new_device=False,
    ))
    return rows


def fraud_unusual_geo_device(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    new_device = _make_device_id()
    new_location = random.choice([c for c in CITIES if c != user.home_location])
    receiver = random.choice(receiver_pool)
    amount = max(200.0, np.random.normal(user.avg_amount, user.amount_std))
    hour = random.randint(0, 23)
    ts = _random_timestamp_in_range(START_DATE, END_DATE).replace(hour=hour, minute=random.randint(0, 59))
    return [_base_fraud_row(user, receiver, amount, ts, new_device, new_location, "unusual_geo_device")]


def fraud_high_value_anomaly(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    receiver = random.choice(receiver_pool)
    amount = max(user.avg_amount * 6, user.avg_amount + 8 * user.amount_std)
    hour = _sample_hour_from_profile(user.typical_hours)
    ts = _random_timestamp_in_range(START_DATE, END_DATE).replace(hour=hour, minute=random.randint(0, 59))
    return [_base_fraud_row(
        user, receiver, amount, ts, user.home_device, user.home_location,
        "high_value_anomaly", is_new_device=False,
    )]


def fraud_odd_hour(user: UserProfile, receiver_pool: list[str]) -> list[dict]:
    receiver = random.choice(receiver_pool)
    amount = max(500.0, np.random.normal(user.avg_amount * 2, user.amount_std))
    odd_hour = random.choice([0, 1, 2, 3, 4])
    ts = _random_timestamp_in_range(START_DATE, END_DATE).replace(hour=odd_hour, minute=random.randint(0, 59))
    return [_base_fraud_row(
        user, receiver, amount, ts, user.home_device, user.home_location,
        "odd_hour_fraud", is_new_device=False,
    )]


FRAUD_GENERATORS = {
    "account_takeover": fraud_account_takeover,
    "phishing_induced": fraud_phishing_induced,
    "mule_account": fraud_mule_account,
    "velocity_fraud": fraud_velocity,
    "micro_transaction_probing": fraud_micro_probing,
    "unusual_geo_device": fraud_unusual_geo_device,
    "high_value_anomaly": fraud_high_value_anomaly,
    "odd_hour_fraud": fraud_odd_hour,
}


# ---------------------------------------------------------------------------
# Main generation routine
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "transaction_id", "timestamp", "sender_upi_id", "receiver_upi_id",
    "sender_account_id", "receiver_account_id", "amount", "transaction_type",
    "device_id", "ip_address", "location", "sender_bank", "receiver_bank",
    "hour_of_day", "day_of_week", "is_new_device", "is_new_receiver",
    "transaction_status", "label_is_fraud", "fraud_type",
]


def generate_dataset(n_transactions: int, fraud_rate: float, seed: int) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    n_users = max(200, n_transactions // 40)
    n_receivers = max(100, n_transactions // 60)

    users = build_user_pool(n_users)
    receiver_pool = build_receiver_pool(n_receivers)

    target_fraud_count = int(n_transactions * fraud_rate)
    rows: list[dict] = []

    # --- Fraud generation (each call may emit multiple rows, e.g. bursts) ---
    while len([r for r in rows if r["label_is_fraud"]]) < target_fraud_count:
        fraud_type = random.choice(FRAUD_TYPES)
        user = random.choice(users)
        new_rows = FRAUD_GENERATORS[fraud_type](user, receiver_pool)
        rows.extend(new_rows)

    # Trim any overshoot from multi-row fraud bursts
    fraud_rows = [r for r in rows if r["label_is_fraud"]][:target_fraud_count]

    # --- Legitimate transaction generation to fill the remainder ---
    n_legit = n_transactions - len(fraud_rows)
    legit_rows = [make_legit_transaction(random.choice(users), receiver_pool) for _ in range(n_legit)]

    all_rows = fraud_rows + legit_rows
    random.shuffle(all_rows)

    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek  # 0=Monday

    df = df[OUTPUT_COLUMNS]
    return df


def print_summary(df: pd.DataFrame) -> None:
    total = len(df)
    fraud = int(df["label_is_fraud"].sum())
    print(f"Total transactions: {total}")
    print(f"Fraudulent: {fraud} ({fraud / total:.2%})")
    print(f"Legitimate: {total - fraud} ({(total - fraud) / total:.2%})")
    print("\nFraud breakdown by type:")
    print(df.loc[df["label_is_fraud"], "fraud_type"].value_counts().to_string())
    print(f"\nDate range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Unique senders: {df['sender_upi_id'].nunique()}")
    print(f"Unique receivers: {df['receiver_upi_id'].nunique()}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic UPI transaction data.")
    parser.add_argument("--n-transactions", type=int, default=50000)
    parser.add_argument("--fraud-rate", type=float, default=0.04)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="data/raw/synthetic_transactions.csv")
    args = parser.parse_args()

    df = generate_dataset(args.n_transactions, args.fraud_rate, args.seed)
    df.to_csv(args.output, index=False)

    print(f"Wrote {len(df)} transactions to {args.output}\n")
    print_summary(df)


if __name__ == "__main__":
    main()
