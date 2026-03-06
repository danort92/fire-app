"""
Sensitivity analysis: how the portfolio value at target age changes as a function
of monthly PAC and monthly expenses, given a fixed planned retirement age.
"""
import pandas as pd

from .fire_analysis import run_your_scenario
from .pension_state import calculate_state_pension


PAC_DELTAS     = (-0.20, -0.10, 0.0, 0.10, 0.20)
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
    stop_working_age: int,
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
    pac_deltas: tuple = PAC_DELTAS,
    expense_deltas: tuple = EXPENSE_DELTAS,
) -> pd.DataFrame:
    """
    Run a 5×5 sensitivity grid.
    Rows  = expense variation (%) — index
    Cols  = monthly PAC variation (%) — columns
    Values = portfolio real value at target_age (€k), given fixed stop_working_age
    """
    # Pension info depends only on stop_working_age — compute once
    pension_info = calculate_state_pension(
        ral=ral, ral_growth=ral_growth,
        inps_contribution_rate=inps_contribution_rate,
        gdp_revaluation_rate=gdp_revaluation_rate,
        current_age=current_age, age_started_working=age_started_working,
        stop_working_age=stop_working_age, part_time=part_time,
        part_time_salary=part_time_salary,
        part_time_until_age=part_time_until_age,
        net_monthly_salary=net_monthly_salary,
        age_joined_fund=age_joined_fund,
        part_time_monthly_gross=part_time_monthly_gross,
        early_pension_years=early_pension_years,
        defer_to_71=defer_to_71,
    )
    state_pension_net = pension_info["net_annual_nominal"] if pension_info["eligible"] else 0.0
    p_start_age       = pension_info["pension_age"]
    contrib_years     = pension_info["contribution_years"]

    results = {}

    for exp_delta in expense_deltas:
        exp_label  = f"{exp_delta:+.0%}"
        row        = {}
        monthly_exp = base_monthly_expenses * (1 + exp_delta)

        for pac_delta in pac_deltas:
            pac_label = f"{pac_delta:+.0%}"
            pac       = monthly_pac * (1 + pac_delta)

            result = run_your_scenario(
                current_age=current_age, target_age=target_age,
                net_monthly_salary=net_monthly_salary,
                monthly_expenses=monthly_exp,
                age_started_working=age_started_working,
                etf_value=etf_value, monthly_pac=pac,
                etf_net_return=base_etf_net_return,
                capital_gains_tax=capital_gains_tax,
                bank_balance=bank_balance, bank_interest=bank_interest,
                emergency_fund=emergency_fund, stamp_duty=stamp_duty,
                pension_fund_value=pension_fund_value,
                total_annual_contribution=total_annual_contribution,
                voluntary_extra=voluntary_extra,
                pension_fund_return=pension_fund_return,
                annuity_rate=annuity_rate, age_joined_fund=age_joined_fund,
                stop_working_age=stop_working_age, part_time=part_time,
                part_time_salary=part_time_salary,
                part_time_until_age=part_time_until_age,
                inflation=inflation,
                state_pension_annual_net=state_pension_net,
                pension_start_age=p_start_age,
                contribution_years=contrib_years,
                part_time_monthly_gross=part_time_monthly_gross,
                inps_employee_rate=inps_employee_rate,
                surcharges_rate=surcharges_rate,
                tfr_destination=tfr_destination,
                tfr_annual_accrual=tfr_annual_accrual,
                tfr_company_value=tfr_company_value,
                tfr_revaluation_rate=tfr_revaluation_rate,
                couple_net_monthly=couple_net_monthly,
                couple_stop_working_age=couple_stop_working_age,
            )
            row[pac_label] = round(result["assets_at_target_real"] / 1_000)

        results[exp_label] = row

    df = pd.DataFrame(results).T
    df.index.name   = "Expenses Δ"
    df.columns.name = "PAC Δ"
    return df
