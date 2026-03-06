"""
NPV comparison: Pension Fund voluntary contribution vs ETF investment.
Compares investing 3850 EUR/year in pension fund vs same in ETF.
"""
from functools import reduce


def calculate_npv_comparison(
    voluntary_extra: float,
    tax_savings_annual: float,
    fund_return: float,
    etf_net_return: float,
    annuity_rate: float,
    pension_tax_rate: float,
    discount_rate: float,
    contribution_years: int,   # working years until stop (17 = 50-33)
    dormant_years: int,        # years from stop to pension_age (21 = 71-50)
    payout_years_pf: int,      # pension payout years (19 = 90-71)
    payout_years_etf: int,     # ETF withdrawal years (40 = 90-33-17)
    pension_start_years: int,  # years from now to pension start (38 = 71-33)
    swr: float = 0.035,
    capital_gains_tax: float = 0.26,
    # Legacy alias
    payout_years: int = None,
) -> dict:
    """
    Compare NPV of pension fund vs ETF for voluntary_extra EUR/year.

    A: Pension Fund NPV
      Cost PV = sum((voluntary - tax_savings) / (1+dr)^y for y in 1..contrib_years)
      Montante = accumulate over contrib_years at fund_return
      Dormant growth for dormant_years at fund_return
      Rendita = montante_final × annuity_rate × (1 - pension_tax)
      Payout PV = sum(rendita / (1+dr)^(y+pension_start_years) for y in 1..payout_years_pf)

    B: ETF NPV
      Cost PV = sum(voluntary / (1+dr)^y for y in 1..contrib_years)
      Montante = accumulate at etf_net_return
      Gross withdrawal = montante × swr
      Net withdrawal after CGT on gains
      Withdraw PV = sum(net_withdrawal / (1+dr)^(y+contrib_years) for y in 1..payout_years_etf)
    """
    # Handle legacy single payout_years parameter
    if payout_years is not None and payout_years_pf == 0:
        payout_years_pf = payout_years
    if payout_years is not None and payout_years_etf == 0:
        payout_years_etf = payout_years

    # === A: Pension Fund ===
    net_annual_cost_pf = voluntary_extra - tax_savings_annual

    # Cost PV
    cost_pv_pf = sum(
        net_annual_cost_pf / (1 + discount_rate) ** y
        for y in range(1, contribution_years + 1)
    )

    # Accumulate montante over contribution years
    montante = reduce(
        lambda s, _: s * (1 + fund_return) + voluntary_extra,
        range(contribution_years),
        0.0,
    )

    # Dormant growth (retired but not yet pension age)
    montante_at_pension = montante * (1 + fund_return) ** dormant_years

    # Annual pension payment (net of tax)
    rendita = montante_at_pension * annuity_rate * (1 - pension_tax_rate)

    # Payout PV: discount from pension start
    # Exponent = y + pension_start_years (years from NOW to pension start)
    payout_pv_pf = sum(
        rendita / (1 + discount_rate) ** (y + pension_start_years)
        for y in range(1, payout_years_pf + 1)
    )

    npv_pf = payout_pv_pf - cost_pv_pf

    # === B: ETF ===
    # Cost PV (no tax savings)
    cost_pv_etf = sum(
        voluntary_extra / (1 + discount_rate) ** y
        for y in range(1, contribution_years + 1)
    )

    # Accumulate at ETF net return
    montante_etf = reduce(
        lambda s, _: s * (1 + etf_net_return) + voluntary_extra,
        range(contribution_years),
        0.0,
    )

    # Gross withdrawal at SWR
    gross_withdrawal = montante_etf * swr

    # Net withdrawal after CGT: gain fraction = (montante - cost_basis) / montante
    cost_basis_total = voluntary_extra * contribution_years
    gain_fraction = max(0.0, (montante_etf - cost_basis_total) / max(1.0, montante_etf))
    net_withdrawal = gross_withdrawal * (1 - gain_fraction * capital_gains_tax)

    # Withdrawal PV: exponent = y + contribution_years (years from NOW to withdrawal start)
    withdraw_pv_etf = sum(
        net_withdrawal / (1 + discount_rate) ** (y + contribution_years)
        for y in range(1, payout_years_etf + 1)
    )

    npv_etf = withdraw_pv_etf - cost_pv_etf

    winner = "Pension Fund" if npv_pf >= npv_etf else "ETF"

    return {
        "pension_fund_npv": round(npv_pf, 2),
        "etf_npv": round(npv_etf, 2),
        "npv_difference": round(abs(npv_pf - npv_etf), 2),
        "winner": winner,
        "montante_pf": round(montante_at_pension, 2),
        "montante_etf": round(montante_etf, 2),
        "rendita_annual": round(rendita, 2),
        "net_withdrawal_annual": round(net_withdrawal, 2),
        "cost_pv_pf": round(cost_pv_pf, 2),
        "cost_pv_etf": round(cost_pv_etf, 2),
        "payout_pv_pf": round(payout_pv_pf, 2),
        "withdraw_pv_etf": round(withdraw_pv_etf, 2),
    }
