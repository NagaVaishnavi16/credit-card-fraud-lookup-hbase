"""
fraud_rules.py
--------------
Deterministic fraud rule engine.
Each rule takes the card's recent transaction history (list of dicts)
plus the current transaction and returns True/False.

Risk score = weighted sum of triggered rules.
"""

# ---------------------------------------------------------------------------
# Rule weights — must sum to 1.0
# ---------------------------------------------------------------------------
RULE_WEIGHTS = {
    "HighValueTransaction": 0.30,
    "VelocityRule":         0.25,
    "PreviousFraudHistory": 0.30,
    "AmountSpikeRule":      0.15,
}

# ---------------------------------------------------------------------------
# Thresholds (tunable)
# ---------------------------------------------------------------------------
HIGH_VALUE_THRESHOLD     = 1000.0   # absolute $ amount
VELOCITY_WINDOW_SEC      = 60      # time window in seconds
VELOCITY_MAX_COUNT       = 3       # max allowed txns in that window
SPIKE_MULTIPLIER         = 3.0     # current amount vs recent mean


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def rule_high_value(current_txn: dict, _history: list) -> tuple:
    """
    Flags a single large transaction.
    Rationale: Fraudsters often attempt one high-value purchase quickly.
    """
    triggered = current_txn["amount"] > HIGH_VALUE_THRESHOLD
    detail    = f"Amount ${current_txn['amount']:.2f} > threshold ${HIGH_VALUE_THRESHOLD}"
    return triggered, detail


def rule_velocity(current_txn: dict, history: list) -> tuple:
    """
    Flags cards with too many transactions in a short time window.
    Rationale: Card-testing attacks make many small rapid transactions.
    """
    current_time = current_txn["time_offset"]
    window_start = current_time - VELOCITY_WINDOW_SEC
    recent = [t for t in history if t["time_offset"] >= window_start]
    count  = len(recent)
    triggered = count >= VELOCITY_MAX_COUNT
    detail    = f"{count} transactions in last {VELOCITY_WINDOW_SEC}s (max {VELOCITY_MAX_COUNT})"
    return triggered, detail


def rule_previous_fraud(current_txn: dict, history: list) -> tuple:
    """
    Flags cards with a confirmed fraud label in their history.
    Rationale: Once a card is compromised it is frequently re-used.
    """
    prior_frauds = [t for t in history if t.get("label") == 1]
    triggered    = len(prior_frauds) > 0
    detail       = f"{len(prior_frauds)} prior fraud transaction(s) on record"
    return triggered, detail


def rule_amount_spike(current_txn: dict, history: list) -> tuple:
    """
    Flags a sudden jump in transaction amount relative to card's recent average.
    Rationale: Fraudulent charges are often far larger than a card's normal pattern.
    """
    if not history:
        return False, "No history to compare against"

    amounts = [t["amount"] for t in history]
    avg     = sum(amounts) / len(amounts)

    if avg == 0:
        return False, "Recent average is zero — cannot compute spike"

    triggered = current_txn["amount"] > SPIKE_MULTIPLIER * avg
    detail    = (
        f"Amount ${current_txn['amount']:.2f} vs "
        f"recent avg ${avg:.2f} (spike factor "
        f"{current_txn['amount'] / avg:.1f}x, threshold {SPIKE_MULTIPLIER}x)"
    )
    return triggered, detail


# ---------------------------------------------------------------------------
# Composite risk scorer
# ---------------------------------------------------------------------------

RULES = {
    "HighValueTransaction": rule_high_value,
    "VelocityRule":         rule_velocity,
    "PreviousFraudHistory": rule_previous_fraud,
    "AmountSpikeRule":      rule_amount_spike,
}


def evaluate(current_txn: dict, history: list) -> dict:
    """
    Runs all rules and returns a risk assessment dict.

    Args:
        current_txn : dict with keys: amount, time_offset, label
        history     : list of dicts (same schema) — recent card transactions

    Returns:
        {
          "risk_score":   float  (0.0 – 1.0),
          "risk_level":   str    (LOW / MEDIUM / HIGH / CRITICAL),
          "triggered":    list   of rule names that fired,
          "details":      dict   {rule_name: explanation string},
          "recommendation": str
        }
    """
    triggered = []
    details   = {}

    for rule_name, rule_fn in RULES.items():
        fired, detail = rule_fn(current_txn, history)
        details[rule_name] = detail
        if fired:
            triggered.append(rule_name)

    score = sum(RULE_WEIGHTS[r] for r in triggered)

    if score < 0.20:
        level = "LOW"
        recommendation = "APPROVE — transaction appears normal."
    elif score < 0.50:
        level = "MEDIUM"
        recommendation = "REVIEW — flag for manual inspection."
    elif score < 0.75:
        level = "HIGH"
        recommendation = "HOLD — request additional verification."
    else:
        level = "CRITICAL"
        recommendation = "BLOCK — decline and alert cardholder."

    return {
        "risk_score":     round(score, 2),
        "risk_level":     level,
        "triggered":      triggered,
        "details":        details,
        "recommendation": recommendation,
    }
