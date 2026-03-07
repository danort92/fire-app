"""
Monte Carlo simulation engine: 1000 runs, block bootstrap + parametric hybrid.
"""
import numpy as np
from typing import List, Dict, Any, Optional
from .constants import MSCI_WORLD_RETURNS, MSCI_MEAN_GROSS
from .projections import run_projection


SCENARIO_OPTIONS = ["Normal", "Moderate Stress", "Severe Stress", "Historical Bootstrap", "Hybrid"]


def _generate_block_bootstrap_returns(
    n_years: int,
    expected_gross_return: float,
    ter: float,
    ivafe: float,
    rng: np.random.Generator,
    block_size: int = 3,
) -> List[float]:
    """
    Generate n_years of ETF net returns using block bootstrap from MSCI data.
    Mean-adjusts: adjusted = historical - hist_mean + expected_gross_return.
    Net return = adjusted - TER - IVAFE.
    """
    returns_arr = np.array(MSCI_WORLD_RETURNS)
    n_hist = len(returns_arr)
    net_returns = []

    i = 0
    while i < n_years:
        # Pick random starting index (0-indexed)
        start = rng.integers(0, n_hist)
        for j in range(block_size):
            if i >= n_years:
                break
            idx = (start + j) % n_hist
            gross = returns_arr[idx]
            # Mean-adjust
            adjusted = gross - MSCI_MEAN_GROSS + expected_gross_return
            net = adjusted - ter - ivafe
            net_returns.append(net)
            i += 1

    return net_returns


def _generate_parametric_returns(
    n_years: int,
    expected_net_return: float,
    volatility: float,
    rng: np.random.Generator,
) -> List[float]:
    """Generate parametric normal returns."""
    return rng.normal(expected_net_return, volatility, n_years).tolist()


def _add_stress_events(
    returns: List[float],
    n_crises: int,
    crisis_mean: float,
    crisis_vol: float,
    rng: np.random.Generator,
) -> List[float]:
    """Add random crisis years to returns."""
    n = len(returns)
    result = returns[:]
    crisis_years = rng.choice(n, size=min(n_crises, n), replace=False)
    for yr in crisis_years:
        result[yr] += rng.normal(crisis_mean, crisis_vol)
    return result


def generate_etf_returns(
    n_years: int,
    scenario: str,
    expected_gross_return: float,
    expected_net_return: float,
    volatility: float,
    ter: float,
    ivafe: float,
    rng: np.random.Generator,
) -> List[float]:
    """Generate ETF returns based on scenario."""
    if scenario == "Normal":
        return _generate_parametric_returns(n_years, expected_net_return, volatility, rng)

    elif scenario == "Moderate Stress":
        base = _generate_parametric_returns(n_years, expected_net_return, volatility, rng)
        return _add_stress_events(base, 3, -0.35, volatility * 0.5, rng)

    elif scenario == "Severe Stress":
        base = _generate_parametric_returns(n_years, expected_net_return, volatility, rng)
        return _add_stress_events(base, 3, -0.475, volatility * 0.5, rng)

    elif scenario == "Historical Bootstrap":
        return _generate_block_bootstrap_returns(n_years, expected_gross_return, ter, ivafe, rng)

    elif scenario == "Hybrid":
        # Block bootstrap base + 15% chance of extra shock per year
        base = _generate_block_bootstrap_returns(n_years, expected_gross_return, ter, ivafe, rng)
        result = []
        for r in base:
            if rng.random() < 0.15:
                shock = rng.normal(0, volatility * 0.5)
                result.append(r + shock)
            else:
                result.append(r)
        return result

    return _generate_parametric_returns(n_years, expected_net_return, volatility, rng)


def run_monte_carlo(
    n_simulations: int,
    current_age: int,
    target_age: int,
    net_monthly_salary: float,
    monthly_expenses: float,
    age_started_working: int,
    etf_value: float,
    monthly_pac: float,
    etf_net_return: float,
    expected_gross_return: float,
    etf_volatility: float,
    ter: float,
    ivafe: float,
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
    inflation_std: float,
    state_pension_annual_net: float,
    pension_start_age: int,
    contribution_years: int,
    scenario: str = "Hybrid",
    seed: Optional[int] = 42,
    part_time_monthly_gross: float = 0.0,
    inps_employee_rate: float = 0.0919,
    surcharges_rate: float = 0.02,
    tfr_destination: str = "fund",
    tfr_annual_accrual: float = 0.0,
    tfr_company_value: float = 0.0,
    tfr_revaluation_rate: float = 0.015,
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation.

    Returns percentile bands per age and summary statistics.
    """
    rng = np.random.default_rng(seed)
    n_years = target_age - current_age
    ages = list(range(current_age, target_age + 1))

    # Store liquid assets (bank + etf) in real terms per simulation
    all_liquid_real = np.zeros((n_simulations, n_years + 1))
    all_total_real = np.zeros((n_simulations, n_years + 1))
    solvent_count = 0
    broke_ages = []

    for sim in range(n_simulations):
        # Generate random ETF returns
        etf_returns = generate_etf_returns(
            n_years=n_years,
            scenario=scenario,
            expected_gross_return=expected_gross_return,
            expected_net_return=etf_net_return,
            volatility=etf_volatility,
            ter=ter,
            ivafe=ivafe,
            rng=rng,
        )

        # Generate random inflation path
        raw_inflation = rng.normal(inflation, inflation_std, n_years)
        annual_inflation = np.maximum(0, raw_inflation)
        # Cumulative inflation factors (1-indexed: year 1 = inflation[0])
        cum_inflation = np.cumprod(1 + annual_inflation)

        # Run projection with this simulation's parameters
        rows = run_projection(
            current_age=current_age,
            target_age=target_age,
            net_monthly_salary=net_monthly_salary,
            monthly_expenses=monthly_expenses,
            age_started_working=age_started_working,
            etf_value=etf_value,
            monthly_pac=monthly_pac,
            etf_net_return=etf_net_return,
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
            stop_working_age=stop_working_age,
            part_time=part_time,
            part_time_salary=part_time_salary,
            part_time_until_age=part_time_until_age,
            inflation=inflation,
            state_pension_annual_net=state_pension_annual_net,
            pension_start_age=pension_start_age,
            contribution_years=contribution_years,
            etf_returns=etf_returns,
            inflation_factors=cum_inflation.tolist(),
            part_time_monthly_gross=part_time_monthly_gross,
            inps_employee_rate=inps_employee_rate,
            surcharges_rate=surcharges_rate,
            tfr_destination=tfr_destination,
            tfr_annual_accrual=tfr_annual_accrual,
            tfr_company_value=tfr_company_value,
            tfr_revaluation_rate=tfr_revaluation_rate,
        )

        # Extract liquid real assets per year
        is_solvent = True
        broke_age = None
        for row in rows:
            yr = row["yr"]
            age_val = row["age"]
            liquid = row["bank"] + row["etf"]
            inf_cum = cum_inflation[yr - 1] if yr > 0 else 1.0
            liquid_real = liquid / inf_cum if yr > 0 else liquid
            all_liquid_real[sim, yr] = liquid_real
            all_total_real[sim, yr] = row["total_real"]

            if yr > 0 and is_solvent and not row["working"]:
                if row["etf"] <= 0 and row["bank"] < 100:
                    is_solvent = False
                    broke_age = age_val

        if is_solvent:
            solvent_count += 1
        elif broke_age is not None:
            broke_ages.append(broke_age)

    # Compute percentiles across simulations for each year
    percentiles = [5, 10, 25, 50, 75, 90, 95]
    pct_data = {}
    for p in percentiles:
        pct_data[f"p{p}"] = np.percentile(all_liquid_real, p, axis=0).tolist()

    probability_solvent = solvent_count / n_simulations
    avg_broke_age = float(np.mean(broke_ages)) if broke_ages else target_age
    terminal_wealth = all_liquid_real[:, -1].tolist()

    return {
        "ages": ages,
        "percentiles": pct_data,
        "probability_solvent": probability_solvent,
        "avg_broke_age": avg_broke_age,
        "terminal_wealth": terminal_wealth,
        "n_simulations": n_simulations,
        "scenario": scenario,
    }
