"""
FIRE Planning Tool — Streamlit app for Italian workers.
v2: TFR azienda/fondo, part-time IRPEF, Trattamento Integrativo,
    pensione anticipata, coppia, FIRE Number, sensitivity, scenario comparison,
    export Excel, save/load JSON.
"""
import copy
import io
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from modules.constants import DEFAULT_ASSUMPTIONS, DEFAULT_EXPENSES, INPS_COEFFICIENTS
from modules.tax import calculate_net_salary, marginal_irpef_rate, gross_to_net_annual
from modules.expenses import compute_category_totals, compute_total_monthly, compute_total_annual
from modules.pension_state import calculate_state_pension
from modules.pension_fund import calculate_pension_fund_info, pension_fund_tax_rate
from modules.projections import run_projection
from modules.fire_analysis import run_your_scenario, find_earliest_retirement, find_optimal_pac
from modules.npv_comparison import calculate_npv_comparison
from modules.monte_carlo import run_monte_carlo, SCENARIO_OPTIONS
from modules.sensitivity import run_sensitivity, AXIS_VARIABLES, OUTPUT_METRICS

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="FIRE Planning Tool",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def fmt_eur(value: float, decimals: int = 0) -> str:
    if decimals == 0:
        return f"€ {value:,.0f}"
    return f"€ {value:,.{decimals}f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


# ─────────────────────────────────────────────
# Cached wrappers
# ─────────────────────────────────────────────
@st.cache_data
def _cached_find_earliest(**kwargs):
    return find_earliest_retirement(**kwargs)


@st.cache_data
def _cached_optimal_pac(**kwargs):
    return find_optimal_pac(**kwargs)


@st.cache_data
def _cached_monte_carlo(**kwargs):
    return run_monte_carlo(**kwargs)


@st.cache_data
def _cached_sensitivity(**kwargs):
    return run_sensitivity(**kwargs)


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
def sidebar_inputs():
    st.sidebar.title("⚙️ Parameters")

    # ── Display mode toggle ────────────────────────────────────────────────
    _mode = st.sidebar.radio(
        "📊 Chart display mode",
        ["Real (today's €)", "Nominal (year-of-payment €)"],
        index=0,
        horizontal=True,
        key="display_mode_radio",
        help="Real: inflation-adjusted to today's purchasing power. "
             "Nominal: future money at face value.",
    )
    st.session_state["display_real"] = (_mode == "Real (today's €)")
    st.sidebar.divider()

    D = DEFAULT_ASSUMPTIONS
    p = D["personal"]
    s = D["salary"]
    e = D["etf"]
    b = D["bank"]
    pf = D["pension_fund"]
    m = D["macro"]
    f = D["fire_scenario"]
    mc = D["monte_carlo"]
    po = D["pension_options"]
    cp = D["couple"]

    with st.sidebar.expander("👤 Personal", expanded=True):
        current_age = st.number_input("Current age", 18, 70, p["current_age"])
        target_age = st.number_input("Target age (end of simulation)", 70, 100, p["target_age"])
        age_started_working = st.number_input("Age started working", 16, 50, p["age_started_working"],
            help="Age when INPS contributions started.")

    with st.sidebar.expander("💼 Salary & Tax"):
        ral = st.number_input("Gross annual salary RAL (€)", 10000, 200000, s["ral"], step=500)
        company_benefits = st.number_input("Company benefits (€/year)", 0, 20000, s["company_benefits"], step=100)
        inps_emp_pct = st.number_input("INPS employee rate (%)", 0.0, 20.0,
            round(s["inps_employee_rate"] * 100, 4), step=0.1, format="%.2f")
        surcharges_pct = st.number_input("Regional/municipal surcharges (%)", 0.0, 10.0,
            round(s["surcharges_rate"] * 100, 3), step=0.1, format="%.2f")

    with st.sidebar.expander("📈 ETF / PAC"):
        etf_value = st.number_input("Current ETF value (€)", 0, 2000000, e["current_value"], step=1000)
        monthly_pac = st.number_input("Monthly PAC investment (€)", 0, 5000, e["monthly_pac"], step=50)
        ter_pct = st.number_input("Annual TER (%)", 0.0, 2.0, round(e["ter"] * 100, 3), step=0.05, format="%.2f")
        ivafe_pct = st.number_input("Annual IVAFE (%)", 0.0, 1.0, round(e["ivafe"] * 100, 3), step=0.05, format="%.2f")
        gross_return_pct = st.number_input("Expected gross ETF return (%)", 1.0, 20.0,
            round(e["expected_gross_return"] * 100, 2), step=0.1, format="%.1f")
        cgt_pct = st.number_input("Capital gains tax (%)", 0.0, 50.0,
            round(e["capital_gains_tax"] * 100, 1), step=1.0, format="%.0f")

    with st.sidebar.expander("🏦 Bank Account"):
        bank_balance = st.number_input("Bank balance (€)", 0, 500000, b["current_balance"], step=1000)
        bank_interest_pct = st.number_input("Bank interest rate (%)", 0.0, 10.0,
            round(b["interest_rate"] * 100, 3), step=0.1, format="%.2f")
        emergency_fund = st.number_input("Emergency fund (€)", 0, 100000, b["emergency_fund"], step=1000)
        stamp_duty = st.number_input("Annual stamp duty (€)", 0.0, 100.0, b["stamp_duty"],
            step=1.0, format="%.2f")

    with st.sidebar.expander("🏛️ Pension Fund & TFR"):
        tfr_destination = st.radio(
            "TFR destination",
            options=["fund", "company"],
            index=0 if pf.get("tfr_destination", "fund") == "fund" else 1,
            format_func=lambda x: "Pension fund (default)" if x == "fund" else "Left with employer (TFR company)",
            help="If 'company': TFR stays with employer, revalued at 1.5%+75%×ISTAT, paid net at termination.",
        )
        pf_value = st.number_input("Pension fund value (€)", 0, 500000, pf["current_value"], step=1000)
        tfr_contribution = st.number_input("TFR annual contribution (€)", 0, 10000,
            pf["tfr_contribution"], step=100,
            help="Annual TFR redirected to the pension fund (only relevant if TFR is in 'fund').")
        if tfr_destination == "company":
            tfr_company_value = st.number_input(
                "Current TFR in company (€)", 0, 200000, pf.get("tfr_company_value", 0), step=1000,
                help="Current accumulated TFR balance in the company. Will grow at 1.5%+75%×inflation and be paid net at early retirement.")
        else:
            tfr_company_value = 0
        employer_contribution = st.number_input("Employer contribution (€/year)", 0, 10000,
            pf["employer_contribution"], step=100)
        personal_contribution = st.number_input("Personal base contribution (€/year)", 0, 10000,
            pf["personal_contribution"], step=100)
        voluntary_extra = st.number_input("Extra voluntary contribution (€/year)", 0, 20000,
            pf["voluntary_extra"], step=100)
        max_deductible = st.number_input("Max deductible (€)", 0.0, 10000.0,
            pf["max_deductible"], step=100.0, format="%.2f")
        fund_return_pct = st.number_input("Pension fund return (%)", 0.0, 15.0,
            round(pf["fund_return"] * 100, 2), step=0.1, format="%.1f")
        annuity_rate_pct = st.number_input("Annuity conversion rate (%)", 0.0, 10.0,
            round(pf["annuity_rate"] * 100, 2), step=0.1, format="%.1f")
        age_joined_fund = st.number_input("Age joined pension fund", 18, 65, pf["age_joined"], step=1)

    with st.sidebar.expander("🌍 Macro"):
        inflation_pct = st.number_input("Expected inflation (%)", 0.0, 10.0,
            round(m["inflation"] * 100, 2), step=0.1, format="%.1f")
        ral_growth_pct = st.number_input("Annual salary growth (%)", 0.0, 10.0,
            round(m["ral_growth"] * 100, 2), step=0.1, format="%.1f")
        inps_rate_pct = st.number_input("Total INPS contribution rate (%)", 10.0, 40.0,
            round(m["inps_contribution_rate"] * 100, 1), step=0.5, format="%.1f",
            help="Total INPS rate (employee + employer) for state pension accrual.")
        gdp_rev_pct = st.number_input("GDP revaluation rate for INPS (%)", 0.0, 5.0,
            round(m["gdp_revaluation_rate"] * 100, 2), step=0.1, format="%.1f")

    with st.sidebar.expander("🔥 FIRE Scenario"):
        stop_working_age = st.number_input("Target retirement age", int(current_age) + 1, 70,
            f["stop_working_age"], step=1)
        part_time = st.checkbox("Part-time work after retirement?", value=f["part_time"])
        if part_time:
            pt_gross_toggle = st.checkbox("Enter part-time as gross (RAL)?", value=False,
                help="If checked, enter gross monthly income and net will be computed via IRPEF.")
            if pt_gross_toggle:
                part_time_monthly_gross = st.number_input(
                    "Monthly gross part-time income (€)", 0, 10000,
                    int(f.get("part_time_monthly_gross", 0) or 1100), step=100,
                    help="Gross monthly income — net will be calculated after IRPEF.")
                part_time_salary = 0.0  # will be derived
            else:
                part_time_monthly_gross = 0.0
                part_time_salary = st.number_input("Monthly net part-time income (€)", 0, 5000,
                    f["part_time_salary"], step=100)
            part_time_until_age = st.number_input("Part-time until age",
                int(stop_working_age), 70, f["part_time_until_age"], step=1)
        else:
            part_time_monthly_gross = 0.0
            part_time_salary = 0
            part_time_until_age = int(stop_working_age)
        swr_pct = st.number_input("Safe Withdrawal Rate / SWR (%)", 1.0, 10.0,
            round(f["safe_withdrawal_rate"] * 100, 2), step=0.1, format="%.1f")

    with st.sidebar.expander("🏦 Early Pension (Pensione Anticipata)"):
        defer_to_71 = st.checkbox("Defer state pension to 71 (max coefficient)?", value=po.get("defer_to_71", False),
            help="If checked, pension age = 71 for maximum INPS coefficient. Otherwise, standard pension at 67.")
        early_pension = st.checkbox("Early pension (41+ contribution years)?",
            value=(po.get("early_pension_years", 0) > 0),
            help="If checked, pension starts when contribution years threshold is reached (min age 57).")
        if early_pension and not defer_to_71:
            early_pension_years = st.number_input(
                "Contribution years threshold", 20, 45, po.get("early_pension_years", 41),
                help="Standard early pension: 41 years + 10 months (women) / 42 + 10 months (men).")
        else:
            early_pension_years = 0
        le_adjustment = st.checkbox(
            "Apply life expectancy adjustment (Fornero)?",
            value=po.get("le_adjustment", False),
            help="ISTAT reviews life expectancy every 2 years and increases the vecchiaia age by ~3 months "
                 "per period. Checked: shifts standard pension age upward from 67 (+0.25 yrs per 2-yr period).",
        )
        if le_adjustment and not defer_to_71 and early_pension_years == 0:
            _years_to_67 = max(0, 67 - int(current_age))
            _le_periods = _years_to_67 // 2
            _le_delta = _le_periods * 0.25
            vecchiaia_age = min(71, round(67 + _le_delta))
            st.caption(f"Projected vecchiaia age: **{vecchiaia_age}** "
                       f"(+{_le_delta:.2f} yrs, {_le_periods} bienni ISTAT from now)")
        else:
            vecchiaia_age = 67

    with st.sidebar.expander("👫 Couple mode"):
        couple_enabled = st.checkbox("Add partner income?", value=cp.get("enabled", False))
        if couple_enabled:
            couple_net_monthly = st.number_input("Partner net monthly income (€)", 0, 20000,
                int(cp.get("partner_net_monthly", 1500)), step=100,
                help="Partner's net monthly income (after tax). Added to household cash flow while they are working.")
            couple_stop_working_age = st.number_input("Partner stops working at age", int(current_age) + 1, 70,
                int(cp.get("partner_stop_working_age", 0) or int(stop_working_age)),
                help="Age at which partner stops working (0 = same as primary earner).")
        else:
            couple_net_monthly = 0.0
            couple_stop_working_age = 0

    with st.sidebar.expander("🎲 Monte Carlo"):
        n_simulations = st.number_input("Number of simulations", 100, 5000, mc["n_simulations"], step=100)
        etf_vol_pct = st.number_input("ETF annual volatility (%)", 5.0, 40.0,
            round(mc["etf_volatility"] * 100, 1), step=1.0, format="%.0f")
        pf_vol_pct = st.number_input("Pension fund volatility (%)", 0.0, 20.0,
            round(mc["pension_fund_volatility"] * 100, 1), step=1.0, format="%.0f")
        inflation_std_pct = st.number_input("Inflation std deviation (%)", 0.0, 5.0,
            round(mc["inflation_std"] * 100, 2), step=0.1, format="%.1f")
        mc_scenario = st.selectbox("Monte Carlo scenario", SCENARIO_OPTIONS,
            index=SCENARIO_OPTIONS.index(mc["scenario"]))

    # ── Save / Load scenario ──────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("💾 Save / Load Scenario")

    # Build saveable config from current widget state
    _save_config = {
        "current_age": int(current_age), "target_age": int(target_age),
        "age_started_working": int(age_started_working),
        "ral": float(ral), "company_benefits": float(company_benefits),
        "inps_employee_rate": inps_emp_pct / 100, "surcharges_rate": surcharges_pct / 100,
        "etf_value": float(etf_value), "monthly_pac": float(monthly_pac),
        "ter": ter_pct / 100, "ivafe": ivafe_pct / 100,
        "expected_gross_return": gross_return_pct / 100, "capital_gains_tax": cgt_pct / 100,
        "bank_balance": float(bank_balance), "bank_interest": bank_interest_pct / 100,
        "emergency_fund": float(emergency_fund), "stamp_duty": float(stamp_duty),
        "pf_value": float(pf_value), "tfr_contribution": float(tfr_contribution),
        "tfr_destination": tfr_destination, "tfr_company_value": float(tfr_company_value),
        "employer_contribution": float(employer_contribution),
        "personal_contribution": float(personal_contribution),
        "voluntary_extra": float(voluntary_extra), "max_deductible": float(max_deductible),
        "fund_return": fund_return_pct / 100, "annuity_rate": annuity_rate_pct / 100,
        "age_joined_fund": int(age_joined_fund),
        "inflation": inflation_pct / 100, "ral_growth": ral_growth_pct / 100,
        "inps_contribution_rate": inps_rate_pct / 100, "gdp_revaluation_rate": gdp_rev_pct / 100,
        "stop_working_age": int(stop_working_age), "part_time": bool(part_time),
        "part_time_salary": float(part_time_salary),
        "part_time_monthly_gross": float(part_time_monthly_gross),
        "part_time_until_age": int(part_time_until_age), "swr": swr_pct / 100,
        "defer_to_71": bool(defer_to_71), "early_pension_years": int(early_pension_years),
        "le_adjustment": bool(le_adjustment), "vecchiaia_age": int(vecchiaia_age),
        "couple_net_monthly": float(couple_net_monthly),
        "couple_stop_working_age": int(couple_stop_working_age),
        "n_simulations": int(n_simulations), "etf_volatility": etf_vol_pct / 100,
        "pf_volatility": pf_vol_pct / 100, "inflation_std": inflation_std_pct / 100,
        "mc_scenario": mc_scenario,
    }

    st.sidebar.download_button(
        "⬇️ Download scenario JSON",
        data=json.dumps(_save_config, indent=2),
        file_name="fire_scenario.json",
        mime="application/json",
    )

    uploaded = st.sidebar.file_uploader("⬆️ Load scenario JSON", type="json", key="json_upload")
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.read())
            st.sidebar.success("Scenario loaded! Refresh the page to apply all values.")
            st.session_state["loaded_scenario"] = loaded
        except Exception as ex:
            st.sidebar.error(f"Failed to parse JSON: {ex}")

    return _save_config


# ─────────────────────────────────────────────
# Tab 1: Monthly Expenses
# ─────────────────────────────────────────────
def tab_spese(expenses_state):
    st.header("💸 Monthly Expenses")
    st.caption("Edit your expenses by category. Frequencies: Monthly, Quarterly, Semi-annual, Annual.")

    updated_expenses = {}
    all_rows = []

    for category, items in expenses_state.items():
        with st.expander(f"📂 {category}", expanded=False):
            edited_items = []
            for i, item in enumerate(items):
                cols = st.columns([3, 2, 2, 1])
                name = cols[0].text_input("Name", item["name"], key=f"{category}_{i}_name")
                freq = cols[1].selectbox("Frequency",
                    ["Monthly", "Quarterly", "Semi-annual", "Annual"],
                    index=["Monthly", "Quarterly", "Semi-annual", "Annual"].index(item["frequency"]),
                    key=f"{category}_{i}_freq")
                amount = cols[2].number_input("Amount (€)", 0.0, 10000.0, float(item["amount"]),
                    step=5.0, key=f"{category}_{i}_amount")
                edited_items.append({"name": name, "frequency": freq, "amount": amount})
                monthly_val = amount / {"Monthly": 1, "Quarterly": 3, "Semi-annual": 6, "Annual": 12}[freq]
                all_rows.append({"Category": category, "Item": name, "Frequency": freq,
                                  "Amount": amount, "Monthly equiv.": monthly_val})
            updated_expenses[category] = edited_items

    cat_totals = compute_category_totals(updated_expenses)
    total_monthly = compute_total_monthly(updated_expenses)
    total_annual = compute_total_annual(updated_expenses)

    st.divider()
    col1, col2 = st.columns(2)
    col1.metric("Total Monthly", fmt_eur(total_monthly, 2))
    col2.metric("Total Annual", fmt_eur(total_annual))

    fig = px.bar(
        x=list(cat_totals.keys()), y=list(cat_totals.values()),
        labels={"x": "Category", "y": "€/month"},
        title="Monthly expenses by category",
        color=list(cat_totals.values()), color_continuous_scale="Blues",
    )
    fig.update_layout(showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    return updated_expenses, total_monthly


# ─────────────────────────────────────────────
# Tab 2: Salary & Tax
# ─────────────────────────────────────────────
def tab_salary(p):
    st.header("💰 Salary & Tax (IRPEF 2025)")

    tax_result = calculate_net_salary(
        p["ral"], p["company_benefits"], p["inps_employee_rate"], p["surcharges_rate"]
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gross RAL", fmt_eur(p["ral"]))
    col2.metric("Net Annual Salary", fmt_eur(tax_result["net_annual_salary"]))
    col3.metric("Net Monthly (÷13)", fmt_eur(tax_result["net_monthly_13"]))
    col4.metric("Net Monthly (÷12)", fmt_eur(tax_result["net_monthly_12"]))

    st.divider()

    # Part-time net preview
    if p.get("part_time") and p.get("part_time_monthly_gross", 0) > 0:
        pt_net = gross_to_net_annual(
            p["part_time_monthly_gross"] * 12,
            p["inps_employee_rate"],
            p["surcharges_rate"],
        )
        st.info(
            f"Part-time gross {fmt_eur(p['part_time_monthly_gross'])}/month → "
            f"**Net {fmt_eur(pt_net / 13, 2)}/month** (÷13 after IRPEF)"
        )

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Tax Breakdown")
        ti = tax_result["trattamento_integrativo"]
        breakdown_rows = [
            ("INPS (employee share)", tax_result["inps"]),
            ("Taxable income", tax_result["taxable_income"]),
            ("Gross IRPEF", tax_result["irpef"]),
            ("Employment deductions (detrazioni lav. dip.)", -tax_result["deductions"]),
        ]
        if ti > 0:
            breakdown_rows.append(("Tax bonus (Trattamento Integrativo 2025)", -ti))
        breakdown_rows += [
            ("Regional/municipal surcharges", tax_result["surcharges"]),
            ("Net IRPEF + surcharges", tax_result["net_irpef"]),
        ]
        df = pd.DataFrame(breakdown_rows, columns=["Item", "Amount (€)"])
        df["Amount (€)"] = df["Amount (€)"].apply(lambda x: fmt_eur(x))
        st.dataframe(df, use_container_width=True, hide_index=True)
        if ti > 0:
            st.success(f"Tax Bonus (Trattamento Integrativo): +{fmt_eur(ti)}/year ({fmt_eur(ti/12, 2)}/month)")

    with col_b:
        st.subheader("RAL Breakdown")
        labels = ["INPS", "Net IRPEF", "Benefits", "Take-home pay"]
        values = [
            tax_result["inps"],
            tax_result["net_irpef"],
            p["company_benefits"],
            tax_result["net_annual_salary"] - p["company_benefits"],
        ]
        colors = ["#EF553B", "#FFA15A", "#00CC96", "#636EFA"]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.45,
            marker_colors=colors, textinfo="label+percent",
        ))
        fig.update_layout(title="Where does your RAL go?", height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Marginal IRPEF rate: {fmt_pct(tax_result['marginal_rate'])}")
    return tax_result


# ─────────────────────────────────────────────
# Tab 3: Projections
# ─────────────────────────────────────────────
def tab_projections(p, net_monthly_salary, monthly_expenses, pension_info, rows):
    st.header("📊 Wealth Projections")

    df = pd.DataFrame(rows)

    # Show TFR column only if in azienda mode
    show_tfr = p.get("tfr_destination") == "company" and any(r.get("tfr_company", 0) > 0 for r in rows)

    display_real = st.session_state.get("display_real", True)

    if not display_real:
        st.warning(
            "⚠️ Showing **nominal** values — future money at face value, **not** adjusted for inflation. "
            "Switch to *Real* mode in the sidebar for inflation-adjusted figures."
        )

    ages = [r["age"] for r in rows]
    if display_real:
        banks_  = [r["bank_real"] for r in rows]
        etfs_   = [r["etf_real"] for r in rows]
        pfs_    = [r["pf_real"] for r in rows]
        tfrs_   = [r.get("tfr_real", 0) for r in rows]
        totals_ = [r["total_real"] for r in rows]
        y_label = "€ real (today's purchasing power)"
        mode_label = "real (today's €, inflation-adjusted)"
        total_name = "Total Real"
    else:
        banks_  = [r["bank"] for r in rows]
        etfs_   = [r["etf"] for r in rows]
        pfs_    = [r["pf"] for r in rows]
        tfrs_   = [r.get("tfr_company", 0) for r in rows]
        totals_ = [r["total_nominal"] for r in rows]
        y_label = "€ nominal (year-of-payment)"
        mode_label = "nominal (future money, not inflation-adjusted)"
        total_name = "Total Nominal"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ages, y=banks_, name="Bank Account",
                              stackgroup="one", fill="tonexty", line_color="#636EFA"))
    fig.add_trace(go.Scatter(x=ages, y=pfs_, name="Pension Fund",
                              stackgroup="one", fill="tonexty", line_color="#00CC96"))
    fig.add_trace(go.Scatter(x=ages, y=etfs_, name="ETF",
                              stackgroup="one", fill="tonexty", line_color="#FFA15A"))
    if show_tfr:
        fig.add_trace(go.Scatter(x=ages, y=tfrs_, name="TFR",
                                  stackgroup="one", fill="tonexty", line_color="#AB63FA"))
    fig.add_trace(go.Scatter(x=ages, y=totals_, name=total_name, mode="lines",
                              line=dict(color="white", width=2, dash="dot")))

    fig.add_vline(x=p["stop_working_age"], line_dash="dash", line_color="red",
                  annotation_text=f"Early retirement {p['stop_working_age']}")
    if pension_info["eligible"]:
        fig.add_vline(x=pension_info["pension_age"], line_dash="dash", line_color="green",
                      annotation_text=f"State pension {pension_info['pension_age']}")

    fig.update_layout(
        title=f"Wealth Evolution by Asset Class — {mode_label}",
        xaxis_title="Age", yaxis_title=y_label,
        hovermode="x unified", template="plotly_dark", height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Detailed Table")
    display_cols = ["age", "bank_real", "etf_real", "pf_real", "total_real", "bank", "etf", "pf", "total_nominal"]
    col_names    = ["Age", "Bank real (€)", "ETF real (€)", "Pension Fund real (€)", "Total Real (€)",
                    "Bank nominal (€)", "ETF nominal (€)", "Pension Fund nominal (€)", "Total Nominal (€)"]
    if show_tfr:
        display_cols.insert(4, "tfr_real")
        col_names.insert(4, "TFR real (€)")

    df_display = df[display_cols].copy()
    df_display.columns = col_names
    for col in col_names[1:]:
        df_display[col] = df_display[col].apply(lambda x: fmt_eur(x))
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # ── Export Excel ──────────────────────────────────────────────────────
    st.subheader("⬇️ Export")
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Projection", index=False)
            # Summary sheet
            summary = pd.DataFrame([
                ["RAL", p["ral"]],
                ["Net Monthly (÷13)", float(net_monthly_salary)],
                ["Monthly Expenses", monthly_expenses],
                ["ETF Gross Return %", p["expected_gross_return"] * 100],
                ["Stop Working Age", p["stop_working_age"]],
                ["FIRE Number (at SWR)", monthly_expenses * 12 / p["swr"]],
                ["Pension Age", pension_info["pension_age"]],
                ["Pension Annual Net", pension_info["net_annual_nominal"]],
            ], columns=["Parameter", "Value"])
            summary.to_excel(writer, sheet_name="Summary", index=False)
        st.download_button(
            "📥 Download Excel",
            data=buf.getvalue(),
            file_name="fire_projection.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as ex:
        st.warning(f"Excel export unavailable: {ex}")


# ─────────────────────────────────────────────
# Tab 4: FIRE Analysis
# ─────────────────────────────────────────────
def tab_fire_results(p, net_monthly_salary, monthly_expenses, pension_info, tax_result):
    st.header("🔥 FIRE Analysis")

    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]
    # TFR goes to fund unless destination is "company"
    tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
    total_annual_contribution = tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]
    tfr_accrual = p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0

    # ── FIRE Number ───────────────────────────────────────────────────────
    annual_expenses = monthly_expenses * 12
    fire_number = annual_expenses / p["swr"]
    current_liquid = p["etf_value"] + p["bank_balance"] - p["emergency_fund"]
    progress_pct = min(100.0, current_liquid / fire_number * 100) if fire_number > 0 else 0.0
    savings = float(net_monthly_salary) - monthly_expenses
    savings_rate = savings / float(net_monthly_salary) if net_monthly_salary > 0 else 0.0
    if p.get("couple_net_monthly", 0) > 0:
        couple_annual = p["couple_net_monthly"] * 12
        savings += p["couple_net_monthly"]
        savings_rate = (float(net_monthly_salary) + p["couple_net_monthly"] - monthly_expenses) / (
            float(net_monthly_salary) + p["couple_net_monthly"]
        )

    st.subheader("🎯 FIRE Number")
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("FIRE Number", fmt_eur(fire_number),
               help=f"Annual expenses / SWR = {fmt_eur(annual_expenses)} / {fmt_pct(p['swr'])}")
    fc2.metric("Current liquid wealth", fmt_eur(current_liquid))
    fc3.metric("FIRE progress", f"{progress_pct:.1f}%")
    fc4.metric("Savings rate", fmt_pct(savings_rate))
    st.progress(int(min(100, progress_pct)))

    st.divider()

    _common = dict(
        current_age=p["current_age"], target_age=p["target_age"],
        net_monthly_salary=net_monthly_salary, monthly_expenses=monthly_expenses,
        age_started_working=p["age_started_working"], etf_value=p["etf_value"],
        etf_net_return=etf_net_return, capital_gains_tax=p["capital_gains_tax"],
        bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
        emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
        pension_fund_value=p["pf_value"], total_annual_contribution=total_annual_contribution,
        voluntary_extra=p["voluntary_extra"], pension_fund_return=p["fund_return"],
        annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
        part_time=p["part_time"], part_time_salary=p["part_time_salary"],
        part_time_until_age=p["part_time_until_age"], inflation=p["inflation"],
        ral=p["ral"], ral_growth=p["ral_growth"],
        inps_contribution_rate=p["inps_contribution_rate"],
        gdp_revaluation_rate=p["gdp_revaluation_rate"],
        part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
        inps_employee_rate=p["inps_employee_rate"], surcharges_rate=p["surcharges_rate"],
        tfr_destination=p.get("tfr_destination", "fund"),
        tfr_annual_accrual=tfr_accrual,
        tfr_company_value=p.get("tfr_company_value", 0.0),
        tfr_revaluation_rate=0.015,
        couple_net_monthly=p.get("couple_net_monthly", 0.0),
        couple_stop_working_age=p.get("couple_stop_working_age", 0),
        early_pension_years=p.get("early_pension_years", 0),
        defer_to_71=p.get("defer_to_71", False),
    )

    with st.spinner("Running your scenario..."):
        scenario_result = run_your_scenario(
            monthly_pac=p["monthly_pac"],
            stop_working_age=p["stop_working_age"],
            state_pension_annual_net=pension_info["net_annual_nominal"] if pension_info["eligible"] else 0.0,
            pension_start_age=pension_info["pension_age"],
            contribution_years=pension_info["contribution_years"],
            **_common,
        )

    solvent = scenario_result["solvent_to_target"]
    assets_at_target = scenario_result["assets_at_target_real"]
    eff_pac = scenario_result["effective_avg_monthly_pac"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Solvent to target age?", "✅ Yes" if solvent else "❌ No")
    col2.metric(f"Real wealth at {p['target_age']}", fmt_eur(assets_at_target))
    col3.metric("Effective avg monthly PAC", fmt_eur(eff_pac, 2))

    st.divider()

    with st.spinner("Finding earliest possible retirement age..."):
        earliest_age = _cached_find_earliest(
            monthly_pac=p["monthly_pac"],
            pension_start_age=pension_info["pension_age"],
            part_time_salary_gross=p["part_time_salary"],
            **_common,
        )

    col_a, col_b = st.columns(2)
    col_a.metric("Earliest possible FIRE age", f"{earliest_age} years",
                  delta=f"{earliest_age - p['current_age']} years to FIRE")
    contrib_at_fire = earliest_age - p["age_started_working"]
    if contrib_at_fire < 20:
        st.warning(
            f"⚠️ At FIRE age {earliest_age} you would have only **{contrib_at_fire} contribution years** "
            f"(need ≥20 for INPS state pension). Solvency is based entirely on your investment portfolio — "
            f"**no state pension income** is included in this projection."
        )

    with st.spinner("Computing optimal PAC..."):
        optimal_pac = _cached_optimal_pac(
            pension_start_age=pension_info["pension_age"],
            global_earliest_age=earliest_age,
            part_time_salary_gross=p["part_time_salary"],
            **_common,
        )
    col_b.metric("Optimal monthly PAC (minimum for FIRE)", fmt_eur(optimal_pac))

    st.divider()
    st.subheader("Real wealth at target age for different retirement ages")
    test_ages = list(range(max(p["current_age"] + 1, 38), 66, 2))

    with st.spinner("Running scenario sweep..."):
        sweep_data = []
        for test_age in test_ages:
            p_info = calculate_state_pension(
                ral=p["ral"], ral_growth=p["ral_growth"],
                inps_contribution_rate=p["inps_contribution_rate"],
                gdp_revaluation_rate=p["gdp_revaluation_rate"],
                current_age=p["current_age"], age_started_working=p["age_started_working"],
                stop_working_age=test_age, part_time=p["part_time"],
                part_time_salary=p["part_time_salary"],
                part_time_until_age=p["part_time_until_age"],
                net_monthly_salary=float(net_monthly_salary),
                age_joined_fund=p["age_joined_fund"],
                part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
                early_pension_years=p.get("early_pension_years", 0),
                defer_to_71=p.get("defer_to_71", False),
                base_vecchiaia_age=p.get("vecchiaia_age", 67),
            )
            rs = run_your_scenario(
                monthly_pac=p["monthly_pac"],
                stop_working_age=test_age,
                state_pension_annual_net=p_info["net_annual_nominal"] if p_info["eligible"] else 0.0,
                pension_start_age=p_info["pension_age"],
                contribution_years=p_info["contribution_years"],
                **_common,
            )
            sweep_data.append({
                "Retirement age": test_age,
                "Real wealth (€)": rs["assets_at_target_real"],
                "Solvent": rs["solvent_to_target"],
            })

    df_sweep = pd.DataFrame(sweep_data)
    colors = ["#00CC96" if s else "#EF553B" for s in df_sweep["Solvent"]]
    fig_sweep = go.Figure(go.Bar(
        x=df_sweep["Retirement age"], y=df_sweep["Real wealth (€)"],
        marker_color=colors,
        text=[fmt_eur(v) for v in df_sweep["Real wealth (€)"]],
        textposition="outside",
    ))
    fig_sweep.add_hline(y=0, line_dash="dash", line_color="white")
    fig_sweep.update_layout(
        title="Real wealth at target age vs retirement age (green=solvent, red=broke)",
        xaxis_title="Retirement age", yaxis_title="€ real",
        template="plotly_dark", height=400,
    )
    st.plotly_chart(fig_sweep, use_container_width=True)


# ─────────────────────────────────────────────
# Tab 5: State Pension & Pension Fund
# ─────────────────────────────────────────────
def tab_pension(p, net_monthly_salary, pension_info, tax_result):
    st.header("🏛️ State Pension (INPS) & Supplementary Pension Fund")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("INPS State Pension (Contributory Method)")
        early_yrs = p.get("early_pension_years", 0)
        if early_yrs > 0:
            st.info(f"Early pension enabled: threshold {early_yrs} contribution years")
        if p.get("defer_to_71"):
            st.info("Pension deferred to age 71 for maximum INPS coefficient")

        st.caption("⚠️ Figures are **nominal** (future money at pension age). "
                   "IRPEF-taxed. Supplementary fund shown separately →")
        if p.get("le_adjustment") and not p.get("defer_to_71") and not p.get("early_pension_years"):
            _adj = p.get("vecchiaia_age", 67) - 67
            st.info(
                f"Life expectancy adjustment active: standard pension age shifted from 67 to "
                f"**{p.get('vecchiaia_age', 67)}** (+{_adj} yr). "
                f"Based on ISTAT +3 months per 2-year period (Riforma Fornero)."
            )
        if pension_info["eligible"]:
            st.success(f"Eligible for state pension at age **{pension_info['pension_age']}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("INPS pension age", f"{pension_info['pension_age']} yrs")
            m2.metric("Contribution years", pension_info["contribution_years"])
            m3.metric("Pension pot (montante)", fmt_eur(pension_info["montante"]))
            m4, m5 = st.columns(2)
            m4.metric("Gross annual pension — nominal at retirement",
                      fmt_eur(pension_info["gross_annual"]))
            m5.metric("Net annual pension — nominal at retirement",
                      fmt_eur(pension_info["net_annual_nominal"]))
            # Real equivalent in today's money
            years_to_pension = pension_info["pension_age"] - p["current_age"]
            real_equiv_monthly = pension_info["net_monthly_nominal"] / (
                (1 + p["inflation"]) ** years_to_pension)
            st.metric("Net monthly pension (÷13) — nominal at retirement",
                      fmt_eur(pension_info["net_monthly_nominal"]),
                      help=f"In today's purchasing power ≈ {fmt_eur(real_equiv_monthly)}/month "
                           f"(deflated {years_to_pension} yrs at {p['inflation']:.1%}/yr)")
        else:
            st.error("Not eligible for INPS state pension — insufficient contribution years (need ≥20)")

    with col2:
        st.subheader("Supplementary Pension Fund")
        tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
        pf_info = calculate_pension_fund_info(
            current_value=p["pf_value"],
            tfr_contribution=tfr_to_fund,
            employer_contribution=p["employer_contribution"],
            personal_contribution=p["personal_contribution"],
            voluntary_extra=p["voluntary_extra"],
            max_deductible=p["max_deductible"],
            fund_return=p["fund_return"],
            annuity_rate=p["annuity_rate"],
            age_joined=p["age_joined_fund"],
            taxable_income=tax_result["taxable_income"],
        )
        m1, m2 = st.columns(2)
        m1.metric("Total base annual contribution", fmt_eur(pf_info["total_base_contribution"]))
        m2.metric("With voluntary extra", fmt_eur(pf_info["total_with_voluntary"]))
        m3, m4 = st.columns(2)
        m3.metric("Deductible amount", fmt_eur(pf_info["actual_deductible"]))
        m4.metric("Annual tax saving", fmt_eur(pf_info["tax_savings"]))

        if p.get("tfr_destination") == "company":
            st.warning(
                f"TFR stays with employer — not flowing into the pension fund. "
                f"TFR accrual: ~{fmt_eur(p['ral']/13.5, 0)}/year"
            )

        pf_tax_age = pension_fund_tax_rate(pension_info["pension_age"], p["age_joined_fund"])
        st.caption(f"Pension fund payout tax rate at age {pension_info['pension_age']}: {fmt_pct(pf_tax_age)}")

    st.divider()
    st.subheader("⚖️ NPV Comparison: Pension Fund vs ETF")

    contrib_yrs_npv = max(1, p["stop_working_age"] - p["current_age"])
    dormant_yrs_npv = max(0, pension_info["pension_age"] - p["stop_working_age"])
    payout_yrs_pf   = max(1, p["target_age"] - pension_info["pension_age"])
    payout_yrs_etf  = max(1, p["target_age"] - p["current_age"] - contrib_yrs_npv)
    pension_start_yrs = pension_info["pension_age"] - p["current_age"]
    pf_tax_at_pension = pension_fund_tax_rate(pension_info["pension_age"], p["age_joined_fund"])
    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]
    actual_deductible = min(
        p["employer_contribution"] + p["personal_contribution"] + p["voluntary_extra"],
        p["max_deductible"],
    )
    tax_sav_annual = round(actual_deductible * marginal_irpef_rate(tax_result["taxable_income"]), 0)

    npv_result = calculate_npv_comparison(
        voluntary_extra=p["voluntary_extra"],
        tax_savings_annual=tax_sav_annual,
        fund_return=p["fund_return"],
        etf_net_return=etf_net_return,
        annuity_rate=p["annuity_rate"],
        pension_tax_rate=pf_tax_at_pension,
        discount_rate=p["inflation"],
        contribution_years=contrib_yrs_npv,
        dormant_years=dormant_yrs_npv,
        payout_years_pf=payout_yrs_pf,
        payout_years_etf=payout_yrs_etf,
        pension_start_years=pension_start_yrs,
        swr=p["swr"],
        capital_gains_tax=p["capital_gains_tax"],
    )

    col_n1, col_n2, col_n3 = st.columns(3)
    col_n1.metric("NPV Pension Fund", fmt_eur(npv_result["pension_fund_npv"], 2))
    col_n2.metric("NPV ETF", fmt_eur(npv_result["etf_npv"], 2))
    col_n3.metric("NPV Difference", fmt_eur(npv_result["npv_difference"], 2),
                   help=f"Winner: {npv_result['winner']}")

    if npv_result["winner"] != "ETF":
        st.success(f"🏆 **Pension Fund** wins (NPV +{fmt_eur(npv_result['npv_difference'], 2)})")
    else:
        st.info(f"🏆 **ETF** wins (NPV +{fmt_eur(npv_result['npv_difference'], 2)})")

    fig_npv = go.Figure(go.Bar(
        x=["Pension Fund", "ETF"],
        y=[npv_result["pension_fund_npv"], npv_result["etf_npv"]],
        marker_color=["#00CC96", "#636EFA"],
        text=[fmt_eur(v, 0) for v in [npv_result["pension_fund_npv"], npv_result["etf_npv"]]],
        textposition="outside",
    ))
    fig_npv.update_layout(
        title="NPV Comparison: Pension Fund vs ETF",
        yaxis_title="Net Present Value (€)",
        template="plotly_dark", height=350,
    )
    st.plotly_chart(fig_npv, use_container_width=True)


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# Tab 6: Summary Dashboard
# ─────────────────────────────────────────────
def tab_dashboard(p, tax_result, monthly_expenses, pension_info, rows):
    st.header("📋 Summary Dashboard")

    net_mo = tax_result["net_monthly_13"]
    couple_mo = p.get("couple_net_monthly", 0.0)
    total_income_monthly = float(net_mo) + float(couple_mo)
    monthly_savings = total_income_monthly - monthly_expenses
    savings_rate = monthly_savings / total_income_monthly if total_income_monthly > 0 else 0.0
    fire_number = monthly_expenses * 12 / p["swr"]
    current_liquid = p["etf_value"] + p["bank_balance"] - p["emergency_fund"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Net monthly income", fmt_eur(total_income_monthly),
               help="Primary + partner net monthly income" if couple_mo > 0 else "Net monthly salary")
    c2.metric("Monthly expenses", fmt_eur(monthly_expenses, 2))
    c3.metric("Monthly savings", fmt_eur(monthly_savings))
    c4.metric("Savings rate", fmt_pct(savings_rate))
    c5.metric("INPS pension / year", fmt_eur(pension_info["net_annual_nominal"]) if pension_info["eligible"] else "N/A")

    st.divider()

    f1, f2, f3 = st.columns(3)
    f1.metric("FIRE Number", fmt_eur(fire_number),
               help=f"Target portfolio = annual expenses / SWR")
    f2.metric("Current liquid wealth", fmt_eur(current_liquid))
    progress_pct = min(100.0, current_liquid / fire_number * 100) if fire_number > 0 else 0.0
    f3.metric("FIRE progress", f"{progress_pct:.1f}%")
    st.progress(int(min(100, progress_pct)))

    st.divider()

    # Wealth evolution chart
    if rows:
        display_real = st.session_state.get("display_real", True)

        if not display_real:
            st.warning(
                "⚠️ Showing **nominal** values — future money at face value, **not** adjusted for inflation. "
                "Switch to *Real* mode in the sidebar for inflation-adjusted figures."
            )

        st.subheader("📈 Wealth Evolution")
        ages_d = [r["age"] for r in rows]
        if display_real:
            _etf_y  = [r["etf_real"] for r in rows]
            _pf_y   = [r["pf_real"] for r in rows]
            _bank_y = [r["bank_real"] for r in rows]
            _dash_title = "Wealth by component — real (today's €, inflation-adjusted)"
            _y_axis = "€ real"
        else:
            _etf_y  = [r["etf"] for r in rows]
            _pf_y   = [r["pf"] for r in rows]
            _bank_y = [r["bank"] for r in rows]
            _dash_title = "Wealth by component — nominal (year-of-payment €)"
            _y_axis = "€ nominal"

        fig_dash = go.Figure()
        fig_dash.add_trace(go.Scatter(x=ages_d, y=_etf_y,
                                      name="ETF", stackgroup="wealth",
                                      line=dict(color="#636EFA")))
        fig_dash.add_trace(go.Scatter(x=ages_d, y=_pf_y,
                                      name="Pension Fund", stackgroup="wealth",
                                      line=dict(color="#00CC96")))
        fig_dash.add_trace(go.Scatter(x=ages_d, y=_bank_y,
                                      name="Bank", stackgroup="wealth",
                                      line=dict(color="#FFA15A")))
        fig_dash.add_vline(x=p["stop_working_age"], line_dash="dash", line_color="red",
                           annotation_text="Retire", annotation_position="top right")
        fig_dash.update_layout(
            title=_dash_title,
            xaxis_title="Age", yaxis_title=_y_axis,
            template="plotly_dark", height=380, hovermode="x unified",
        )
        st.plotly_chart(fig_dash, use_container_width=True)

    st.divider()

    _mode_caption = "today's purchasing power, inflation-adjusted" if st.session_state.get("display_real", True) else "nominal future money — not inflation-adjusted"
    st.caption(f"Snapshot amounts in {_mode_caption}.")
    # Snapshots
    display_real = st.session_state.get("display_real", True)
    _snap_suffix = "real" if display_real else "nominal"
    for snap_age, snap_label in [(50, "50"), (p["target_age"], str(p["target_age"]))]:
        row = next((r for r in rows if r["age"] == snap_age), None)
        if row:
            st.subheader(f"📸 Wealth snapshot at age {snap_label} ({_snap_suffix} €)")
            cols = st.columns(4 if p.get("tfr_destination") != "company" else 5)
            if display_real:
                cols[0].metric("Bank", fmt_eur(row["bank_real"]))
                cols[1].metric("ETF", fmt_eur(row["etf_real"]))
                cols[2].metric("Pension Fund", fmt_eur(row["pf_real"]))
                if p.get("tfr_destination") == "company":
                    cols[3].metric("TFR", fmt_eur(row.get("tfr_real", 0)))
                    cols[4].metric("Total", fmt_eur(row["total_real"]))
                else:
                    cols[3].metric("Total", fmt_eur(row["total_real"]))
            else:
                cols[0].metric("Bank", fmt_eur(row["bank"]))
                cols[1].metric("ETF", fmt_eur(row["etf"]))
                cols[2].metric("Pension Fund", fmt_eur(row["pf"]))
                if p.get("tfr_destination") == "company":
                    cols[3].metric("TFR", fmt_eur(row.get("tfr_company", 0)))
                    cols[4].metric("Total", fmt_eur(row["total_nominal"]))
                else:
                    cols[3].metric("Total", fmt_eur(row["total_nominal"]))

    if p.get("couple_net_monthly", 0) > 0:
        st.info(
            f"Partner income: {fmt_eur(p['couple_net_monthly'])}/month included until age "
            f"{p.get('couple_stop_working_age') or p['stop_working_age']}."
        )
    if tax_result.get("trattamento_integrativo", 0) > 0:
        ti = tax_result["trattamento_integrativo"]
        st.success(f"Tax Bonus (Trattamento Integrativo): +{fmt_eur(ti)}/year applied to your IRPEF.")


# ─────────────────────────────────────────────
# Tab 8: Sensitivity Analysis
# ─────────────────────────────────────────────
def tab_sensitivity(p, net_monthly_salary, monthly_expenses, pension_info):
    st.header("🔬 Sensitivity Analysis")

    axis_options = list(AXIS_VARIABLES.keys())

    sc1, sc2, sc3 = st.columns(3)
    output_metric = sc1.selectbox("Output metric", OUTPUT_METRICS, index=0)
    y_var = sc2.selectbox("Y variable (rows)", axis_options,
                          index=axis_options.index("Monthly expenses"))
    x_default = "ETF net return" if y_var != "ETF net return" else "Monthly expenses"
    x_options = [v for v in axis_options if v != y_var]
    x_var = sc3.selectbox("X variable (columns)", x_options,
                          index=x_options.index(x_default) if x_default in x_options else 0)

    st.caption(
        f"How **{output_metric.lower()}** changes as "
        f"**{x_var}** (columns) and **{y_var}** (rows) vary from your base values."
    )

    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]
    tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
    total_annual_contribution = tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]

    with st.spinner("Computing 25 scenarios..."):
        df_sens = _cached_sensitivity(
            base_etf_net_return=etf_net_return,
            base_monthly_expenses=monthly_expenses,
            current_age=p["current_age"], target_age=p["target_age"],
            net_monthly_salary=float(net_monthly_salary),
            age_started_working=p["age_started_working"],
            etf_value=p["etf_value"], monthly_pac=p["monthly_pac"],
            capital_gains_tax=p["capital_gains_tax"],
            bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
            emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
            pension_fund_value=p["pf_value"],
            total_annual_contribution=total_annual_contribution,
            voluntary_extra=p["voluntary_extra"],
            pension_fund_return=p["fund_return"],
            annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
            part_time=p["part_time"], part_time_salary=p["part_time_salary"],
            part_time_until_age=p["part_time_until_age"], inflation=p["inflation"],
            pension_start_age=pension_info["pension_age"],
            ral=p["ral"], ral_growth=p["ral_growth"],
            inps_contribution_rate=p["inps_contribution_rate"],
            gdp_revaluation_rate=p["gdp_revaluation_rate"],
            stop_working_age=p["stop_working_age"],
            part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
            inps_employee_rate=p["inps_employee_rate"],
            surcharges_rate=p["surcharges_rate"],
            tfr_destination=p.get("tfr_destination", "fund"),
            tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
            tfr_company_value=p.get("tfr_company_value", 0.0),
            couple_net_monthly=p.get("couple_net_monthly", 0.0),
            couple_stop_working_age=p.get("couple_stop_working_age", 0),
            early_pension_years=p.get("early_pension_years", 0),
            defer_to_71=p.get("defer_to_71", False),
            x_var=x_var,
            y_var=y_var,
            output_metric=output_metric,
        )

    # Heatmap config depends on metric
    is_age_metric = output_metric == "Earliest retirement age"
    color_scale  = "RdYlGn_r" if is_age_metric else "RdYlGn"
    color_label  = "Age (years)" if is_age_metric else "Portfolio (€k)"
    better_note  = "lower = better" if is_age_metric else "higher = better"

    fig_heat = px.imshow(
        df_sens.values,
        x=df_sens.columns.tolist(),
        y=df_sens.index.tolist(),
        color_continuous_scale=color_scale,
        text_auto=True,
        labels={"x": x_var, "y": y_var, "color": color_label},
        title=f"{output_metric} ({better_note})",
        aspect="auto",
    )
    fig_heat.update_layout(template="plotly_dark", height=420)
    st.plotly_chart(fig_heat, use_container_width=True)

    st.subheader("Table")
    st.dataframe(df_sens, use_container_width=True)

    # Key metrics — find the base cell (delta = +0 for both axes)
    x_zero = AXIS_VARIABLES[x_var]["label_fmt"].format(0.0)
    y_zero = AXIS_VARIABLES[y_var]["label_fmt"].format(0.0)
    base_val = df_sens.loc[y_zero, x_zero] if y_zero in df_sens.index and x_zero in df_sens.columns else None
    if base_val is not None:
        if is_age_metric:
            best_case  = int(df_sens.values.min())
            worst_case = int(df_sens.values.max())
            fmt_v = lambda v: f"{v} yrs"
        else:
            best_case  = int(df_sens.values.max())
            worst_case = int(df_sens.values.min())
            fmt_v = lambda v: f"€{v}k"
        base_val = int(base_val)
        bc1, bc2, bc3 = st.columns(3)
        bc1.metric("Base case", fmt_v(base_val))
        # For age: lower is better → invert Streamlit's default green=positive convention
        dc = "inverse" if is_age_metric else "normal"
        bc2.metric("Best case", fmt_v(best_case),
                   delta=f"{best_case - base_val:+d}", delta_color=dc)
        bc3.metric("Worst case", fmt_v(worst_case),
                   delta=f"{worst_case - base_val:+d}", delta_color=dc)


# ─────────────────────────────────────────────
# Tab 8: Scenarios & Monte Carlo (unified)
# ─────────────────────────────────────────────
def tab_scenarios_mc(p, net_monthly_salary, monthly_expenses, pension_info):
    st.header("📊 Scenari & Monte Carlo")
    st.caption("Confronta tre strategie, poi verifica la robustezza stocastica con Monte Carlo.")

    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]
    tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
    total_annual_contribution = tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]

    _base = dict(
        current_age=p["current_age"], target_age=p["target_age"],
        net_monthly_salary=float(net_monthly_salary), monthly_expenses=monthly_expenses,
        age_started_working=p["age_started_working"],
        etf_value=p["etf_value"], etf_net_return=etf_net_return,
        capital_gains_tax=p["capital_gains_tax"],
        bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
        emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
        pension_fund_value=p["pf_value"],
        total_annual_contribution=total_annual_contribution,
        voluntary_extra=p["voluntary_extra"], pension_fund_return=p["fund_return"],
        annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
        part_time=p["part_time"], part_time_salary=p["part_time_salary"],
        part_time_until_age=p["part_time_until_age"], inflation=p["inflation"],
        part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
        inps_employee_rate=p["inps_employee_rate"], surcharges_rate=p["surcharges_rate"],
        tfr_destination=p.get("tfr_destination", "fund"),
        tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
        tfr_company_value=p.get("tfr_company_value", 0.0),
        couple_net_monthly=p.get("couple_net_monthly", 0.0),
        couple_stop_working_age=p.get("couple_stop_working_age", 0),
    )

    # ── Scenario definitions ──────────────────────────────────────────────
    st.subheader("Definisci i 3 scenari")
    base_etf = p["expected_gross_return"] - p["ter"] - p["ivafe"]

    scol1, scol2, scol3 = st.columns(3)

    with scol1:
        st.markdown("**Scenario A**")
        a_name    = st.text_input("Name A", "Conservativo (ritiro tardivo)", key="sc_a_name")
        a_retire  = st.number_input("Retire age", p["current_age"] + 1, 70,
                        min(65, p["stop_working_age"] + 5), key="sc_a_retire")
        a_pac     = st.number_input("Monthly PAC (€)", 0, 10_000, int(p["monthly_pac"]), step=50, key="sc_a_pac")
        a_exp     = st.number_input("Monthly expenses (€)", 500, 20_000, int(monthly_expenses), step=100, key="sc_a_exp")
        a_etf     = st.number_input("ETF net return (%)", 0.0, 20.0, round(base_etf * 100, 2), step=0.1, key="sc_a_etf") / 100
        a_infl    = st.number_input("Inflation (%)", 0.0, 10.0, round(p["inflation"] * 100, 1), step=0.1, key="sc_a_infl") / 100
        a_ral     = st.number_input("Annual gross salary RAL (€)", 10_000, 500_000, int(p["ral"]), step=1_000, key="sc_a_ral")

    with scol2:
        st.markdown("**Scenario B** (Base)")
        b_name    = st.text_input("Name B", "Base scenario", key="sc_b_name")
        b_retire  = st.number_input("Retire age", p["current_age"] + 1, 70,
                        p["stop_working_age"], key="sc_b_retire")
        b_pac     = st.number_input("Monthly PAC (€)", 0, 10_000, int(p["monthly_pac"]), step=50, key="sc_b_pac")
        b_exp     = st.number_input("Monthly expenses (€)", 500, 20_000, int(monthly_expenses), step=100, key="sc_b_exp")
        b_etf     = st.number_input("ETF net return (%)", 0.0, 20.0, round(base_etf * 100, 2), step=0.1, key="sc_b_etf") / 100
        b_infl    = st.number_input("Inflation (%)", 0.0, 10.0, round(p["inflation"] * 100, 1), step=0.1, key="sc_b_infl") / 100
        b_ral     = st.number_input("Annual gross salary RAL (€)", 10_000, 500_000, int(p["ral"]), step=1_000, key="sc_b_ral")

    with scol3:
        st.markdown("**Scenario C**")
        c_name    = st.text_input("Name C", "Aggressivo (ritiro anticipato)", key="sc_c_name")
        c_retire  = st.number_input("Retire age", p["current_age"] + 1, 70,
                        max(p["current_age"] + 1, p["stop_working_age"] - 5), key="sc_c_retire")
        c_pac     = st.number_input("Monthly PAC (€)", 0, 10_000,
                        min(10_000, int(p["monthly_pac"]) + 200), step=50, key="sc_c_pac")
        c_exp     = st.number_input("Monthly expenses (€)", 500, 20_000, int(monthly_expenses), step=100, key="sc_c_exp")
        c_etf     = st.number_input("ETF net return (%)", 0.0, 20.0, round(base_etf * 100, 2), step=0.1, key="sc_c_etf") / 100
        c_infl    = st.number_input("Inflation (%)", 0.0, 10.0, round(p["inflation"] * 100, 1), step=0.1, key="sc_c_infl") / 100
        c_ral     = st.number_input("Annual gross salary RAL (€)", 10_000, 500_000, int(p["ral"]), step=1_000, key="sc_c_ral")

    scenarios = [
        (a_name, a_retire, a_pac, a_exp, a_etf, a_infl, a_ral),
        (b_name, b_retire, b_pac, b_exp, b_etf, b_infl, b_ral),
        (c_name, c_retire, c_pac, c_exp, c_etf, c_infl, c_ral),
    ]

    with st.spinner("Calcolo 3 scenari deterministici..."):
        results = []
        for name, retire_age, pac, sc_exp, sc_etf, sc_infl, sc_ral in scenarios:
            p_info = calculate_state_pension(
                ral=sc_ral, ral_growth=p["ral_growth"],
                inps_contribution_rate=p["inps_contribution_rate"],
                gdp_revaluation_rate=p["gdp_revaluation_rate"],
                current_age=p["current_age"], age_started_working=p["age_started_working"],
                stop_working_age=retire_age, part_time=p["part_time"],
                part_time_salary=p["part_time_salary"],
                part_time_until_age=p["part_time_until_age"],
                net_monthly_salary=float(net_monthly_salary),
                age_joined_fund=p["age_joined_fund"],
                part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
                early_pension_years=p.get("early_pension_years", 0),
                defer_to_71=p.get("defer_to_71", False),
                base_vecchiaia_age=p.get("vecchiaia_age", 67),
            )
            sc_base = {**_base,
                       "monthly_expenses": sc_exp,
                       "etf_net_return": sc_etf,
                       "inflation": sc_infl,
                       "ral": sc_ral}
            rs = run_your_scenario(
                monthly_pac=pac,
                stop_working_age=retire_age,
                state_pension_annual_net=p_info["net_annual_nominal"] if p_info["eligible"] else 0.0,
                pension_start_age=p_info["pension_age"],
                contribution_years=p_info["contribution_years"],
                **sc_base,
            )
            results.append({
                "name": name,
                "retire_age": retire_age,
                "pac": pac,
                "expenses": sc_exp,
                "etf": sc_etf,
                "inflation": sc_infl,
                "ral": sc_ral,
                "pension_age": p_info["pension_age"],
                "pension_net": p_info["net_annual_nominal"] if p_info["eligible"] else 0,
                "contribution_years": p_info["contribution_years"],
                "rows": rs["rows"],
                "solvent": rs["solvent_to_target"],
                "final_wealth": rs["assets_at_target_real"],
            })

    # ── Key metrics ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Metriche chiave")
    cols = st.columns(3)
    for res, col in zip(results, cols):
        with col:
            status = "✅ Solvent" if res["solvent"] else "❌ Broke"
            st.markdown(f"**{res['name']}**")
            st.metric("Retire age", res["retire_age"])
            st.metric("Monthly PAC", fmt_eur(res["pac"]))
            st.metric("Monthly expenses", fmt_eur(res["expenses"]))
            st.metric("ETF net return", fmt_pct(res["etf"]))
            st.metric("Inflation", fmt_pct(res["inflation"]))
            st.metric("RAL", fmt_eur(res["ral"]))
            st.metric("Status", status)
            st.metric(f"Real wealth at {p['target_age']}", fmt_eur(res["final_wealth"]))
            st.metric("State pension age", res["pension_age"])
            st.metric("State pension/year", fmt_eur(res["pension_net"]))

    # ── Deterministic wealth chart ────────────────────────────────────────
    st.subheader("Evoluzione del patrimonio — deterministico")
    colors_sc = ["#EF553B", "#636EFA", "#00CC96"]
    fig_cmp = go.Figure()
    for res, color in zip(results, colors_sc):
        ages_sc = [r["age"] for r in res["rows"]]
        totals_sc = [r["total_real"] for r in res["rows"]]
        fig_cmp.add_trace(go.Scatter(
            x=ages_sc, y=totals_sc,
            name=res["name"],
            line=dict(color=color, width=2),
        ))
    fig_cmp.add_hline(y=0, line_dash="dash", line_color="white")
    fig_cmp.update_layout(
        title="Patrimonio reale totale nel tempo — 3 scenari",
        xaxis_title="Età", yaxis_title="€ reali",
        template="plotly_dark", hovermode="x unified", height=450,
    )
    st.plotly_chart(fig_cmp, use_container_width=True)

    # ── Monte Carlo — parametri base ─────────────────────────────────────
    st.divider()
    st.subheader("🎲 Monte Carlo — parametri base")
    st.caption(
        f"Scenario: **{p['mc_scenario']}** | Simulazioni: **{p['n_simulations']}** · "
        "Usa i parametri principali della sidebar, non quelli degli scenari sopra."
    )

    with st.spinner(f"Running {p['n_simulations']} simulations..."):
        mc_result = _cached_monte_carlo(
            n_simulations=p["n_simulations"],
            current_age=p["current_age"], target_age=p["target_age"],
            net_monthly_salary=float(net_monthly_salary),
            monthly_expenses=monthly_expenses,
            age_started_working=p["age_started_working"],
            etf_value=p["etf_value"], monthly_pac=p["monthly_pac"],
            etf_net_return=etf_net_return,
            expected_gross_return=p["expected_gross_return"],
            etf_volatility=p["etf_volatility"],
            ter=p["ter"], ivafe=p["ivafe"],
            capital_gains_tax=p["capital_gains_tax"],
            bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
            emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
            pension_fund_value=p["pf_value"],
            total_annual_contribution=total_annual_contribution,
            voluntary_extra=p["voluntary_extra"],
            pension_fund_return=p["fund_return"],
            annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
            stop_working_age=p["stop_working_age"],
            part_time=p["part_time"], part_time_salary=p["part_time_salary"],
            part_time_until_age=p["part_time_until_age"],
            inflation=p["inflation"], inflation_std=p["inflation_std"],
            state_pension_annual_net=pension_info["net_annual_nominal"] if pension_info["eligible"] else 0.0,
            pension_start_age=pension_info["pension_age"],
            contribution_years=pension_info["contribution_years"],
            scenario=p["mc_scenario"],
            part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
            inps_employee_rate=p["inps_employee_rate"],
            surcharges_rate=p["surcharges_rate"],
            tfr_destination=p.get("tfr_destination", "fund"),
            tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
            tfr_company_value=p.get("tfr_company_value", 0.0),
            couple_net_monthly=p.get("couple_net_monthly", 0.0),
            couple_stop_working_age=p.get("couple_stop_working_age", 0),
        )

    pct = mc_result["percentiles"]
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Probabilità solvenza", f"{mc_result['probability_solvent'] * 100:.1f}%")
    mc2.metric("Età media di rovina (se accade)", f"{mc_result['avg_broke_age']:.1f} anni")
    mc3.metric(f"Patrimonio mediano (P50) a {p['target_age']}", fmt_eur(pct["p50"][-1]))

    ages_mc = mc_result["ages"]
    fig_mc = go.Figure()
    bands = [
        ("p5",  "p95", "rgba(99,110,250,0.10)", "P5–P95"),
        ("p10", "p90", "rgba(99,110,250,0.20)", "P10–P90"),
        ("p25", "p75", "rgba(99,110,250,0.35)", "P25–P75"),
    ]
    for lo, hi, color, bname in bands:
        fig_mc.add_trace(go.Scatter(
            x=ages_mc + ages_mc[::-1],
            y=pct[hi] + pct[lo][::-1],
            fill="toself", fillcolor=color,
            line=dict(color="rgba(0,0,0,0)"),
            name=bname,
        ))
    fig_mc.add_trace(go.Scatter(x=ages_mc, y=pct["p50"], name="Mediana (P50)",
                                line=dict(color="#636EFA", width=2)))
    fig_mc.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Patrimonio = 0")
    fig_mc.add_vline(x=p["stop_working_age"], line_dash="dash", line_color="orange",
                     annotation_text=f"Ritiro {p['stop_working_age']}")
    fig_mc.update_layout(
        title="Monte Carlo: Liquidità reale (Banca + ETF) — parametri base",
        xaxis_title="Età", yaxis_title="€ reali",
        template="plotly_dark", hovermode="x unified", height=500,
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    st.subheader(f"Distribuzione patrimonio terminale (età {p['target_age']})")
    fig_hist = px.histogram(
        x=mc_result["terminal_wealth"], nbins=50,
        labels={"x": "Patrimonio reale (€)", "y": "Simulazioni"},
        color_discrete_sequence=["#636EFA"],
        title=f"Distribuzione del patrimonio reale a {p['target_age']} anni",
    )
    fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
    fig_hist.update_layout(template="plotly_dark", height=350)
    st.plotly_chart(fig_hist, use_container_width=True)

    st.subheader("Percentili a età chiave — parametri base")
    key_ages = sorted(set(a for a in [
        p["current_age"], p["stop_working_age"], 60, pension_info["pension_age"], p["target_age"]
    ] if p["current_age"] <= a <= p["target_age"]))
    pct_table = [{
        "Età": ka,
        "P5": fmt_eur(pct["p5"][ages_mc.index(ka)]),
        "P25": fmt_eur(pct["p25"][ages_mc.index(ka)]),
        "P50": fmt_eur(pct["p50"][ages_mc.index(ka)]),
        "P75": fmt_eur(pct["p75"][ages_mc.index(ka)]),
        "P95": fmt_eur(pct["p95"][ages_mc.index(ka)]),
    } for ka in key_ages if ka in ages_mc]
    if pct_table:
        st.dataframe(pd.DataFrame(pct_table), use_container_width=True, hide_index=True)

    # ── MC confronto scenari (solo tabella) ──────────────────────────────
    st.divider()
    st.subheader("📋 Confronto Monte Carlo tra scenari")
    st.caption(
        "Stesso seed casuale per tutti e 3 (Common Random Numbers): le differenze riflettono "
        f"i parametri, non il rumore. Simulazioni: min({p['n_simulations']}, 500)."
    )
    run_mc_cmp = st.checkbox(
        "Calcola Monte Carlo per i 3 scenari?",
        value=False,
        key="sc_run_mc",
        help="Avvia N simulazioni per scenario (N da sidebar, massimo 500).",
    )

    if run_mc_cmp:
        _n_sim = min(p["n_simulations"], 500)
        mc_results_list = []
        with st.spinner(f"Running {_n_sim} × 3 scenari (stesso seed = CRN)…"):
            for res in results:
                _mc = _cached_monte_carlo(
                    n_simulations=_n_sim,
                    current_age=p["current_age"], target_age=p["target_age"],
                    net_monthly_salary=float(net_monthly_salary),
                    monthly_expenses=res["expenses"],
                    age_started_working=p["age_started_working"],
                    etf_value=p["etf_value"], monthly_pac=res["pac"],
                    etf_net_return=res["etf"],
                    expected_gross_return=res["etf"] + p["ter"] + p["ivafe"],
                    etf_volatility=p["etf_volatility"],
                    ter=p["ter"], ivafe=p["ivafe"],
                    capital_gains_tax=p["capital_gains_tax"],
                    bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
                    emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
                    pension_fund_value=p["pf_value"],
                    total_annual_contribution=total_annual_contribution,
                    voluntary_extra=p["voluntary_extra"],
                    pension_fund_return=p["fund_return"],
                    annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
                    stop_working_age=res["retire_age"],
                    part_time=p["part_time"], part_time_salary=p["part_time_salary"],
                    part_time_until_age=p["part_time_until_age"],
                    inflation=res["inflation"], inflation_std=p["inflation_std"],
                    state_pension_annual_net=res["pension_net"],
                    pension_start_age=res["pension_age"],
                    contribution_years=res["contribution_years"],
                    scenario=p["mc_scenario"],
                    seed=42,
                    part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
                    inps_employee_rate=p["inps_employee_rate"],
                    surcharges_rate=p["surcharges_rate"],
                    tfr_destination=p.get("tfr_destination", "fund"),
                    tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
                    tfr_company_value=p.get("tfr_company_value", 0.0),
                    couple_net_monthly=p.get("couple_net_monthly", 0.0),
                    couple_stop_working_age=p.get("couple_stop_working_age", 0),
                )
                mc_results_list.append(_mc)

        _summary_rows = []
        for res, mc_r in zip(results, mc_results_list):
            _pct = mc_r["percentiles"]
            _summary_rows.append({
                "Scenario": res["name"],
                "Età ritiro": res["retire_age"],
                "P(solvenza)": f"{mc_r['probability_solvent'] * 100:.1f}%",
                "Età media rovina": f"{mc_r['avg_broke_age']:.0f}" if mc_r["probability_solvent"] < 1.0 else "—",
                f"P10 a {p['target_age']}": fmt_eur(_pct["p10"][-1]),
                f"P50 a {p['target_age']}": fmt_eur(_pct["p50"][-1]),
                f"P90 a {p['target_age']}": fmt_eur(_pct["p90"][-1]),
            })
        st.dataframe(pd.DataFrame(_summary_rows), use_container_width=True, hide_index=True)



    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]
    tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
    total_annual_contribution = tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]

    _base = dict(
        current_age=p["current_age"], target_age=p["target_age"],
        net_monthly_salary=float(net_monthly_salary), monthly_expenses=monthly_expenses,
        age_started_working=p["age_started_working"],
        etf_value=p["etf_value"], etf_net_return=etf_net_return,
        capital_gains_tax=p["capital_gains_tax"],
        bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
        emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
        pension_fund_value=p["pf_value"],
        total_annual_contribution=total_annual_contribution,
        voluntary_extra=p["voluntary_extra"], pension_fund_return=p["fund_return"],
        annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
        part_time=p["part_time"], part_time_salary=p["part_time_salary"],
        part_time_until_age=p["part_time_until_age"], inflation=p["inflation"],
        part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
        inps_employee_rate=p["inps_employee_rate"], surcharges_rate=p["surcharges_rate"],
        tfr_destination=p.get("tfr_destination", "fund"),
        tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
        tfr_company_value=p.get("tfr_company_value", 0.0),
        couple_net_monthly=p.get("couple_net_monthly", 0.0),
        couple_stop_working_age=p.get("couple_stop_working_age", 0),
    )

    # Scenario definitions
    st.subheader("Define Scenarios")
    base_etf = p["expected_gross_return"] - p["ter"] - p["ivafe"]

    scol1, scol2, scol3 = st.columns(3)

    with scol1:
        st.markdown("**Scenario A**")
        a_name    = st.text_input("Name A", "Conservative (retire later)", key="sc_a_name")
        a_retire  = st.number_input("Retire age", p["current_age"] + 1, 70,
                        min(65, p["stop_working_age"] + 5), key="sc_a_retire")
        a_pac     = st.number_input("Monthly PAC (€)", 0, 10_000, int(p["monthly_pac"]), step=50, key="sc_a_pac")
        a_exp     = st.number_input("Monthly expenses (€)", 500, 20_000, int(monthly_expenses), step=100, key="sc_a_exp")
        a_etf     = st.number_input("ETF net return (%)", 0.0, 20.0, round(base_etf * 100, 2), step=0.1, key="sc_a_etf") / 100
        a_infl    = st.number_input("Inflation (%)", 0.0, 10.0, round(p["inflation"] * 100, 1), step=0.1, key="sc_a_infl") / 100
        a_ral     = st.number_input("Annual gross salary RAL (€)", 10_000, 500_000, int(p["ral"]), step=1_000, key="sc_a_ral")

    with scol2:
        st.markdown("**Scenario B** (Base)")
        b_name    = st.text_input("Name B", "Base scenario", key="sc_b_name")
        b_retire  = st.number_input("Retire age", p["current_age"] + 1, 70,
                        p["stop_working_age"], key="sc_b_retire")
        b_pac     = st.number_input("Monthly PAC (€)", 0, 10_000, int(p["monthly_pac"]), step=50, key="sc_b_pac")
        b_exp     = st.number_input("Monthly expenses (€)", 500, 20_000, int(monthly_expenses), step=100, key="sc_b_exp")
        b_etf     = st.number_input("ETF net return (%)", 0.0, 20.0, round(base_etf * 100, 2), step=0.1, key="sc_b_etf") / 100
        b_infl    = st.number_input("Inflation (%)", 0.0, 10.0, round(p["inflation"] * 100, 1), step=0.1, key="sc_b_infl") / 100
        b_ral     = st.number_input("Annual gross salary RAL (€)", 10_000, 500_000, int(p["ral"]), step=1_000, key="sc_b_ral")

    with scol3:
        st.markdown("**Scenario C**")
        c_name    = st.text_input("Name C", "Aggressive (retire early)", key="sc_c_name")
        c_retire  = st.number_input("Retire age", p["current_age"] + 1, 70,
                        max(p["current_age"] + 1, p["stop_working_age"] - 5), key="sc_c_retire")
        c_pac     = st.number_input("Monthly PAC (€)", 0, 10_000,
                        min(10_000, int(p["monthly_pac"]) + 200), step=50, key="sc_c_pac")
        c_exp     = st.number_input("Monthly expenses (€)", 500, 20_000, int(monthly_expenses), step=100, key="sc_c_exp")
        c_etf     = st.number_input("ETF net return (%)", 0.0, 20.0, round(base_etf * 100, 2), step=0.1, key="sc_c_etf") / 100
        c_infl    = st.number_input("Inflation (%)", 0.0, 10.0, round(p["inflation"] * 100, 1), step=0.1, key="sc_c_infl") / 100
        c_ral     = st.number_input("Annual gross salary RAL (€)", 10_000, 500_000, int(p["ral"]), step=1_000, key="sc_c_ral")

    scenarios = [
        (a_name, a_retire, a_pac, a_exp, a_etf, a_infl, a_ral),
        (b_name, b_retire, b_pac, b_exp, b_etf, b_infl, b_ral),
        (c_name, c_retire, c_pac, c_exp, c_etf, c_infl, c_ral),
    ]

    with st.spinner("Running 3 scenarios..."):
        results = []
        for name, retire_age, pac, sc_exp, sc_etf, sc_infl, sc_ral in scenarios:
            p_info = calculate_state_pension(
                ral=sc_ral, ral_growth=p["ral_growth"],
                inps_contribution_rate=p["inps_contribution_rate"],
                gdp_revaluation_rate=p["gdp_revaluation_rate"],
                current_age=p["current_age"], age_started_working=p["age_started_working"],
                stop_working_age=retire_age, part_time=p["part_time"],
                part_time_salary=p["part_time_salary"],
                part_time_until_age=p["part_time_until_age"],
                net_monthly_salary=float(net_monthly_salary),
                age_joined_fund=p["age_joined_fund"],
                part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
                early_pension_years=p.get("early_pension_years", 0),
                defer_to_71=p.get("defer_to_71", False),
                base_vecchiaia_age=p.get("vecchiaia_age", 67),
            )
            sc_base = {**_base,
                       "monthly_expenses": sc_exp,
                       "etf_net_return": sc_etf,
                       "inflation": sc_infl,
                       "ral": sc_ral}
            rs = run_your_scenario(
                monthly_pac=pac,
                stop_working_age=retire_age,
                state_pension_annual_net=p_info["net_annual_nominal"] if p_info["eligible"] else 0.0,
                pension_start_age=p_info["pension_age"],
                contribution_years=p_info["contribution_years"],
                **sc_base,
            )
            results.append({
                "name": name,
                "retire_age": retire_age,
                "pac": pac,
                "expenses": sc_exp,
                "etf": sc_etf,
                "inflation": sc_infl,
                "ral": sc_ral,
                "pension_age": p_info["pension_age"],
                "pension_net": p_info["net_annual_nominal"] if p_info["eligible"] else 0,
                "contribution_years": p_info["contribution_years"],
                "rows": rs["rows"],
                "solvent": rs["solvent_to_target"],
                "final_wealth": rs["assets_at_target_real"],
            })

    # Metrics comparison
    st.divider()
    st.subheader("Key Metrics")
    cols = st.columns(3)
    for i, (res, col) in enumerate(zip(results, cols)):
        with col:
            status = "✅ Solvent" if res["solvent"] else "❌ Broke"
            st.markdown(f"**{res['name']}**")
            st.metric("Retire age", res["retire_age"])
            st.metric("Monthly PAC", fmt_eur(res["pac"]))
            st.metric("Monthly expenses", fmt_eur(res["expenses"]))
            st.metric("ETF net return", fmt_pct(res["etf"]))
            st.metric("Inflation", fmt_pct(res["inflation"]))
            st.metric("RAL", fmt_eur(res["ral"]))
            st.metric("Status", status)
            st.metric(f"Real wealth at {p['target_age']}", fmt_eur(res["final_wealth"]))
            st.metric("State pension age", res["pension_age"])
            st.metric("State pension/year", fmt_eur(res["pension_net"]))

    # Wealth chart comparison — deterministic
    st.subheader("Wealth Evolution Comparison (deterministic)")
    colors_sc = ["#EF553B", "#636EFA", "#00CC96"]
    fig_cmp = go.Figure()
    for res, color in zip(results, colors_sc):
        ages_sc = [r["age"] for r in res["rows"]]
        totals_sc = [r["total_real"] for r in res["rows"]]
        fig_cmp.add_trace(go.Scatter(
            x=ages_sc, y=totals_sc,
            name=res["name"],
            line=dict(color=color, width=2),
        ))
    fig_cmp.add_hline(y=0, line_dash="dash", line_color="white")
    fig_cmp.update_layout(
        title="Real total wealth over time — 3 scenarios",
        xaxis_title="Age", yaxis_title="€ real",
        template="plotly_dark", hovermode="x unified", height=450,
    )
    st.plotly_chart(fig_cmp, use_container_width=True)

    # ── Monte Carlo comparison ────────────────────────────────────────────
    st.divider()
    st.subheader("🎲 Monte Carlo Comparison")
    st.caption(
        "Same random seed across all 3 scenarios (Common Random Numbers) — differences reflect "
        "parameters, not noise. Uses the MC settings from the sidebar."
    )
    run_mc_cmp = st.checkbox(
        "Run Monte Carlo for all 3 scenarios?",
        value=False,
        key="sc_run_mc",
        help="Runs N simulations per scenario (N from sidebar, capped at 500 for speed).",
    )

    if run_mc_cmp:
        _tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
        _total_ac = _tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]
        _n_sim = min(p["n_simulations"], 500)

        mc_colors = ["#EF553B", "#636EFA", "#00CC96"]
        mc_alphas = ["rgba(239,85,59,{a})", "rgba(99,110,250,{a})", "rgba(0,204,150,{a})"]

        mc_results_list = []
        with st.spinner(f"Running {_n_sim} × 3 MC scenarios (same seed = CRN)…"):
            for res in results:
                _mc = _cached_monte_carlo(
                    n_simulations=_n_sim,
                    current_age=p["current_age"], target_age=p["target_age"],
                    net_monthly_salary=float(net_monthly_salary),
                    monthly_expenses=res["expenses"],
                    age_started_working=p["age_started_working"],
                    etf_value=p["etf_value"], monthly_pac=res["pac"],
                    etf_net_return=res["etf"],
                    expected_gross_return=res["etf"] + p["ter"] + p["ivafe"],
                    etf_volatility=p["etf_volatility"],
                    ter=p["ter"], ivafe=p["ivafe"],
                    capital_gains_tax=p["capital_gains_tax"],
                    bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
                    emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
                    pension_fund_value=p["pf_value"],
                    total_annual_contribution=_total_ac,
                    voluntary_extra=p["voluntary_extra"],
                    pension_fund_return=p["fund_return"],
                    annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
                    stop_working_age=res["retire_age"],
                    part_time=p["part_time"], part_time_salary=p["part_time_salary"],
                    part_time_until_age=p["part_time_until_age"],
                    inflation=res["inflation"], inflation_std=p["inflation_std"],
                    state_pension_annual_net=res["pension_net"],
                    pension_start_age=res["pension_age"],
                    contribution_years=res["contribution_years"],
                    scenario=p["mc_scenario"],
                    seed=42,
                    part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
                    inps_employee_rate=p["inps_employee_rate"],
                    surcharges_rate=p["surcharges_rate"],
                    tfr_destination=p.get("tfr_destination", "fund"),
                    tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
                    tfr_company_value=p.get("tfr_company_value", 0.0),
                    couple_net_monthly=p.get("couple_net_monthly", 0.0),
                    couple_stop_working_age=p.get("couple_stop_working_age", 0),
                )
                mc_results_list.append(_mc)

        # Fan chart: P10–P90 band + P50 median per scenario
        fig_mc = go.Figure()
        for i, (res, mc_r) in enumerate(zip(results, mc_results_list)):
            _ages = mc_r["ages"]
            _pct  = mc_r["percentiles"]
            _col  = mc_colors[i]
            _alph = mc_alphas[i]

            # P10-P90 band
            fig_mc.add_trace(go.Scatter(
                x=_ages + _ages[::-1],
                y=_pct["p90"] + _pct["p10"][::-1],
                fill="toself",
                fillcolor=_alph.format(a=0.12),
                line=dict(color="rgba(0,0,0,0)"),
                name=f"{res['name']} P10–P90",
                showlegend=True,
            ))
            # P25-P75 band
            fig_mc.add_trace(go.Scatter(
                x=_ages + _ages[::-1],
                y=_pct["p75"] + _pct["p25"][::-1],
                fill="toself",
                fillcolor=_alph.format(a=0.25),
                line=dict(color="rgba(0,0,0,0)"),
                name=f"{res['name']} P25–P75",
                showlegend=True,
            ))
            # P50 median
            fig_mc.add_trace(go.Scatter(
                x=_ages, y=_pct["p50"],
                name=f"{res['name']} P50",
                line=dict(color=_col, width=2),
            ))

        fig_mc.add_hline(y=0, line_dash="dash", line_color="white")
        fig_mc.update_layout(
            title=f"Monte Carlo — real liquid wealth · {_n_sim} sims/scenario · same seed (CRN) · {p['mc_scenario']}",
            xaxis_title="Age", yaxis_title="€ real (liquid)",
            template="plotly_dark", hovermode="x unified", height=520,
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        # Summary table
        st.subheader("📋 Monte Carlo Summary Table")
        _summary_rows = []
        for res, mc_r in zip(results, mc_results_list):
            _pct = mc_r["percentiles"]
            _summary_rows.append({
                "Scenario": res["name"],
                "P(solvent)": f"{mc_r['probability_solvent'] * 100:.1f}%",
                "Avg ruin age": f"{mc_r['avg_broke_age']:.0f}" if mc_r["probability_solvent"] < 1.0 else "—",
                f"P10 wealth at {p['target_age']}": fmt_eur(_pct["p10"][-1]),
                f"P50 wealth at {p['target_age']}": fmt_eur(_pct["p50"][-1]),
                f"P90 wealth at {p['target_age']}": fmt_eur(_pct["p90"][-1]),
            })
        st.dataframe(pd.DataFrame(_summary_rows), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    st.title("🔥 FIRE Planning Tool — Italian Financial Independence Calculator")
    st.caption(
        "Models IRPEF 2025 (incl. Trattamento Integrativo), INPS contributory pension, "
        "supplementary pension fund, TFR, couple mode. "
        "All projections in real (inflation-adjusted) terms where noted."
    )

    p = sidebar_inputs()

    if "expenses" not in st.session_state:
        st.session_state.expenses = copy.deepcopy(DEFAULT_EXPENSES)

    tax_result = calculate_net_salary(
        p["ral"], p["company_benefits"], p["inps_employee_rate"], p["surcharges_rate"]
    )
    net_monthly_salary = tax_result["net_monthly_13"]
    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]

    # TFR to fund only if destination is "fund"
    tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
    total_annual_contribution = tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]

    pension_info = calculate_state_pension(
        ral=p["ral"], ral_growth=p["ral_growth"],
        inps_contribution_rate=p["inps_contribution_rate"],
        gdp_revaluation_rate=p["gdp_revaluation_rate"],
        current_age=p["current_age"], age_started_working=p["age_started_working"],
        stop_working_age=p["stop_working_age"],
        part_time=p["part_time"], part_time_salary=p["part_time_salary"],
        part_time_until_age=p["part_time_until_age"],
        net_monthly_salary=float(net_monthly_salary),
        age_joined_fund=p["age_joined_fund"],
        part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
        early_pension_years=p.get("early_pension_years", 0),
        defer_to_71=p.get("defer_to_71", False),
        base_vecchiaia_age=p.get("vecchiaia_age", 67),
    )

    monthly_expenses_val = compute_total_monthly(st.session_state.expenses)
    rows = run_projection(
        current_age=p["current_age"], target_age=p["target_age"],
        net_monthly_salary=float(net_monthly_salary),
        monthly_expenses=monthly_expenses_val,
        age_started_working=p["age_started_working"],
        etf_value=p["etf_value"], monthly_pac=p["monthly_pac"],
        etf_net_return=etf_net_return, capital_gains_tax=p["capital_gains_tax"],
        bank_balance=p["bank_balance"], bank_interest=p["bank_interest"],
        emergency_fund=p["emergency_fund"], stamp_duty=p["stamp_duty"],
        pension_fund_value=p["pf_value"],
        total_annual_contribution=total_annual_contribution,
        voluntary_extra=p["voluntary_extra"], pension_fund_return=p["fund_return"],
        annuity_rate=p["annuity_rate"], age_joined_fund=p["age_joined_fund"],
        stop_working_age=p["stop_working_age"],
        part_time=p["part_time"], part_time_salary=p["part_time_salary"],
        part_time_until_age=p["part_time_until_age"], inflation=p["inflation"],
        state_pension_annual_net=pension_info["net_annual_nominal"] if pension_info["eligible"] else 0.0,
        pension_start_age=pension_info["pension_age"],
        contribution_years=pension_info["contribution_years"],
        part_time_monthly_gross=p.get("part_time_monthly_gross", 0.0),
        inps_employee_rate=p["inps_employee_rate"],
        surcharges_rate=p["surcharges_rate"],
        tfr_destination=p.get("tfr_destination", "fund"),
        tfr_annual_accrual=p["ral"] / 13.5 if p.get("tfr_destination") == "company" else 0.0,
        tfr_company_value=p.get("tfr_company_value", 0.0),
        couple_net_monthly=p.get("couple_net_monthly", 0.0),
        couple_stop_working_age=p.get("couple_stop_working_age", 0),
    )

    tabs = st.tabs([
        "💸 Expenses", "💰 Salary", "📊 Projections", "🔥 FIRE",
        "🏛️ Pension & NPV", "📋 Dashboard",
        "🔬 Sensitivity", "📊 Scenari & MC",
    ])

    with tabs[0]:
        updated_expenses, monthly_expenses_val = tab_spese(st.session_state.expenses)
        st.session_state.expenses = updated_expenses

    with tabs[1]:
        tab_salary(p)

    with tabs[2]:
        tab_projections(p, float(net_monthly_salary), monthly_expenses_val, pension_info, rows)

    with tabs[3]:
        tab_fire_results(p, float(net_monthly_salary), monthly_expenses_val, pension_info, tax_result)

    with tabs[4]:
        tab_pension(p, float(net_monthly_salary), pension_info, tax_result)

    with tabs[5]:
        tab_dashboard(p, tax_result, monthly_expenses_val, pension_info, rows)

    with tabs[6]:
        tab_sensitivity(p, float(net_monthly_salary), monthly_expenses_val, pension_info)

    with tabs[7]:
        tab_scenarios_mc(p, float(net_monthly_salary), monthly_expenses_val, pension_info)


if __name__ == "__main__":
    main()
