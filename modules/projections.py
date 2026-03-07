"""
Year-by-year asset projection engine (Bank + ETF + Pension Fund + TFR).
Ages current_age → target_age.

New in v2:
- Part-time income taxed via IRPEF (if part_time_monthly_gross provided)
- TFR in azienda option: accumulates separately, paid out at stop_working_age
"""
from typing import List, Dict, Any, Optional

from .pension_fund import pension_fund_tax_rate
from .tax import gross_to_net_annual


def _compute_pension_income(
    age: int,
    pension_fund_value: float,
    annuity_rate: float,
    pension_start_age: int,
    state_pension_annual_net: float,
    inflation: float,
    contribution_years: int,
    age_joined_fund: int,
    stop_working_age: int,
    current_age: int,
) -> tuple:
    """Return (state_pension_inc, pvt_pension_inc, has_state, has_pvt)."""
    has_state = contribution_years >= 20
    has_pvt = (stop_working_age - age_joined_fund) >= 5

    if age < pension_start_age:
        return 0.0, 0.0, has_state, has_pvt

    state_inc = 0.0
    if has_state:
        state_inc = state_pension_annual_net * (1 + inflation) ** (age - pension_start_age)

    pvt_inc = 0.0
    if has_pvt:
        # Tax rate fixed at pension_start_age (annuity rate is set at purchase)
        pvt_tax = pension_fund_tax_rate(pension_start_age, age_joined_fund)
        pvt_inc = pension_fund_value * annuity_rate * (1 - pvt_tax)

    return state_inc, pvt_inc, has_state, has_pvt


def run_projection(
    current_age: int,
    target_age: int,
    net_monthly_salary: float,
    monthly_expenses: float,
    age_started_working: int,
    etf_value: float,
    monthly_pac: float,
    etf_net_return: float,
    capital_gains_tax: float,
    bank_balance: float,
    bank_interest: float,
    emergency_fund: float,
    stamp_duty: float,
    pension_fund_value: float,
    total_annual_contribution: float,
    voluntary_extra: float,
    pension_fund_return: float,
    annuity_rate: float,
    age_joined_fund: int,
    stop_working_age: int,
    part_time: bool,
    part_time_salary: float,
    part_time_until_age: int,
    inflation: float,
    state_pension_annual_net: float,
    pension_start_age: int,
    contribution_years: int,
    # ── New parameters (all optional with defaults for backward compat) ──
    part_time_monthly_gross: float = 0.0,   # gross monthly; if >0 IRPEF is applied
    inps_employee_rate: float = 0.0919,
    surcharges_rate: float = 0.02,
    tfr_destination: str = "fund",           # "fund" or "company"
    tfr_annual_accrual: float = 0.0,         # annual TFR accrual (RAL/13.5) if company
    tfr_company_value: float = 0.0,          # existing TFR in company at current_age
    tfr_revaluation_rate: float = 0.015,     # base TFR revaluation (1.5% + 75%*infl)
    etf_returns: Optional[List[float]] = None,
    inflation_factors: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Run year-by-year projection from current_age to target_age.
    Returns list of dicts with state per age.
    """
    rows = []

    # Resolve part-time net: if gross is given, compute via IRPEF; else use net directly
    if part_time_monthly_gross > 0:
        pt_net_annual = gross_to_net_annual(
            part_time_monthly_gross * 12, inps_employee_rate, surcharges_rate
        )
    else:
        pt_net_annual = part_time_salary * 12  # treat entered value as net

    # TFR revaluation including inflation component: 1.5% + 75% * inflation
    _tfr_rev = tfr_revaluation_rate + 0.75 * inflation

    # Initial state
    bank = bank_balance
    etf = etf_value
    pf = pension_fund_value
    cost_basis = etf_value
    tfr_co = tfr_company_value  # TFR in azienda balance

    rows.append({
        "age": current_age,
        "yr": 0,
        "bank": bank, "bank_real": bank,
        "etf": etf,   "etf_real": etf,
        "pf": pf,     "pf_real": pf,
        "tfr_company": tfr_co, "tfr_real": tfr_co,
        "cost_basis": cost_basis,
        "total_nominal": bank + etf + pf + tfr_co,
        "total_real": bank + etf + pf + tfr_co,
        "max_pac": 0.0,
        "vol_pen": 0.0,
        "working": True,
        "part_time": False,
    })

    n_years = target_age - current_age

    for yr in range(1, n_years + 1):
        age = current_age + yr
        prev = rows[-1]
        bank = prev["bank"]
        etf = prev["etf"]
        pf = prev["pf"]
        cost_basis = prev["cost_basis"]
        tfr_co = prev["tfr_company"]

        is_working = age < stop_working_age
        is_pt = part_time and (stop_working_age <= age < part_time_until_age)

        # ── Inflation / ETF return ─────────────────────────────────────────
        if inflation_factors is not None:
            inf_factor = inflation_factors[yr - 1] if yr - 1 < len(inflation_factors) else inflation_factors[-1]
            expenses_annual = monthly_expenses * 12 * inf_factor
        else:
            expenses_annual = monthly_expenses * 12 * (1 + inflation) ** yr

        if etf_returns is not None:
            etf_r = etf_returns[yr - 1] if yr - 1 < len(etf_returns) else etf_net_return
        else:
            etf_r = etf_net_return

        # ── Pension income ─────────────────────────────────────────────────
        state_inc, pvt_inc, has_state, has_pvt = _compute_pension_income(
            age=age,
            pension_fund_value=pf,
            annuity_rate=annuity_rate,
            pension_start_age=pension_start_age,
            state_pension_annual_net=state_pension_annual_net,
            inflation=inflation,
            contribution_years=contribution_years,
            age_joined_fund=age_joined_fund,
            stop_working_age=stop_working_age,
            current_age=current_age,
        )
        pension_income = state_inc + pvt_inc

        # ── TFR in azienda accumulation/payout ────────────────────────────
        if tfr_destination == "company":
            if is_working:
                # Accrue + revalue existing balance
                tfr_co = tfr_co * (1 + _tfr_rev) + tfr_annual_accrual
            elif age == stop_working_age:
                # Payout at termination: net of 17% substitute tax on gains
                # Simplified: apply flat 17% to the entire balance
                bank += tfr_co * (1 - 0.17)
                tfr_co = 0.0
        else:
            tfr_co = 0.0  # TFR is in the fund, not tracked separately

        # ── Bank account ──────────────────────────────────────────────────
        bank_grow = bank * (1 + bank_interest) - stamp_duty

        if is_working:
            salary = net_monthly_salary * 12
            cash_avail = salary - expenses_annual

            bank_before_pac = bank_grow + cash_avail

            # Voluntary pension first-pass (how much affordable)
            vol_pen = min(voluntary_extra, max(0.0, bank_before_pac - emergency_fund))

            # PAC after voluntary pension
            max_pac = min(monthly_pac * 12, max(0.0, bank_before_pac - vol_pen - emergency_fund))

            new_bank = bank_grow + cash_avail - vol_pen - max_pac

        else:
            # Not working: income from part-time + pension
            pt_income = pt_net_annual if is_pt else 0.0
            ncf = pension_income + pt_income - expenses_annual

            eff_ef = emergency_fund if (is_working or etf > 1) else 0.0
            bank_deficit = min(0.0, max(-(bank_grow - eff_ef), ncf))
            new_bank = max(eff_ef, bank_grow + bank_deficit)

            max_pac = 0.0
            vol_pen = 0.0

        # ── ETF portfolio ─────────────────────────────────────────────────
        etf_before = etf * (1 + etf_r) + max_pac

        if is_working:
            new_etf = etf_before
            disinvest = 0.0
        else:
            pt_income = pt_net_annual if is_pt else 0.0
            ncf_non_working = pension_income + pt_income - expenses_annual
            shortfall = min(0.0, ncf_non_working + (bank_grow - new_bank))

            if shortfall < 0:
                gain_ratio = max(0.0, 1 - cost_basis / max(etf, 1.0))
                tax_drag = max(1 - gain_ratio * capital_gains_tax, 0.01)
                disinvest = min(-shortfall / tax_drag, etf_before)
            else:
                disinvest = 0.0

            new_etf = max(0.0, etf_before - disinvest)

        # ── Cost basis ────────────────────────────────────────────────────
        if new_etf <= 0:
            new_cost_basis = 0.0
        else:
            new_cb = cost_basis + max_pac
            denom = max(1.0, etf * (1 + etf_r) + max_pac)
            new_cost_basis = new_cb * min(1.0, new_etf / denom)

        # ── Pension fund ──────────────────────────────────────────────────
        if age >= pension_start_age and has_pvt:
            new_pf = max(0.0, pf * (1 + pension_fund_return) - pf * annuity_rate)
        elif is_working:
            new_pf = pf * (1 + pension_fund_return) + total_annual_contribution + vol_pen
        else:
            new_pf = pf * (1 + pension_fund_return)

        # ── Totals ────────────────────────────────────────────────────────
        total_nominal = new_bank + new_etf + new_pf + (tfr_co if tfr_destination == "company" else 0.0)
        if inflation_factors is not None:
            inf_cum = inflation_factors[yr - 1] if yr - 1 < len(inflation_factors) else inflation_factors[-1]
        else:
            inf_cum = (1 + inflation) ** yr
        total_real = total_nominal / inf_cum

        rows.append({
            "age": age,
            "yr": yr,
            # Nominal values (year-of-payment money)
            "bank": round(new_bank, 2),
            "etf": round(new_etf, 2),
            "pf": round(new_pf, 2),
            "tfr_company": round(tfr_co, 2),
            # Real values (deflated to current_age purchasing power)
            "bank_real": round(new_bank / inf_cum, 2),
            "etf_real": round(new_etf / inf_cum, 2),
            "pf_real": round(new_pf / inf_cum, 2),
            "tfr_real": round((tfr_co if tfr_destination == "company" else 0.0) / inf_cum, 2),
            "cost_basis": round(new_cost_basis, 2),
            "total_nominal": round(total_nominal, 2),
            "total_real": round(total_real, 2),
            "max_pac": round(max_pac / 12, 2),
            "vol_pen": round(vol_pen, 2),
            "working": is_working,
            "part_time": is_pt,
            "expenses_annual": round(expenses_annual, 2),
            "pension_income": round(pension_income, 2),
        })

        bank = new_bank
        etf = new_etf
        pf = new_pf
        cost_basis = new_cost_basis

    return rows
