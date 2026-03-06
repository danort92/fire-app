"""
Monthly expense tracker with category breakdown.
"""
from typing import Dict, List


FREQUENCY_MONTHS = {
    "Monthly": 1,
    "Quarterly": 3,
    "Semi-annual": 6,
    "Annual": 12,
}


def to_monthly(amount: float, frequency: str) -> float:
    """Convert amount at given frequency to monthly equivalent."""
    months = FREQUENCY_MONTHS.get(frequency, 1)
    return amount / months


def compute_category_totals(expenses: Dict[str, List[dict]]) -> Dict[str, float]:
    """Return dict of {category: monthly_total}."""
    totals = {}
    for category, items in expenses.items():
        totals[category] = sum(to_monthly(item["amount"], item["frequency"]) for item in items)
    return totals


def compute_total_monthly(expenses: Dict[str, List[dict]]) -> float:
    """Return total monthly expenses across all categories."""
    return sum(compute_category_totals(expenses).values())


def compute_total_annual(expenses: Dict[str, List[dict]]) -> float:
    """Return total annual expenses."""
    return compute_total_monthly(expenses) * 12
