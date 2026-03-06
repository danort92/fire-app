"""
INPS contributive pension calculation (metodo contributivo).
Supports pensione di vecchiaia (67) and pensione anticipata (41+ anni contributi).
"""
from .constants import INPS_COEFFICIENTS


def _pension_tax_rate(pension_age: int, age_joined_fund: int) -> float:
    """Pension fund tax rate at payout."""
    years_in_fund = pension_age - age_joined_fund
    reduction = min(0.06, max(0, (years_in_fund - 15) * 0.003))
    return max(0.09, 0.15 - reduction)


def calculate_state_pension(
    ral: float,
    ral_growth: float,
    inps_contribution_rate: float,
    gdp_revaluation_rate: float,
    current_age: int,
    age_started_working: int,
    stop_working_age: int,
    part_time: bool,
    part_time_salary: float,            # net monthly part-time income
    part_time_until_age: int,
    net_monthly_salary: float,          # used for backward-compat fraction fallback
    age_joined_fund: int = 30,
    min_contribution_years: int = 20,
    early_pension_years: int = 0,       # if > 0, trigger early pension at this contribution threshold
    part_time_monthly_gross: float = 0.0,  # gross monthly part-time RAL (preferred over net for INPS)
    defer_to_71: bool = False,          # if True, defer pension to 71 for max INPS coefficient
) -> dict:
    """
    Calculate INPS state pension using contributive method.

    Pension age logic:
    - defer_to_71=True  → age 71 (maximum coefficient)
    - early_pension_years > 0 and sufficient contributions → pensione anticipata
    - default → pensione di vecchiaia at age 67 (contributivo, min 20 years)

    Returns dict with pension_age, contribution_years, montante,
    gross_annual, net_annual_nominal, net_monthly_nominal.
    """
    # Contribution years
    full_time_years = max(0, stop_working_age - age_started_working)
    pt_years = max(0, part_time_until_age - stop_working_age) if part_time else 0
    contribution_years = full_time_years + pt_years

    # Part-time RAL fraction for INPS accrual
    # Prefer gross-based ratio (more accurate); fallback to net-based ratio
    if part_time and part_time_monthly_gross > 0 and ral > 0:
        pt_ral_fraction = (part_time_monthly_gross * 12) / ral
    elif net_monthly_salary > 0 and part_time:
        pt_ral_fraction = part_time_salary / net_monthly_salary
    else:
        pt_ral_fraction = 0.0
    # Clamp to [0, 1] — part-time can't exceed full-time
    pt_ral_fraction = max(0.0, min(1.0, pt_ral_fraction))

    # ── Determine pension_age ──────────────────────────────────────────────
    years_already_contributed = current_age - age_started_working
    years_needed = max(0, min_contribution_years - years_already_contributed)
    pension_age_min = current_age + years_needed

    if defer_to_71:
        # User explicitly wants max coefficient deferral
        pension_age = max(pension_age_min, 71)

    elif early_pension_years > 0 and contribution_years >= early_pension_years:
        # Pensione anticipata: available when total contributions hit threshold
        # Age when threshold is reached
        if full_time_years >= early_pension_years:
            # Reached threshold during full-time
            early_age = age_started_working + early_pension_years
        else:
            # Reached during part-time
            years_pt_needed = early_pension_years - full_time_years
            early_age = stop_working_age + years_pt_needed

        pension_age = max(57, early_age)  # INPS coefficient table starts at 57
        pension_age = min(pension_age, 71)  # coefficient table ends at 71

    else:
        # Standard pensione di vecchiaia contributiva: age 67
        pension_age = max(pension_age_min, 67)
        pension_age = min(pension_age, 71)  # never force beyond 71

    # Eligibility check
    eligible = contribution_years >= min_contribution_years

    if not eligible:
        return {
            "pension_age": pension_age,
            "contribution_years": contribution_years,
            "eligible": False,
            "montante": 0,
            "gross_annual": 0,
            "net_annual_nominal": 0,
            "net_monthly_nominal": 0,
        }

    # ── Build montante year by year from career start to pension_age ───────
    montante = 0.0
    for yr_idx in range(pension_age - age_started_working):
        year_age = age_started_working + yr_idx
        remaining_years = pension_age - year_age - 1

        ral_yr = ral * (1 + ral_growth) ** (year_age - age_started_working)

        if year_age < stop_working_age:
            contribution = ral_yr * inps_contribution_rate
        elif part_time and stop_working_age <= year_age < part_time_until_age:
            contribution = ral_yr * pt_ral_fraction * inps_contribution_rate
        else:
            contribution = 0.0

        montante += contribution * (1 + gdp_revaluation_rate) ** remaining_years

    # Gross pension = montante × INPS transformation coefficient
    coeff = INPS_COEFFICIENTS.get(pension_age, INPS_COEFFICIENTS[71])
    gross_annual = montante * coeff

    # Pension tax (uses same schedule as pension fund)
    tax_rate = _pension_tax_rate(pension_age, age_joined_fund)
    net_annual_nominal = gross_annual * (1 - tax_rate)
    net_monthly_nominal = round(net_annual_nominal / 13, 0)

    return {
        "pension_age": pension_age,
        "contribution_years": contribution_years,
        "eligible": eligible,
        "montante": montante,
        "gross_annual": gross_annual,
        "net_annual_nominal": net_annual_nominal,
        "net_monthly_nominal": net_monthly_nominal,
    }
