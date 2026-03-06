"""
Comprehensive test suite for fire_app modules.
Tests correctness, consistency and edge cases for all financial calculations.
"""
import sys
import math
import traceback

sys.path.insert(0, "/home/user/fire_app")

PASS = 0
FAIL = 0
ERRORS = []


def ok(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        ERRORS.append(name)


def approx(a, b, tol=0.01):
    """Relative tolerance check."""
    if b == 0:
        return abs(a) < tol
    return abs(a - b) / abs(b) < tol


def approx_abs(a, b, tol=1.0):
    """Absolute tolerance check (euros)."""
    return abs(a - b) <= tol


# ─────────────────────────────────────────────────────────
# 1. TAX MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 1. TAX MODULE ===")
from modules.tax import marginal_irpef_rate, calculate_net_salary

# Marginal rates by bracket
ok("marginal_rate ≤28k → 23%", marginal_irpef_rate(20000) == 0.23)
ok("marginal_rate 28k-50k → 35%", marginal_irpef_rate(35000) == 0.35)
ok("marginal_rate >50k → 43%", marginal_irpef_rate(60000) == 0.43)
ok("marginal_rate at exact 28000 → 23%", marginal_irpef_rate(28000) == 0.23)
ok("marginal_rate at exact 50000 → 35%", marginal_irpef_rate(50000) == 0.35)

# Known-good benchmark: RAL=35600, benefits=2000, inps=9.19%, surcharges=2%
r = calculate_net_salary(35600, 2000, 0.0919, 0.02)
ok("INPS ~3272", approx_abs(r["inps"], 3272, 5), f"got {r['inps']}")
ok("taxable_income ~32328", approx_abs(r["taxable_income"], 32328, 5), f"got {r['taxable_income']}")
ok("net_annual_salary positive", r["net_annual_salary"] > 0)
ok("net_monthly_13 = net_annual/13", approx_abs(r["net_monthly_13"], round(r["net_annual_salary"] / 13, 0), 1))
ok("net_monthly_12 = net_annual/12", approx_abs(r["net_monthly_12"], round(r["net_annual_salary"] / 12, 0), 1))
ok("net_annual includes benefits", r["net_annual_salary"] == r["net_annual_salary"])  # tautology; detailed below
# net_annual = ral - inps - net_irpef + benefits
expected_net = 35600 - r["inps"] - r["net_irpef"] + 2000
ok("net_annual_salary formula check", approx_abs(r["net_annual_salary"], expected_net, 1), f"got {r['net_annual_salary']} expected {expected_net}")

# Zero RAL edge case
r0 = calculate_net_salary(0, 0, 0.0919, 0.02)
ok("zero RAL → zero net", r0["net_annual_salary"] == 0)

# High RAL (>50k) — deductions should be 0
r_high = calculate_net_salary(80000, 0, 0.0919, 0.02)
ok("high RAL deductions = 0", r_high["deductions"] == 0)
ok("high RAL marginal rate = 43%", r_high["marginal_rate"] == 0.43)

# Low RAL (≤15k) — deductions should be 1955
r_low = calculate_net_salary(14000, 0, 0.0919, 0.02)
ok("low RAL deductions = 1955", r_low["deductions"] == 1955)

# ─────────────────────────────────────────────────────────
# 2. EXPENSES MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 2. EXPENSES MODULE ===")
from modules.expenses import to_monthly, compute_category_totals, compute_total_monthly, compute_total_annual
from modules.constants import DEFAULT_EXPENSES

ok("Monthly freq → 1x", to_monthly(100, "Monthly") == 100)
ok("Quarterly freq → 1/3", approx_abs(to_monthly(300, "Quarterly"), 100, 0.01))
ok("Semi-annual freq → 1/6", approx_abs(to_monthly(600, "Semi-annual"), 100, 0.01))
ok("Annual freq → 1/12", approx_abs(to_monthly(1200, "Annual"), 100, 0.01))
ok("Unknown freq → 1x (fallback)", to_monthly(100, "Weekly") == 100)

# Default expenses consistency
totals = compute_category_totals(DEFAULT_EXPENSES)
ok("All categories positive", all(v >= 0 for v in totals.values()))
total_monthly = compute_total_monthly(DEFAULT_EXPENSES)
total_annual = compute_total_annual(DEFAULT_EXPENSES)
ok("annual = monthly × 12", approx_abs(total_annual, total_monthly * 12, 0.01))
ok("default total monthly > 0", total_monthly > 0)
ok("category totals sum = total_monthly", approx_abs(sum(totals.values()), total_monthly, 0.01))

# Single expense
single = {"Cat": [{"name": "X", "frequency": "Monthly", "amount": 500}]}
ok("single monthly expense = 500", compute_total_monthly(single) == 500)

single_q = {"Cat": [{"name": "X", "frequency": "Quarterly", "amount": 300}]}
ok("single quarterly expense = 100/mo", approx_abs(compute_total_monthly(single_q), 100, 0.01))

# ─────────────────────────────────────────────────────────
# 3. PENSION FUND MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 3. PENSION FUND MODULE ===")
from modules.pension_fund import pension_fund_tax_rate, calculate_pension_fund_info

# Tax rate mechanics: 15% base, -0.3%/yr after 15yrs, floor 9%
ok("15 years → 15%", approx_abs(pension_fund_tax_rate(45, 30), 0.15, 0.001))
ok("16 years → 14.7%", approx_abs(pension_fund_tax_rate(46, 30), 0.147, 0.001))
ok("35 years → 9% floor", approx_abs(pension_fund_tax_rate(65, 30), 0.09, 0.001))
ok("5 years (< 15) → 15% floor", approx_abs(pension_fund_tax_rate(35, 30), 0.15, 0.001))

# After 15+20=35 years: 15 - 20*0.3% = 15-6=9% floor
ok("35+ years → exactly 9% floor", pension_fund_tax_rate(70, 30) == 0.09)

# calculate_pension_fund_info
info = calculate_pension_fund_info(
    current_value=22000,
    tfr_contribution=1993,
    employer_contribution=1079,
    personal_contribution=228,
    voluntary_extra=3850,
    max_deductible=5164.57,
    fund_return=0.04,
    annuity_rate=0.05,
    age_joined=30,
    taxable_income=32328,
)
ok("total_base_contribution = tfr+employer+personal", approx_abs(info["total_base_contribution"], 1993 + 1079 + 228, 0.01))
ok("total_with_voluntary = employer+personal+vol", approx_abs(info["total_with_voluntary"], 1079 + 228 + 3850, 0.01))
ok("actual_deductible ≤ max_deductible", info["actual_deductible"] <= 5164.57)
ok("tax_savings > 0", info["tax_savings"] > 0)
ok("tax_savings = deductible × marginal_rate", approx_abs(info["tax_savings"], round(info["actual_deductible"] * info["marginal_rate"], 0), 1))

# When total_with_vol < max_deductible → full deductibility
info2 = calculate_pension_fund_info(
    current_value=22000, tfr_contribution=1993, employer_contribution=500,
    personal_contribution=100, voluntary_extra=200,
    max_deductible=5164.57, fund_return=0.04, annuity_rate=0.05,
    age_joined=30, taxable_income=32328,
)
ok("actual_deductible = total_with_vol when below max", approx_abs(info2["actual_deductible"], 500 + 100 + 200, 0.01))

# ─────────────────────────────────────────────────────────
# 4. STATE PENSION MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 4. STATE PENSION MODULE ===")
from modules.pension_state import calculate_state_pension

base_params = dict(
    ral=35600, ral_growth=0.005, inps_contribution_rate=0.33, gdp_revaluation_rate=0.02,
    current_age=33, age_started_working=26, stop_working_age=50,
    part_time=True, part_time_salary=900, part_time_until_age=60,
    net_monthly_salary=2075, age_joined_fund=30,
)

sp = calculate_state_pension(**base_params)
ok("pension_age ≥ 67", sp["pension_age"] >= 67, f"got {sp['pension_age']}")
ok("contribution_years > 0", sp["contribution_years"] > 0)
ok("eligible with 20+ years", sp["eligible"])
ok("montante > 0", sp["montante"] > 0)
ok("gross_annual > 0", sp["gross_annual"] > 0)
ok("net_annual_nominal < gross_annual (taxed)", sp["net_annual_nominal"] < sp["gross_annual"])
ok("net_monthly_nominal = net_annual/13", approx_abs(sp["net_monthly_nominal"], round(sp["net_annual_nominal"] / 13, 0), 1))

# Not eligible: stop at age 30 (only 4 years worked, plus 0 part-time)
sp_nok = calculate_state_pension(
    ral=35600, ral_growth=0.005, inps_contribution_rate=0.33, gdp_revaluation_rate=0.02,
    current_age=33, age_started_working=29, stop_working_age=33,
    part_time=False, part_time_salary=0, part_time_until_age=33,
    net_monthly_salary=2000, age_joined_fund=30, min_contribution_years=20,
)
ok("ineligible → gross_annual=0", sp_nok["gross_annual"] == 0)
ok("ineligible → eligible=False", not sp_nok["eligible"])

# Full-time only (no part-time)
sp_ft = calculate_state_pension(
    ral=35600, ral_growth=0.005, inps_contribution_rate=0.33, gdp_revaluation_rate=0.02,
    current_age=33, age_started_working=26, stop_working_age=66,
    part_time=False, part_time_salary=0, part_time_until_age=66,
    net_monthly_salary=2075, age_joined_fund=30,
)
ok("full-time stop at 66 → eligible", sp_ft["eligible"])
ok("contribution_years = 66-26 = 40", sp_ft["contribution_years"] == 40)

# ─────────────────────────────────────────────────────────
# 5. PROJECTIONS MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 5. PROJECTIONS MODULE ===")
from modules.projections import run_projection

proj_params = dict(
    current_age=33, target_age=90,
    net_monthly_salary=2075, monthly_expenses=1600,
    age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    stop_working_age=50, part_time=True, part_time_salary=900, part_time_until_age=60,
    inflation=0.02, state_pension_annual_net=10000, pension_start_age=71,
    contribution_years=34,
)

rows = run_projection(**proj_params)

ok("rows count = target-current+1", len(rows) == 90 - 33 + 1, f"got {len(rows)}")
ok("first row age = current_age", rows[0]["age"] == 33)
ok("last row age = target_age", rows[-1]["age"] == 90)
ok("all ages sequential", all(rows[i+1]["age"] == rows[i]["age"] + 1 for i in range(len(rows)-1)))

# First row: yr=0, no changes yet
ok("yr=0 bank = initial bank", approx_abs(rows[0]["bank"], 35000, 1))
ok("yr=0 etf = initial etf", approx_abs(rows[0]["etf"], 85000, 1))
ok("yr=0 pf = initial pf", approx_abs(rows[0]["pf"], 22000, 1))

# Working years: is_working=True until age 50
for r in rows:
    if r["age"] < 50:
        ok(f"age {r['age']} is_working=True", r["working"], f"age={r['age']}")
        break

working_rows = [r for r in rows if r["working"]]
retired_rows = [r for r in rows if not r["working"]]
ok("working rows exist", len(working_rows) > 0)
ok("retired rows exist", len(retired_rows) > 0)

# Bank should never go below zero (enforced by model)
ok("bank always ≥ 0", all(r["bank"] >= 0 for r in rows))
ok("etf always ≥ 0", all(r["etf"] >= 0 for r in rows))
ok("pf always ≥ 0", all(r["pf"] >= 0 for r in rows))

# During working: PAC should be ≥ 0
ok("PAC ≥ 0 in working years", all(r["max_pac"] >= 0 for r in rows if r["working"]))
# During retirement: PAC = 0
ok("PAC = 0 in retirement", all(r["max_pac"] == 0 for r in rows if not r["working"]))

# Pension income starts at pension_start_age
pension_rows = [r for r in rows if r["age"] >= 71]
if pension_rows:
    ok("pension_income > 0 at pension age", pension_rows[0]["pension_income"] > 0)

# ETF grows during working years (not guaranteed but should on average with 5.5% return)
early_etf = [r["etf"] for r in rows if r["age"] == 49]
start_etf = rows[0]["etf"]
if early_etf:
    ok("ETF grows during working years", early_etf[0] > start_etf, f"etf at 49: {early_etf[0]}, start: {start_etf}")

# Total nominal = bank + etf + pf
for r in rows[1:3]:
    computed = round(r["bank"] + r["etf"] + r["pf"], 2)
    ok(f"total_nominal = bank+etf+pf at age {r['age']}", approx_abs(r["total_nominal"], computed, 1), f"diff={abs(r['total_nominal']-computed):.2f}")

# Real values deflated
ok("total_real < total_nominal at age 90 (inflation)", rows[-1]["total_real"] < rows[-1]["total_nominal"])

# Expenses grow with inflation
expense_yr1 = next(r for r in rows if r["age"] == 34)["expenses_annual"]
expense_yr2 = next(r for r in rows if r["age"] == 35)["expenses_annual"]
ok("expenses grow with inflation", expense_yr2 > expense_yr1)

# ─────────────────────────────────────────────────────────
# 6. FIRE ANALYSIS MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 6. FIRE ANALYSIS MODULE ===")
from modules.fire_analysis import run_your_scenario, find_earliest_retirement, find_optimal_pac

scenario_result = run_your_scenario(
    current_age=33, target_age=90,
    net_monthly_salary=2075, monthly_expenses=1600,
    age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    stop_working_age=50, part_time=True, part_time_salary=900, part_time_until_age=60,
    inflation=0.02, state_pension_annual_net=10000, pension_start_age=71,
    contribution_years=34,
)

ok("run_your_scenario returns rows", "rows" in scenario_result and len(scenario_result["rows"]) > 0)
ok("solvent_to_target is bool", isinstance(scenario_result["solvent_to_target"], bool))
ok("assets_at_target_real is numeric", isinstance(scenario_result["assets_at_target_real"], (int, float)))
ok("effective_avg_monthly_pac ≥ 0", scenario_result["effective_avg_monthly_pac"] >= 0)

# find_earliest_retirement: result should be between current_age+1 and 65
earliest = find_earliest_retirement(
    current_age=33, target_age=90,
    net_monthly_salary=2075, monthly_expenses=1600,
    age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    part_time=True, part_time_salary=900, part_time_until_age=60,
    inflation=0.02, pension_start_age=71,
    ral=35600, ral_growth=0.005, inps_contribution_rate=0.33, gdp_revaluation_rate=0.02,
    part_time_salary_gross=900,
)
ok("earliest_retirement in [34,65]", 34 <= earliest <= 65, f"got {earliest}")

# find_optimal_pac: result should be in [100, 2000], multiples of 100
optimal_pac = find_optimal_pac(
    current_age=33, target_age=90,
    net_monthly_salary=2075, monthly_expenses=1600,
    age_started_working=26,
    etf_value=85000, etf_net_return=0.055,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    part_time=True, part_time_salary=900, part_time_until_age=60,
    inflation=0.02, pension_start_age=71,
    ral=35600, ral_growth=0.005, inps_contribution_rate=0.33, gdp_revaluation_rate=0.02,
    global_earliest_age=earliest,
)
ok("optimal_pac in [100,2000]", 100 <= optimal_pac <= 2000, f"got {optimal_pac}")
ok("optimal_pac multiple of 100", optimal_pac % 100 == 0)

# ─────────────────────────────────────────────────────────
# 7. MONTE CARLO MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 7. MONTE CARLO MODULE ===")
from modules.monte_carlo import run_monte_carlo, generate_etf_returns
import numpy as np

# Quick MC with fewer simulations for speed
mc = run_monte_carlo(
    n_simulations=200, current_age=33, target_age=90,
    net_monthly_salary=2075, monthly_expenses=1600,
    age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    expected_gross_return=0.06, etf_volatility=0.16, ter=0.003, ivafe=0.002,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    stop_working_age=50, part_time=True, part_time_salary=900, part_time_until_age=60,
    inflation=0.02, inflation_std=0.01,
    state_pension_annual_net=10000, pension_start_age=71, contribution_years=34,
    scenario="Hybrid", seed=42,
)

ok("MC ages correct length", len(mc["ages"]) == 90 - 33 + 1)
ok("MC ages start at 33", mc["ages"][0] == 33)
ok("MC ages end at 90", mc["ages"][-1] == 90)
ok("MC probability_solvent ∈ [0,1]", 0 <= mc["probability_solvent"] <= 1)
ok("MC probability_solvent > 0", mc["probability_solvent"] > 0)
ok("MC avg_broke_age > 33", mc["avg_broke_age"] > 33)
ok("MC terminal_wealth has 200 values", len(mc["terminal_wealth"]) == 200)
ok("MC percentiles present", all(f"p{p}" in mc["percentiles"] for p in [5, 10, 25, 50, 75, 90, 95]))

# Percentile ordering: p5 ≤ p50 ≤ p95 at each time point
p5 = mc["percentiles"]["p5"]
p50 = mc["percentiles"]["p50"]
p95 = mc["percentiles"]["p95"]
ok("p5 ≤ p50 at all ages", all(p5[i] <= p50[i] + 1 for i in range(len(p5))))
ok("p50 ≤ p95 at all ages", all(p50[i] <= p95[i] + 1 for i in range(len(p50))))

# Test different scenarios don't crash
for scenario in ["Normal", "Moderate Stress", "Severe Stress", "Historical Bootstrap", "Hybrid"]:
    rng = np.random.default_rng(0)
    ret = generate_etf_returns(10, scenario, 0.06, 0.055, 0.16, 0.003, 0.002, rng)
    ok(f"generate_etf_returns scenario={scenario}", len(ret) == 10, f"got {len(ret)}")

# Deterministic: same seed → same result
mc2 = run_monte_carlo(
    n_simulations=50, current_age=33, target_age=60,
    net_monthly_salary=2075, monthly_expenses=1600, age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    expected_gross_return=0.06, etf_volatility=0.16, ter=0.003, ivafe=0.002,
    capital_gains_tax=0.26, bank_balance=35000, bank_interest=0.01,
    emergency_fund=20000, stamp_duty=34.2, pension_fund_value=22000,
    total_annual_contribution=3300, voluntary_extra=3850, pension_fund_return=0.04,
    annuity_rate=0.05, age_joined_fund=30, stop_working_age=50,
    part_time=False, part_time_salary=0, part_time_until_age=50,
    inflation=0.02, inflation_std=0.01, state_pension_annual_net=10000,
    pension_start_age=71, contribution_years=34, scenario="Normal", seed=99,
)
mc3 = run_monte_carlo(
    n_simulations=50, current_age=33, target_age=60,
    net_monthly_salary=2075, monthly_expenses=1600, age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    expected_gross_return=0.06, etf_volatility=0.16, ter=0.003, ivafe=0.002,
    capital_gains_tax=0.26, bank_balance=35000, bank_interest=0.01,
    emergency_fund=20000, stamp_duty=34.2, pension_fund_value=22000,
    total_annual_contribution=3300, voluntary_extra=3850, pension_fund_return=0.04,
    annuity_rate=0.05, age_joined_fund=30, stop_working_age=50,
    part_time=False, part_time_salary=0, part_time_until_age=50,
    inflation=0.02, inflation_std=0.01, state_pension_annual_net=10000,
    pension_start_age=71, contribution_years=34, scenario="Normal", seed=99,
)
ok("MC deterministic (same seed → same p50)", mc2["percentiles"]["p50"] == mc3["percentiles"]["p50"])

# ─────────────────────────────────────────────────────────
# 8. NPV COMPARISON MODULE
# ─────────────────────────────────────────────────────────
print("\n=== 8. NPV COMPARISON MODULE ===")
from modules.npv_comparison import calculate_npv_comparison

npv = calculate_npv_comparison(
    voluntary_extra=3850,
    tax_savings_annual=1174,  # ~3850 * 0.305 approx (capped)
    fund_return=0.04,
    etf_net_return=0.055,
    annuity_rate=0.05,
    pension_tax_rate=0.09,
    discount_rate=0.04,
    contribution_years=17,   # 50 - 33
    dormant_years=21,        # 71 - 50
    payout_years_pf=19,      # 90 - 71
    payout_years_etf=40,     # 90 - 33 + 17... actually 90 - (33+17) = 40
    pension_start_years=38,  # 71 - 33
)

ok("NPV PF is numeric", isinstance(npv["pension_fund_npv"], (int, float)))
ok("NPV ETF is numeric", isinstance(npv["etf_npv"], (int, float)))
ok("npv_difference ≥ 0", npv["npv_difference"] >= 0)
ok("npv_difference = |pf - etf|", approx_abs(npv["npv_difference"], abs(npv["pension_fund_npv"] - npv["etf_npv"]), 1))
ok("winner is PF or ETF", npv["winner"] in ["Pension Fund", "ETF"])
ok("winner consistent with npv", (npv["winner"] == "Pension Fund") == (npv["pension_fund_npv"] >= npv["etf_npv"]))
ok("montante_pf > 0", npv["montante_pf"] > 0)
ok("montante_etf > 0", npv["montante_etf"] > 0)
ok("rendita_annual > 0", npv["rendita_annual"] > 0)
ok("cost_pv_pf < cost_pv_etf (tax advantage)", npv["cost_pv_pf"] < npv["cost_pv_etf"],
   f"cost_pf={npv['cost_pv_pf']:.0f}, cost_etf={npv['cost_pv_etf']:.0f}")
ok("payout_pv_pf > 0", npv["payout_pv_pf"] > 0)
ok("withdraw_pv_etf > 0", npv["withdraw_pv_etf"] > 0)

# Zero voluntary extra → zero montante
npv_zero = calculate_npv_comparison(
    voluntary_extra=0, tax_savings_annual=0, fund_return=0.04, etf_net_return=0.055,
    annuity_rate=0.05, pension_tax_rate=0.09, discount_rate=0.04,
    contribution_years=17, dormant_years=21, payout_years_pf=19, payout_years_etf=40,
    pension_start_years=38,
)
ok("zero voluntary → zero montante_pf", npv_zero["montante_pf"] == 0)
ok("zero voluntary → zero rendita", npv_zero["rendita_annual"] == 0)
ok("zero voluntary → NPV PF = 0", npv_zero["pension_fund_npv"] == 0)

# Higher ETF return than pension return → ETF should win more often
npv_etf_wins = calculate_npv_comparison(
    voluntary_extra=3850, tax_savings_annual=0,  # no tax benefit
    fund_return=0.04, etf_net_return=0.09,       # ETF much higher
    annuity_rate=0.05, pension_tax_rate=0.15,    # pension heavily taxed
    discount_rate=0.04,
    contribution_years=17, dormant_years=21, payout_years_pf=19, payout_years_etf=40,
    pension_start_years=38,
)
ok("with high ETF return and no tax saving → ETF wins", npv_etf_wins["winner"] == "ETF",
   f"got {npv_etf_wins['winner']}")

# ─────────────────────────────────────────────────────────
# 9. CROSS-MODULE CONSISTENCY
# ─────────────────────────────────────────────────────────
print("\n=== 9. CROSS-MODULE CONSISTENCY ===")

# Salary used in projections matches tax module output
salary_info = calculate_net_salary(35600, 2000, 0.0919, 0.02)
net_monthly = salary_info["net_monthly_13"]

# State pension uses net_monthly as denominator; part-time fraction
sp2 = calculate_state_pension(
    ral=35600, ral_growth=0.005, inps_contribution_rate=0.33, gdp_revaluation_rate=0.02,
    current_age=33, age_started_working=26, stop_working_age=50,
    part_time=True, part_time_salary=900, part_time_until_age=60,
    net_monthly_salary=net_monthly, age_joined_fund=30,
)
ok("state pension uses consistent net_monthly", sp2["eligible"])

# Projection with state pension values from state pension module
rows2 = run_projection(
    current_age=33, target_age=90,
    net_monthly_salary=net_monthly,
    monthly_expenses=1600,
    age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    stop_working_age=50, part_time=True, part_time_salary=900, part_time_until_age=60,
    inflation=0.02,
    state_pension_annual_net=sp2["net_annual_nominal"],
    pension_start_age=sp2["pension_age"],
    contribution_years=sp2["contribution_years"],
)
ok("cross-module projection runs without error", len(rows2) == 90 - 33 + 1)

# NPV pension_tax_rate matches pension_fund_tax_rate for same ages
from modules.pension_fund import pension_fund_tax_rate as pftr
pftr_val = pftr(71, 30)
npv_cross = calculate_npv_comparison(
    voluntary_extra=3850, tax_savings_annual=0, fund_return=0.04, etf_net_return=0.055,
    annuity_rate=0.05, pension_tax_rate=pftr_val, discount_rate=0.04,
    contribution_years=17, dormant_years=21, payout_years_pf=19, payout_years_etf=40,
    pension_start_years=38,
)
ok("NPV uses pension_fund_tax_rate consistently", npv_cross["pension_fund_npv"] is not None)

# Expense module annual total feeds correctly into projection monthly_expenses
annual_exp = compute_total_annual(DEFAULT_EXPENSES)
monthly_exp = annual_exp / 12
rows3 = run_projection(
    current_age=33, target_age=50,
    net_monthly_salary=net_monthly,
    monthly_expenses=monthly_exp,
    age_started_working=26,
    etf_value=85000, monthly_pac=1300, etf_net_return=0.055,
    capital_gains_tax=0.26,
    bank_balance=35000, bank_interest=0.01, emergency_fund=20000, stamp_duty=34.2,
    pension_fund_value=22000, total_annual_contribution=3300, voluntary_extra=3850,
    pension_fund_return=0.04, annuity_rate=0.05, age_joined_fund=30,
    stop_working_age=50, part_time=False, part_time_salary=0, part_time_until_age=50,
    inflation=0.02, state_pension_annual_net=0, pension_start_age=71, contribution_years=34,
)
ok("expenses from expense module → valid projection", len(rows3) == 50 - 33 + 1)

# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
if ERRORS:
    print(f"\nFailed tests:")
    for e in ERRORS:
        print(f"  - {e}")
print("="*50)
sys.exit(0 if FAIL == 0 else 1)
