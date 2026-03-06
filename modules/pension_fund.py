"""
Italian private pension fund (fondo pensione complementare) analysis.
"""
from .tax import marginal_irpef_rate


def pension_fund_tax_rate(age_at_payout: int, age_joined: int) -> float:
    """
    Calculate pension fund payout tax rate.
    Reduces from 15% by 0.3% per year after 15 years in fund, floor at 9%.
    """
    years_in_fund = age_at_payout - age_joined
    reduction = min(0.06, max(0, (years_in_fund - 15) * 0.003))
    return max(0.09, 0.15 - reduction)


def calculate_pension_fund_info(
    current_value: float,
    tfr_contribution: float,
    employer_contribution: float,
    personal_contribution: float,
    voluntary_extra: float,
    max_deductible: float,
    fund_return: float,
    annuity_rate: float,
    age_joined: int,
    taxable_income: float,
) -> dict:
    """
    Compute pension fund tax savings and payout details.
    """
    # Total annual contributions
    total_base = tfr_contribution + employer_contribution + personal_contribution
    total_with_vol = employer_contribution + personal_contribution + voluntary_extra

    # Tax-deductible amount (excludes TFR from deductibility)
    actual_deductible = min(total_with_vol, max_deductible)
    # Tax savings at marginal rate on deductible portion
    marginal_rate = marginal_irpef_rate(taxable_income)
    tax_savings = round(actual_deductible * marginal_rate, 0)

    return {
        "total_base_contribution": total_base,
        "total_with_voluntary": total_with_vol,
        "actual_deductible": actual_deductible,
        "tax_savings": tax_savings,
        "marginal_rate": marginal_rate,
        "fund_return": fund_return,
        "annuity_rate": annuity_rate,
        "age_joined": age_joined,
    }
