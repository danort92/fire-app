"""
IRPEF 2025 Italian salary & tax calculation.
Includes Trattamento Integrativo (ex Bonus Renzi).
"""


def marginal_irpef_rate(taxable_income: float) -> float:
    """Return marginal IRPEF rate for given taxable income."""
    if taxable_income > 50000:
        return 0.43
    elif taxable_income > 28000:
        return 0.35
    else:
        return 0.23


def calculate_net_salary(
    ral: float,
    company_benefits: float,
    inps_rate: float,
    surcharges_rate: float,
) -> dict:
    """
    Calculate Italian net salary after IRPEF 2025 taxes.
    Includes Trattamento Integrativo (ex Bonus Renzi).

    Returns dict with all intermediate values and final net salary figures.
    """
    # Step 1: INPS contributions (employee share)
    inps = round(ral * inps_rate, 0)

    # Step 2: Taxable income (reddito complessivo for a single-income employee)
    taxable = ral - inps

    # Step 3: IRPEF 2025 brackets: 23% / 35% / 43%
    irpef = round(
        min(taxable, 28000) * 0.23
        + max(0, min(taxable, 50000) - 28000) * 0.35
        + max(0, taxable - 50000) * 0.43,
        0,
    )

    # Step 4: Tax deductions (detrazioni lavoro dipendente)
    if ral <= 15000:
        deductions = 1955.0
    elif ral <= 28000:
        deductions = 1910 + 1190 * (28000 - ral) / 13000
    elif ral <= 50000:
        deductions = 1910 * (50000 - ral) / 22000
    else:
        deductions = 0.0
    deductions = round(deductions, 0)

    # Step 5: Trattamento Integrativo 2025 (ex Bonus Renzi)
    # Thresholds applied to reddito complessivo (= taxable here)
    if taxable <= 15000:
        # Refundable up to the net IRPEF due after detrazioni
        ti = round(min(1200.0, max(0.0, irpef - deductions)), 0)
    elif taxable <= 28000:
        ti = round(1200.0 * (28000 - taxable) / 13000, 0)
    else:
        ti = 0.0

    # Step 6: Regional/municipal surcharges
    surcharges = round(taxable * surcharges_rate, 0)

    # Step 7: Net IRPEF after deductions, Trattamento Integrativo + surcharges
    net_irpef = max(0, irpef - deductions - ti) + surcharges

    # Step 8: Net annual salary
    net_annual = ral - inps - net_irpef + company_benefits

    # Step 9: Italian 13-month salary system
    net_monthly_13 = round(net_annual / 13, 0)
    net_monthly_12 = round(net_annual / 12, 0)

    return {
        "inps": inps,
        "taxable_income": taxable,
        "irpef": irpef,
        "deductions": deductions,
        "trattamento_integrativo": ti,
        "surcharges": surcharges,
        "net_irpef": net_irpef,
        "net_annual_salary": net_annual,
        "net_monthly_13": net_monthly_13,
        "net_monthly_12": net_monthly_12,
        "marginal_rate": marginal_irpef_rate(taxable),
    }


def gross_to_net_annual(
    ral: float,
    inps_rate: float,
    surcharges_rate: float,
) -> float:
    """Return net annual salary for a given gross RAL (no company benefits)."""
    return calculate_net_salary(ral, 0.0, inps_rate, surcharges_rate)["net_annual_salary"]
