"""
Flexible sensitivity analysis.
The user selects X-axis variable, Y-axis variable and output metric.
"""
import pandas as pd

from .fire_analysis import find_earliest_retirement, run_your_scenario
from .pension_state import calculate_state_pension


# ── Available axis variables ────────────────────────────────────────────────
AXIS_VARIABLES = {
    "Spese mensili":        {"deltas": (-0.20, -0.10, 0.0, 0.10, 0.20),  "label_fmt": "{:+.0%}"},
    "Rendimento ETF netto": {"deltas": (-0.02, -0.01, 0.0, 0.01, 0.02),  "label_fmt": "{:+.1%}"},
    "PAC mensile":          {"deltas": (-0.20, -0.10, 0.0, 0.10, 0.20),  "label_fmt": "{:+.0%}"},
    "Inflazione":           {"deltas": (-0.01, -0.005, 0.0, 0.005, 0.01), "label_fmt": "{:+.1%}"},
    "Crescita RAL":         {"deltas": (-0.01, -0.005, 0.0, 0.005, 0.01), "label_fmt": "{:+.1%}"},
}

# ── Available output metrics ────────────────────────────────────────────────
OUTPUT_METRICS = [
    "Età minima di pensionamento",
    "Portafoglio reale (€k) all'età target",
]


def _apply_delta(params: dict, var_name: str, delta: float) -> dict:
    """Return a copy of params with the given variable shifted by delta."""
    p = dict(params)
    if var_name == "Spese mensili":
        p["monthly_expenses"] = p["monthly_expenses"] * (1 + delta)
    elif var_name == "Rendimento ETF netto":
        p["etf_net_return"] = p["etf_net_return"] + delta
    elif var_name == "PAC mensile":
        p["monthly_pac"] = p["monthly_pac"] * (1 + delta)
    elif var_name == "Inflazione":
        p["inflation"] = p["inflation"] + delta
    elif var_name == "Crescita RAL":
        p["ral_growth"] = p["ral_growth"] + delta
    return p


def _compute_cell(
    params: dict,
    output_metric: str,
    stop_working_age: int,
    _pension_cache: dict,
) -> float:
    """Compute the output metric for a single (x_delta, y_delta) cell."""
    if output_metric == "Età minima di pensionamento":
        return find_earliest_retirement(**params)

    # "Portafoglio reale (€k) all'età target"
    result = run_your_scenario(
        **params,
        stop_working_age=stop_working_age,
        state_pension_annual_net=_pension_cache["state_pension_net"],
        pension_start_age=_pension_cache["pension_start_age"],
        contribution_years=_pension_cache["contribution_years"],
    )
    return round(result["assets_at_target_real"] / 1_000)


def run_sensitivity(
    # ── Base scenario params ──────────────────────────────────────────────
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
    # ── Sensitivity config ────────────────────────────────────────────────
    x_var: str = "Rendimento ETF netto",
    y_var: str = "Spese mensili",
    output_metric: str = "Età minima di pensionamento",
) -> pd.DataFrame:
    """
    Run a 5×5 sensitivity grid.
    Rows  = y_var deltas  (index)
    Cols  = x_var deltas  (columns)
    Values = output_metric
    """
    x_cfg = AXIS_VARIABLES[x_var]
    y_cfg = AXIS_VARIABLES[y_var]

    # Base params dict passed to the compute functions
    base = dict(
        current_age=current_age, target_age=target_age,
        net_monthly_salary=net_monthly_salary,
        monthly_expenses=base_monthly_expenses,
        age_started_working=age_started_working,
        etf_value=etf_value, monthly_pac=monthly_pac,
        etf_net_return=base_etf_net_return,
        capital_gains_tax=capital_gains_tax,
        bank_balance=bank_balance, bank_interest=bank_interest,
        emergency_fund=emergency_fund, stamp_duty=stamp_duty,
        pension_fund_value=pension_fund_value,
        total_annual_contribution=total_annual_contribution,
        voluntary_extra=voluntary_extra,
        pension_fund_return=pension_fund_return,
        annuity_rate=annuity_rate, age_joined_fund=age_joined_fund,
        part_time=part_time, part_time_salary=part_time_salary,
        part_time_until_age=part_time_until_age,
        inflation=inflation,
        pension_start_age=pension_start_age,
        ral=ral, ral_growth=ral_growth,
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

    # Pre-compute pension info once (needed for portfolio metric; fixed stop_working_age)
    pension_info_raw = calculate_state_pension(
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
    pension_cache = {
        "state_pension_net":  pension_info_raw["net_annual_nominal"] if pension_info_raw["eligible"] else 0.0,
        "pension_start_age":  pension_info_raw["pension_age"],
        "contribution_years": pension_info_raw["contribution_years"],
    }

    results = {}
    for y_delta in y_cfg["deltas"]:
        y_label = y_cfg["label_fmt"].format(y_delta)
        row = {}
        params_y = _apply_delta(base, y_var, y_delta)

        for x_delta in x_cfg["deltas"]:
            x_label = x_cfg["label_fmt"].format(x_delta)
            params_xy = _apply_delta(params_y, x_var, x_delta)
            row[x_label] = _compute_cell(params_xy, output_metric, stop_working_age, pension_cache)

        results[y_label] = row

    df = pd.DataFrame(results).T
    df.index.name   = y_var
    df.columns.name = x_var
    return df
