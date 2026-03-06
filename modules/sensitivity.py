"""
Sensitivity analysis: how the earliest retirement age changes as a function
of ETF return and monthly expenses.
"""
from typing import Any, Dict, Optional
import pandas as pd

from .fire_analysis import find_earliest_retirement
from .pension_state import calculate_state_pension


RETURN_DELTAS = (-0.02, -0.01, 0.0, 0.01, 0.02)
EXPENSE_DELTAS = (-0.20, -0.10, 0.0, 0.10, 0.20)


def run_sensitivity(
    base_etf_net_return: float,
    base_monthly_expenses: float,
    current_age: int,
    target_age: int,
    net_monthly_salary: float,
    age_started_working: int,
    etf_value: float,
    monthly_pac: float,
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
    part_time: bool,
    part_time_salary: float,
    part_time_until_age: int,
    inflation: float,
    pension_start_age: int,
    ral: float,
    ral_growth: float,
    inps_contribution_rate: float,
    gdp_revaluation_rate: float,
    part_time_monthly_gross: float = 0.0,
    inps_employee_rate: float = 0.0919,
    surcharges_rate: float = 0.02,
    tfr_destination: str = "fund",
    tfr_annual_accrual: float = 0.0,
    tfr_company_value: float = 0.0,
    tfr_revaluation_rate: float = 0.015,
    couple_net_monthly: float = 0.0,
    couple_stop_working_age: int = 0,
    early_pension_years: int = 0,
    defer_to_71: bool = False,
    return_deltas: tuple = RETURN_DELTAS,
    expense_deltas: tuple = EXPENSE_DELTAS,
) -> pd.DataFrame:
    """
    Run a 5×5 sensitivity grid.
    Rows  = expense variation (%) — index
    Cols  = ETF net return variation (pp) — columns
    Values = earliest retirement age
    """
    results = {}

    for exp_delta in expense_deltas:
        exp_label = f"{exp_delta:+.0%}"
        row = {}
        monthly_exp = base_monthly_expenses * (1 + exp_delta)

        for ret_delta in return_deltas:
            ret_label = f"{ret_delta:+.1%}"
            etf_ret = base_etf_net_return + ret_delta

            earliest = find_earliest_retirement(
                current_age=current_age,
                target_age=target_age,
                net_monthly_salary=net_monthly_salary,
                monthly_expenses=monthly_exp,
                age_started_working=age_started_working,
                etf_value=etf_value,
                monthly_pac=monthly_pac,
                etf_net_return=etf_ret,
                capital_gains_tax=capital_gains_tax,
                bank_balance=bank_balance,
                bank_interest=bank_interest,
                emergency_fund=emergency_fund,
                stamp_duty=stamp_duty,
                pension_fund_value=pension_fund_value,
                total_annual_contribution=total_annual_contribution,
                voluntary_extra=voluntary_extra,
                pension_fund_return=pension_fund_return,
                annuity_rate=annuity_rate,
                age_joined_fund=age_joined_fund,
                part_time=part_time,
                part_time_salary=part_time_salary,
                part_time_until_age=part_time_until_age,
                inflation=inflation,
                pension_start_age=pension_start_age,
                ral=ral,
                ral_growth=ral_growth,
                inps_contribution_rate=inps_contribution_rate,
                gdp_revaluation_rate=gdp_revaluation_rate,
                part_time_monthly_gross=part_time_monthly_gross,
                inps_employee_rate=inps_employee_rate,
                surcharges_rate=surcharges_rate,
                tfr_destination=tfr_destination,
                tfr_annual_accrual=tfr_annual_accrual,
                tfr_company_value=tfr_company_value,
                tfr_revaluation_rate=tfr_revaluation_rate,
                couple_net_monthly=couple_net_monthly,
                couple_stop_working_age=couple_stop_working_age,
                early_pension_years=early_pension_years,
                defer_to_71=defer_to_71,
            )
            row[ret_label] = earliest

        results[exp_label] = row

    df = pd.DataFrame(results).T
    df.index.name = "Expenses Δ"
    df.columns.name = "ETF Return Δ"
    return df
