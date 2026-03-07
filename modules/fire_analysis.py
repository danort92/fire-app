"""
FIRE scenario analysis: earliest retirement age and optimal PAC.
"""
from typing import Optional
from .projections import run_projection
from .pension_state import calculate_state_pension


def _is_solvent_to_target(rows: list, target_age: int, emergency_fund: float = 0) -> bool:
    """
    Check solvency: total liquid assets (bank + ETF) must never be exhausted
    UNLESS pension income alone covers all expenses.
    """
    for row in rows:
        if row["age"] <= 0:
            continue
        if row.get("working", True):
            continue  # only check post-retirement
        total_liquid = row["etf"] + row["bank"]
        pension_covers = row.get("pension_income", 0.0) >= row.get("expenses_annual", float("inf"))
        if total_liquid <= 0 and not pension_covers:
            return False
    return True


def _assets_at_age(rows: list, age: int) -> float:
    """Return total real assets at given age."""
    for row in rows:
        if row["age"] == age:
            return row["total_real"]
    return 0.0


def _build_projection_kwargs(
    current_age, target_age, net_monthly_salary, monthly_expenses,
    age_started_working, etf_value, monthly_pac, etf_net_return,
    capital_gains_tax, bank_balance, bank_interest, emergency_fund,
    stamp_duty, pension_fund_value, total_annual_contribution, voluntary_extra,
    pension_fund_return, annuity_rate, age_joined_fund, stop_working_age,
    part_time, part_time_salary, part_time_until_age, inflation,
    state_pension_annual_net, pension_start_age, contribution_years,
    part_time_monthly_gross=0.0, inps_employee_rate=0.0919, surcharges_rate=0.02,
    tfr_destination="fund", tfr_annual_accrual=0.0, tfr_company_value=0.0,
    tfr_revaluation_rate=0.015,
) -> dict:
    return dict(
        current_age=current_age, target_age=target_age,
        net_monthly_salary=net_monthly_salary, monthly_expenses=monthly_expenses,
        age_started_working=age_started_working, etf_value=etf_value,
        monthly_pac=monthly_pac, etf_net_return=etf_net_return,
        capital_gains_tax=capital_gains_tax, bank_balance=bank_balance,
        bank_interest=bank_interest, emergency_fund=emergency_fund,
        stamp_duty=stamp_duty, pension_fund_value=pension_fund_value,
        total_annual_contribution=total_annual_contribution,
        voluntary_extra=voluntary_extra, pension_fund_return=pension_fund_return,
        annuity_rate=annuity_rate, age_joined_fund=age_joined_fund,
        stop_working_age=stop_working_age, part_time=part_time,
        part_time_salary=part_time_salary, part_time_until_age=part_time_until_age,
        inflation=inflation, state_pension_annual_net=state_pension_annual_net,
        pension_start_age=pension_start_age, contribution_years=contribution_years,
        part_time_monthly_gross=part_time_monthly_gross,
        inps_employee_rate=inps_employee_rate, surcharges_rate=surcharges_rate,
        tfr_destination=tfr_destination, tfr_annual_accrual=tfr_annual_accrual,
        tfr_company_value=tfr_company_value, tfr_revaluation_rate=tfr_revaluation_rate,
    )


def run_your_scenario(
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
    part_time_monthly_gross: float = 0.0,
    inps_employee_rate: float = 0.0919,
    surcharges_rate: float = 0.02,
    tfr_destination: str = "fund",
    tfr_annual_accrual: float = 0.0,
    tfr_company_value: float = 0.0,
    tfr_revaluation_rate: float = 0.015,
    **_,
) -> dict:
    """Run the user's chosen scenario and compute summary stats."""
    kwargs = _build_projection_kwargs(
        current_age=current_age, target_age=target_age,
        net_monthly_salary=net_monthly_salary, monthly_expenses=monthly_expenses,
        age_started_working=age_started_working, etf_value=etf_value,
        monthly_pac=monthly_pac, etf_net_return=etf_net_return,
        capital_gains_tax=capital_gains_tax, bank_balance=bank_balance,
        bank_interest=bank_interest, emergency_fund=emergency_fund,
        stamp_duty=stamp_duty, pension_fund_value=pension_fund_value,
        total_annual_contribution=total_annual_contribution,
        voluntary_extra=voluntary_extra, pension_fund_return=pension_fund_return,
        annuity_rate=annuity_rate, age_joined_fund=age_joined_fund,
        stop_working_age=stop_working_age, part_time=part_time,
        part_time_salary=part_time_salary, part_time_until_age=part_time_until_age,
        inflation=inflation, state_pension_annual_net=state_pension_annual_net,
        pension_start_age=pension_start_age, contribution_years=contribution_years,
        part_time_monthly_gross=part_time_monthly_gross,
        inps_employee_rate=inps_employee_rate, surcharges_rate=surcharges_rate,
        tfr_destination=tfr_destination, tfr_annual_accrual=tfr_annual_accrual,
        tfr_company_value=tfr_company_value, tfr_revaluation_rate=tfr_revaluation_rate,
    )
    rows = run_projection(**kwargs)

    solvent = _is_solvent_to_target(rows, target_age)
    assets_at_target_real = _assets_at_age(rows, target_age)

    working_rows = [r for r in rows if r.get("working", False)]
    effective_avg_pac = (
        sum(r["max_pac"] for r in working_rows) / len(working_rows)
        if working_rows else 0.0
    )

    return {
        "rows": rows,
        "solvent_to_target": solvent,
        "assets_at_target_real": assets_at_target_real,
        "effective_avg_monthly_pac": effective_avg_pac,
    }


def _pension_for_stop_age(
    test_stop_age: int,
    current_age: int,
    age_started_working: int,
    ral: float,
    ral_growth: float,
    inps_contribution_rate: float,
    gdp_revaluation_rate: float,
    part_time: bool,
    part_time_salary: float,
    part_time_until_age: int,
    net_monthly_salary: float,
    age_joined_fund: int,
    part_time_monthly_gross: float = 0.0,
    early_pension_years: int = 0,
    defer_to_71: bool = False,
) -> tuple:
    """Helper: compute (contribution_years, pension_net_annual, pension_age)."""
    from .pension_state import calculate_state_pension
    info = calculate_state_pension(
        ral=ral, ral_growth=ral_growth,
        inps_contribution_rate=inps_contribution_rate,
        gdp_revaluation_rate=gdp_revaluation_rate,
        current_age=current_age, age_started_working=age_started_working,
        stop_working_age=test_stop_age, part_time=part_time,
        part_time_salary=part_time_salary, part_time_until_age=part_time_until_age,
        net_monthly_salary=net_monthly_salary, age_joined_fund=age_joined_fund,
        part_time_monthly_gross=part_time_monthly_gross,
        early_pension_years=early_pension_years,
        defer_to_71=defer_to_71,
    )
    pension_net = info["net_annual_nominal"] if info["eligible"] else 0.0
    return info["contribution_years"], pension_net, info["pension_age"]


def find_earliest_retirement(
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
    part_time: bool,
    part_time_salary: float,
    part_time_until_age: int,
    inflation: float,
    pension_start_age: int,
    ral: float,
    ral_growth: float,
    inps_contribution_rate: float,
    gdp_revaluation_rate: float,
    part_time_salary_gross: float = 0.0,
    part_time_monthly_gross: float = 0.0,
    inps_employee_rate: float = 0.0919,
    surcharges_rate: float = 0.02,
    tfr_destination: str = "fund",
    tfr_annual_accrual: float = 0.0,
    tfr_company_value: float = 0.0,
    tfr_revaluation_rate: float = 0.015,
    early_pension_years: int = 0,
    defer_to_71: bool = False,
) -> int:
    """
    Find earliest stop_working_age where portfolio stays solvent to target_age.
    Tests ages from current_age+1 to 65.
    """
    for test_stop_age in range(current_age + 1, 66):
        contrib_years, state_pension_net, p_start_age = _pension_for_stop_age(
            test_stop_age=test_stop_age,
            current_age=current_age, age_started_working=age_started_working,
            ral=ral, ral_growth=ral_growth,
            inps_contribution_rate=inps_contribution_rate,
            gdp_revaluation_rate=gdp_revaluation_rate,
            part_time=part_time, part_time_salary=part_time_salary,
            part_time_until_age=part_time_until_age,
            net_monthly_salary=net_monthly_salary,
            age_joined_fund=age_joined_fund,
            part_time_monthly_gross=part_time_monthly_gross,
            early_pension_years=early_pension_years,
            defer_to_71=defer_to_71,
        )

        kwargs = _build_projection_kwargs(
            current_age=current_age, target_age=target_age,
            net_monthly_salary=net_monthly_salary, monthly_expenses=monthly_expenses,
            age_started_working=age_started_working, etf_value=etf_value,
            monthly_pac=monthly_pac, etf_net_return=etf_net_return,
            capital_gains_tax=capital_gains_tax, bank_balance=bank_balance,
            bank_interest=bank_interest, emergency_fund=emergency_fund,
            stamp_duty=stamp_duty, pension_fund_value=pension_fund_value,
            total_annual_contribution=total_annual_contribution,
            voluntary_extra=voluntary_extra, pension_fund_return=pension_fund_return,
            annuity_rate=annuity_rate, age_joined_fund=age_joined_fund,
            stop_working_age=test_stop_age, part_time=part_time,
            part_time_salary=part_time_salary, part_time_until_age=part_time_until_age,
            inflation=inflation, state_pension_annual_net=state_pension_net,
            pension_start_age=p_start_age, contribution_years=contrib_years,
            part_time_monthly_gross=part_time_monthly_gross,
            inps_employee_rate=inps_employee_rate, surcharges_rate=surcharges_rate,
            tfr_destination=tfr_destination, tfr_annual_accrual=tfr_annual_accrual,
            tfr_company_value=tfr_company_value, tfr_revaluation_rate=tfr_revaluation_rate,
        )
        rows = run_projection(**kwargs)

        target_row = next((r for r in rows if r["age"] == target_age), None)
        if target_row and target_row["total_real"] > 0 and _is_solvent_to_target(rows, target_age):
            return test_stop_age

    return 65  # fallback


def find_optimal_pac(
    current_age: int,
    target_age: int,
    net_monthly_salary: float,
    monthly_expenses: float,
    age_started_working: int,
    etf_value: float,
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
    part_time: bool,
    part_time_salary: float,
    part_time_until_age: int,
    inflation: float,
    pension_start_age: int,
    ral: float,
    ral_growth: float,
    inps_contribution_rate: float,
    gdp_revaluation_rate: float,
    global_earliest_age: int,
    part_time_monthly_gross: float = 0.0,
    inps_employee_rate: float = 0.0919,
    surcharges_rate: float = 0.02,
    tfr_destination: str = "fund",
    tfr_annual_accrual: float = 0.0,
    tfr_company_value: float = 0.0,
    tfr_revaluation_rate: float = 0.015,
    early_pension_years: int = 0,
    defer_to_71: bool = False,
    **_,
) -> int:
    """Find minimum monthly PAC (step 50) that achieves the global earliest retirement age."""
    for pac in range(0, 5001, 50):
        test_earliest = find_earliest_retirement(
            current_age=current_age, target_age=target_age,
            net_monthly_salary=net_monthly_salary, monthly_expenses=monthly_expenses,
            age_started_working=age_started_working, etf_value=etf_value,
            monthly_pac=pac, etf_net_return=etf_net_return,
            capital_gains_tax=capital_gains_tax, bank_balance=bank_balance,
            bank_interest=bank_interest, emergency_fund=emergency_fund,
            stamp_duty=stamp_duty, pension_fund_value=pension_fund_value,
            total_annual_contribution=total_annual_contribution,
            voluntary_extra=voluntary_extra, pension_fund_return=pension_fund_return,
            annuity_rate=annuity_rate, age_joined_fund=age_joined_fund,
            part_time=part_time, part_time_salary=part_time_salary,
            part_time_until_age=part_time_until_age, inflation=inflation,
            pension_start_age=pension_start_age, ral=ral, ral_growth=ral_growth,
            inps_contribution_rate=inps_contribution_rate,
            gdp_revaluation_rate=gdp_revaluation_rate,
            part_time_salary_gross=part_time_salary,
            part_time_monthly_gross=part_time_monthly_gross,
            inps_employee_rate=inps_employee_rate, surcharges_rate=surcharges_rate,
            tfr_destination=tfr_destination, tfr_annual_accrual=tfr_annual_accrual,
            tfr_company_value=tfr_company_value, tfr_revaluation_rate=tfr_revaluation_rate,
            early_pension_years=early_pension_years, defer_to_71=defer_to_71,
        )
        if test_earliest <= global_earliest_age:
            return pac

    return 5000
