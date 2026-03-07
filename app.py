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


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_etf_info(ticker: str) -> dict:
    try:
        import yfinance as yf
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_etf_history(ticker: str) -> "pd.DataFrame":
    try:
        import yfinance as yf
        return yf.Ticker(ticker).history(period="5y", interval="1mo")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_etf_funds_data(ticker: str) -> dict:
    result: dict = {"top_holdings": None, "sector_weightings": None, "asset_classes": None}
    try:
        import yfinance as yf
        fd = yf.Ticker(ticker).funds_data
        result["top_holdings"]      = fd.top_holdings
        result["sector_weightings"] = fd.sector_weightings
        result["asset_classes"]     = fd.asset_classes
    except Exception:
        pass
    return result


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

    _tbl_mode = "Real (today's €)" if display_real else "Nominal (future €)"
    st.subheader(f"Detailed Table — {_tbl_mode}")
    if display_real:
        display_cols = ["age", "bank_real", "etf_real", "pf_real", "total_real"]
        col_names    = ["Age", "Bank (€)", "ETF (€)", "Pension Fund (€)", "Total (€)"]
        if show_tfr:
            display_cols.insert(4, "tfr_real")
            col_names.insert(4, "TFR (€)")
    else:
        display_cols = ["age", "bank", "etf", "pf", "total_nominal"]
        col_names    = ["Age", "Bank (€)", "ETF (€)", "Pension Fund (€)", "Total (€)"]
        if show_tfr:
            display_cols.insert(4, "tfr_company")
            col_names.insert(4, "TFR (€)")

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
    st.subheader("🎯 FIRE Number")
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("FIRE Number", fmt_eur(fire_number),
               help=f"Annual expenses / SWR = {fmt_eur(annual_expenses)} / {fmt_pct(p['swr'])}")
    fc2.metric("Current liquid wealth", fmt_eur(current_liquid),
               help=f"ETF ({fmt_eur(p['etf_value'])}) + Bank ({fmt_eur(p['bank_balance'])}) − Emergency fund ({fmt_eur(p['emergency_fund'])})")
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
    eff_pac = scenario_result["effective_avg_monthly_pac"]
    display_real = st.session_state.get("display_real", True)
    _tgt_row = next((r for r in scenario_result["rows"] if r["age"] == p["target_age"]), {})
    assets_at_target = _tgt_row.get("total_real" if display_real else "total_nominal", 0.0)
    _wealth_label = f"{'Real' if display_real else 'Nominal'} wealth at {p['target_age']}"

    col1, col2, col3 = st.columns(3)
    col1.metric("Solvent to target age?", "✅ Yes" if solvent else "❌ No")
    col2.metric(_wealth_label, fmt_eur(assets_at_target))
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
    st.subheader(f"{'Real' if display_real else 'Nominal'} wealth at target age for different retirement ages")
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
            _sw_tgt = next((r for r in rs["rows"] if r["age"] == p["target_age"]), {})
            sweep_data.append({
                "Retirement age": test_age,
                "wealth_real": _sw_tgt.get("total_real", 0.0),
                "wealth_nominal": _sw_tgt.get("total_nominal", 0.0),
                "Solvent": rs["solvent_to_target"],
            })

    df_sweep = pd.DataFrame(sweep_data)
    _sw_col = "wealth_real" if display_real else "wealth_nominal"
    _sw_label = f"{'Real' if display_real else 'Nominal'} wealth at {p['target_age']} (€)"
    colors = ["#00CC96" if s else "#EF553B" for s in df_sweep["Solvent"]]
    fig_sweep = go.Figure(go.Bar(
        x=df_sweep["Retirement age"], y=df_sweep[_sw_col],
        marker_color=colors,
        text=[fmt_eur(v) for v in df_sweep[_sw_col]],
        textposition="outside",
    ))
    fig_sweep.add_hline(y=0, line_dash="dash", line_color="white")
    fig_sweep.update_layout(
        title=f"{'Real' if display_real else 'Nominal'} wealth at {p['target_age']} vs retirement age (green=solvent, red=broke)",
        xaxis_title="Retirement age", yaxis_title=_sw_label,
        template="plotly_dark", height=400,
    )
    st.plotly_chart(fig_sweep, use_container_width=True)


# ─────────────────────────────────────────────
# Tab 5: State Pension & Pension Fund
# ─────────────────────────────────────────────
def tab_pension(p, net_monthly_salary, pension_info, tax_result, rows):
    st.header("🏛️ State Pension (INPS) & Supplementary Pension Fund")

    # ── SECTION 1: INPS State Pension ────────────────────────────────────
    st.markdown("### 🏛️ INPS State Pension — Contributory Method")

    # Info banners
    early_yrs = p.get("early_pension_years", 0)
    if early_yrs > 0:
        st.info(f"Early pension enabled: threshold {early_yrs} contribution years")
    if p.get("defer_to_71"):
        st.info("Pension deferred to age 71 for maximum INPS coefficient")
    if p.get("le_adjustment") and not p.get("defer_to_71") and not p.get("early_pension_years"):
        _adj = p.get("vecchiaia_age", 67) - 67
        st.info(
            f"Life expectancy adjustment active: standard pension age shifted from 67 to "
            f"**{p.get('vecchiaia_age', 67)}** (+{_adj} yr). "
            f"Based on ISTAT +3 months per 2-year period (Riforma Fornero)."
        )

    if not pension_info["eligible"]:
        st.error("Not eligible for INPS state pension — insufficient contribution years (need ≥20)")
    else:
        st.success(f"Eligible for state pension at age **{pension_info['pension_age']}**")

        years_to_pension = pension_info["pension_age"] - p["current_age"]
        deflator = (1 + p["inflation"]) ** years_to_pension
        display_real = st.session_state.get("display_real", True)

        # Derived values
        gross_annual_nom   = pension_info["gross_annual"]
        net_annual_nom     = pension_info["net_annual_nominal"]
        gross_monthly_nom  = gross_annual_nom / 13
        net_monthly_nom    = pension_info["net_monthly_nominal"]
        gross_annual_real  = gross_annual_nom  / deflator
        net_annual_real    = net_annual_nom    / deflator
        gross_monthly_real = gross_annual_real / 13
        net_monthly_real   = net_annual_real   / 13

        if display_real:
            _g_ann, _n_ann = gross_annual_real, net_annual_real
            _g_mo,  _n_mo  = gross_monthly_real, net_monthly_real
            _mode_note = (
                f"Showing <b>real</b> values — today's purchasing power "
                f"(deflated {years_to_pension} yrs at {p['inflation']:.1%}/yr). "
                f"Nominal at pension age: gross {fmt_eur(gross_annual_nom)}/yr · "
                f"net {fmt_eur(net_annual_nom)}/yr."
            )
        else:
            _g_ann, _n_ann = gross_annual_nom, net_annual_nom
            _g_mo,  _n_mo  = gross_monthly_nom, net_monthly_nom
            _mode_note = (
                f"Showing <b>nominal</b> values — future money at pension age {pension_info['pension_age']}. "
                f"Real equivalent today: gross {fmt_eur(gross_annual_real)}/yr · "
                f"net {fmt_eur(net_annual_real)}/yr."
            )

        # Row 1: key facts
        k1, k2, k3 = st.columns(3)
        k1.metric("Pension age", f"{pension_info['pension_age']} yrs")
        k2.metric("Contribution years at retirement", pension_info["contribution_years"])
        k3.metric("Pension pot (montante)", fmt_eur(pension_info["montante"]),
                  help="Accumulated INPS virtual pot on which the coefficient is applied")

        st.markdown(
            f"<p style='color:#9ca3af;font-size:0.85rem'>{_mode_note}</p>",
            unsafe_allow_html=True,
        )

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Gross annual", fmt_eur(_g_ann))
        p2.metric("Net annual", fmt_eur(_n_ann))
        p3.metric("Gross monthly (÷13)", fmt_eur(_g_mo))
        p4.metric("Net monthly (÷13)", fmt_eur(_n_mo))

    # ── SECTION 2: Supplementary Pension Fund ────────────────────────────
    st.markdown("---")
    st.markdown("### 💼 Supplementary Pension Fund")
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
    st.caption("Current-year contributions — today's € (toggle has no effect here).")
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

    # ── Annuity payout at retirement ─────────────────────────────────────
    _stop = p["stop_working_age"]
    _pf_row = next((r for r in rows if r["age"] == _stop), None)
    if _pf_row is not None:
        _display_real = st.session_state.get("display_real", True)
        _pf_val_nom = _pf_row.get("pf", 0.0)
        _pf_val_real = _pf_row.get("pf_real", _pf_val_nom)
        _pf_val = _pf_val_real if _display_real else _pf_val_nom
        _mode_lbl = "real" if _display_real else "nominal"

        _gross_ann = _pf_val * p["annuity_rate"]
        _net_ann   = _gross_ann * (1 - pf_tax_age)
        _gross_mo  = _gross_ann / 12
        _net_mo    = _net_ann  / 12

        st.markdown(f"#### 💰 Estimated annuity (rendita) at retirement age {_stop} — {_mode_lbl} €")
        st.caption(
            f"Fund value at {_stop}: {fmt_eur(_pf_val)} × annuity rate {fmt_pct(p['annuity_rate'])} "
            f"× (1 − tax {fmt_pct(pf_tax_age)})"
        )
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Gross annual", fmt_eur(_gross_ann))
        a2.metric("Net annual",   fmt_eur(_net_ann))
        a3.metric("Gross monthly", fmt_eur(_gross_mo, 2))
        a4.metric("Net monthly",   fmt_eur(_net_mo,   2))

    st.markdown("---")
    st.markdown("### ⚖️ NPV Comparison: Pension Fund vs ETF")

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

    st.caption(
        f"NPVs are discounted at your inflation rate ({p['inflation']:.1%}/yr) → always in today's € "
        f"(toggle has no effect here)."
    )
    col_n1, col_n2, col_n3 = st.columns(3)
    col_n1.metric("NPV Pension Fund (today's €)", fmt_eur(npv_result["pension_fund_npv"], 2))
    col_n2.metric("NPV ETF (today's €)", fmt_eur(npv_result["etf_npv"], 2))
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
    total_income_monthly = float(net_mo)
    monthly_savings = total_income_monthly - monthly_expenses
    savings_rate = monthly_savings / total_income_monthly if total_income_monthly > 0 else 0.0
    fire_number = monthly_expenses * 12 / p["swr"]
    current_liquid = p["etf_value"] + p["bank_balance"] - p["emergency_fund"]

    _dash_real = st.session_state.get("display_real", True)
    if pension_info["eligible"]:
        _yrs_to_pen = pension_info["pension_age"] - p["current_age"]
        _pen_annual = (
            pension_info["net_annual_nominal"] / (1 + p["inflation"]) ** _yrs_to_pen
            if _dash_real else pension_info["net_annual_nominal"]
        )
        _pen_label = f"INPS pension / year ({'real' if _dash_real else 'nominal'})"
    else:
        _pen_annual = None
        _pen_label = "INPS pension / year"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Net monthly income", fmt_eur(total_income_monthly),
               help="Net monthly salary")
    c2.metric("Monthly expenses", fmt_eur(monthly_expenses, 2))
    c3.metric("Monthly savings", fmt_eur(monthly_savings))
    c4.metric("Savings rate", fmt_pct(savings_rate))
    c5.metric(_pen_label, fmt_eur(_pen_annual) if _pen_annual is not None else "N/A")

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
# Tab 8: Scenarios & Monte Carlo (unified)  — CLEAN REWRITE
# ─────────────────────────────────────────────
def tab_scenarios_mc(p, net_monthly_salary, monthly_expenses, pension_info):  # noqa: C901
    # ── Header ────────────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='margin-bottom:0'>📊 Scenarios &amp; Monte Carlo</h2>"
        "<p style='color:#9ca3af;margin-top:4px;font-size:0.9rem'>"
        f"Stochastic engine · <b>{p['mc_scenario']}</b> · {p['n_simulations']:,} simulations · "
        "base parameters from sidebar &nbsp;|&nbsp; below: three customisable scenarios</p>",
        unsafe_allow_html=True,
    )

    # ── Shared derived values ─────────────────────────────────────────────
    etf_net_return = p["expected_gross_return"] - p["ter"] - p["ivafe"]
    tfr_to_fund = p["tfr_contribution"] if p.get("tfr_destination", "fund") == "fund" else 0.0
    total_annual_contribution = tfr_to_fund + p["employer_contribution"] + p["personal_contribution"]

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1 — Monte Carlo (base parameters)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🎲 Monte Carlo Simulation — Base Parameters")

    with st.spinner(f"Running {p['n_simulations']:,} simulations…"):
        mc_base = _cached_monte_carlo(
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
        )

    pct = mc_base["percentiles"]
    ages_mc = mc_base["ages"]
    solvent_pct = mc_base["probability_solvent"] * 100
    solvent_color = "#00CC96" if solvent_pct >= 90 else ("#FFA500" if solvent_pct >= 70 else "#EF553B")

    # KPI strip
    kc1, kc2, kc3, kc4 = st.columns(4)
    kc1.metric("Solvency probability", f"{solvent_pct:.1f}%")
    kc2.metric("Avg age of ruin (if occurs)",
               f"{mc_base['avg_broke_age']:.1f}" if solvent_pct < 100 else "—")
    kc3.metric(f"P50 wealth at {p['target_age']}", fmt_eur(pct["p50"][-1]))
    kc4.metric(f"P10 wealth at {p['target_age']}", fmt_eur(pct["p10"][-1]))

    # Fan chart
    _BAND_BLUE = [
        ("p5",  "p95", "rgba(99,110,250,0.08)", "P5–P95"),
        ("p10", "p90", "rgba(99,110,250,0.15)", "P10–P90"),
        ("p25", "p75", "rgba(99,110,250,0.28)", "P25–P75"),
    ]
    fig_fan = go.Figure()
    for lo, hi, fill, label in _BAND_BLUE:
        fig_fan.add_trace(go.Scatter(
            x=ages_mc + ages_mc[::-1], y=pct[hi] + pct[lo][::-1],
            fill="toself", fillcolor=fill,
            line=dict(color="rgba(0,0,0,0)"), name=label, legendgroup="bands",
        ))
    fig_fan.add_trace(go.Scatter(
        x=ages_mc, y=pct["p50"], name="Median (P50)",
        line=dict(color="#818cf8", width=2.5),
        hovertemplate="Age %{x}<br>Median: %{y:,.0f} €<extra></extra>",
    ))
    fig_fan.add_hrect(y0=min(min(pct["p5"]), 0) * 1.1, y1=0,
                      fillcolor="rgba(239,68,68,0.06)", line_width=0)
    fig_fan.add_hline(y=0, line_dash="dot", line_color="rgba(239,68,68,0.7)",
                      annotation_text="Wealth = 0", annotation_position="bottom left",
                      annotation_font_color="rgba(239,68,68,0.85)",
                      annotation_font_size=11)
    fig_fan.add_vline(x=p["stop_working_age"], line_dash="dash",
                      line_color="rgba(251,191,36,0.7)",
                      annotation_text=f"Retirement · {p['stop_working_age']}",
                      annotation_position="top right",
                      annotation_font_color="rgba(251,191,36,0.9)",
                      annotation_font_size=11)
    fig_fan.update_layout(
        title=dict(text="Real Liquid Wealth Distribution (Bank + ETF)", font=dict(size=15)),
        xaxis=dict(title="Age", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(title="€ real", showgrid=True, gridcolor="rgba(255,255,255,0.06)",
                   tickformat=",.0f"),
        template="plotly_dark", hovermode="x unified", height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(t=80, b=50),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,25,1)",
    )
    st.plotly_chart(fig_fan, use_container_width=True)

    # Terminal wealth histogram + percentile table — side by side
    hcol, tcol = st.columns([1, 1])
    with hcol:
        st.markdown("**Terminal wealth distribution** *(age {})* ".format(p["target_age"]))
        fig_hist = go.Figure(go.Histogram(
            x=mc_base["terminal_wealth"], nbinsx=60,
            marker_color="#818cf8", opacity=0.85,
            hovertemplate="Wealth: %{x:,.0f} €<br>Count: %{y}<extra></extra>",
        ))
        fig_hist.add_vline(x=0, line_dash="dot", line_color="rgba(239,68,68,0.7)")
        _p10_val = pct["p10"][-1]
        _p90_val = pct["p90"][-1]
        for xval, label, col in [(_p10_val, "P10", "#fbbf24"), (_p90_val, "P90", "#34d399")]:
            fig_hist.add_vline(x=xval, line_dash="dash", line_color=col,
                               annotation_text=label, annotation_font_color=col)
        fig_hist.update_layout(
            template="plotly_dark", height=320, showlegend=False,
            xaxis=dict(title="Real wealth (€)", tickformat=",.0f",
                       showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title="Simulations", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
            margin=dict(t=20, b=50),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,25,1)",
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with tcol:
        st.markdown("**Wealth percentiles at key ages**")
        key_ages = sorted(set(a for a in [
            p["current_age"], p["stop_working_age"], 60,
            pension_info["pension_age"], p["target_age"]
        ] if p["current_age"] <= a <= p["target_age"]))
        pct_rows = [{
            "Age": ka,
            "P5":  fmt_eur(pct["p5"][ages_mc.index(ka)]),
            "P10": fmt_eur(pct["p10"][ages_mc.index(ka)]),
            "P25": fmt_eur(pct["p25"][ages_mc.index(ka)]),
            "P50": fmt_eur(pct["p50"][ages_mc.index(ka)]),
            "P75": fmt_eur(pct["p75"][ages_mc.index(ka)]),
            "P90": fmt_eur(pct["p90"][ages_mc.index(ka)]),
            "P95": fmt_eur(pct["p95"][ages_mc.index(ka)]),
        } for ka in key_ages if ka in ages_mc]
        if pct_rows:
            st.dataframe(pd.DataFrame(pct_rows), use_container_width=True, hide_index=True,
                         height=320)

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2 — Scenario Comparison
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📊 Scenario Comparison")
    st.markdown(
        "<p style='color:#9ca3af;font-size:0.87rem'>"
        "Configure three strategies below. All other parameters (taxes, TFR, etc.) "
        "are inherited from the sidebar.</p>",
        unsafe_allow_html=True,
    )

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
    )
    base_etf = etf_net_return
    _SC_COLORS  = ["#EF553B", "#636EFA", "#00CC96"]
    _SC_BADGES  = [
        "<span style='background:#EF553B22;color:#EF553B;padding:2px 8px;border-radius:4px;font-size:0.8rem'>A</span>",
        "<span style='background:#636EFA22;color:#636EFA;padding:2px 8px;border-radius:4px;font-size:0.8rem'>B</span>",
        "<span style='background:#00CC9622;color:#00CC96;padding:2px 8px;border-radius:4px;font-size:0.8rem'>C</span>",
    ]

    # Input grid — compact
    scol1, scol2, scol3 = st.columns(3)
    sc_inputs = []
    for col, badge, letter, def_retire, def_pac in zip(
        [scol1, scol2, scol3], _SC_BADGES,
        ["A", "B", "C"],
        [min(65, p["stop_working_age"] + 5), p["stop_working_age"],
         max(p["current_age"] + 1, p["stop_working_age"] - 5)],
        [int(p["monthly_pac"]), int(p["monthly_pac"]), min(10_000, int(p["monthly_pac"]) + 200)],
    ):
        with col:
            st.markdown(f"{badge}", unsafe_allow_html=True)
            k = f"smc_{letter.lower()}"
            _name   = st.text_input("Label", {
                "A": "Conservative — late retirement",
                "B": "Base scenario",
                "C": "Aggressive — early retirement",
            }[letter], key=f"{k}_name", label_visibility="collapsed")
            st.caption("Label")
            _retire = st.number_input("Retirement age", p["current_age"] + 1, 70,
                                       def_retire, key=f"{k}_retire")
            _pac    = st.number_input("Monthly PAC (€)", 0, 10_000, def_pac,
                                       step=50, key=f"{k}_pac")
            _exp    = st.number_input("Monthly expenses (€)", 500, 20_000,
                                       int(monthly_expenses), step=100, key=f"{k}_exp")
            _etf    = st.number_input("ETF net return (%)", 0.0, 20.0,
                                       round(base_etf * 100, 2), step=0.1,
                                       key=f"{k}_etf") / 100
            _infl   = st.number_input("Inflation (%)", 0.0, 10.0,
                                       round(p["inflation"] * 100, 1), step=0.1,
                                       key=f"{k}_infl") / 100
            _ral    = st.number_input("Gross salary RAL (€)", 10_000, 500_000,
                                       int(p["ral"]), step=1_000, key=f"{k}_ral")
            sc_inputs.append((_name, _retire, _pac, _exp, _etf, _infl, _ral))

    # Run deterministic
    with st.spinner("Computing 3 scenarios…"):
        sc_results = []
        for name, retire_age, pac, sc_exp, sc_etf, sc_infl, sc_ral in sc_inputs:
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
            rs = run_your_scenario(
                monthly_pac=pac, stop_working_age=retire_age,
                state_pension_annual_net=p_info["net_annual_nominal"] if p_info["eligible"] else 0.0,
                pension_start_age=p_info["pension_age"],
                contribution_years=p_info["contribution_years"],
                **{**_base, "monthly_expenses": sc_exp, "etf_net_return": sc_etf,
                   "inflation": sc_infl, "ral": sc_ral},
            )
            _sc_tgt = next((r for r in rs["rows"] if r["age"] == p["target_age"]), {})
            sc_results.append({
                "name": name, "retire_age": retire_age, "pac": pac,
                "expenses": sc_exp, "etf": sc_etf, "inflation": sc_infl, "ral": sc_ral,
                "pension_age": p_info["pension_age"],
                "pension_net": p_info["net_annual_nominal"] if p_info["eligible"] else 0,
                "contribution_years": p_info["contribution_years"],
                "rows": rs["rows"],
                "solvent": rs["solvent_to_target"],
                "final_wealth_real": _sc_tgt.get("total_real", 0.0),
                "final_wealth_nominal": _sc_tgt.get("total_nominal", 0.0),
            })

    # ── Parameter summary table ───────────────────────────────────────────
    _display_real = st.session_state.get("display_real", True)
    _wealth_key = "final_wealth_real" if _display_real else "final_wealth_nominal"
    _wealth_label = f"{'Real' if _display_real else 'Nominal'} wealth at {p['target_age']}"
    st.markdown("#### Parameters & Outcomes")
    param_rows = []
    _param_keys = [
        ("Retirement age", "retire_age", lambda v: str(v)),
        ("Monthly PAC", "pac", fmt_eur),
        ("Monthly expenses", "expenses", fmt_eur),
        ("ETF net return", "etf", fmt_pct),
        ("Inflation", "inflation", fmt_pct),
        ("Gross salary (RAL)", "ral", fmt_eur),
        ("State pension age", "pension_age", lambda v: str(v)),
        ("State pension / yr", "pension_net", fmt_eur),
        (_wealth_label, _wealth_key, fmt_eur),
        ("Status", "solvent", lambda v: "✅ Solvent" if v else "❌ Depleted"),
    ]
    for label, key, fmt_fn in _param_keys:
        row = {"Parameter": label}
        for res in sc_results:
            row[res["name"]] = fmt_fn(res[key])
        param_rows.append(row)
    st.dataframe(pd.DataFrame(param_rows), use_container_width=True, hide_index=True)

    # ── Wealth evolution chart ────────────────────────────────────────────
    _det_col = "total_real" if _display_real else "total_nominal"
    _det_ylabel = f"€ {'real' if _display_real else 'nominal'} (total wealth)"
    st.markdown(f"#### Wealth Evolution — Deterministic ({'Real' if _display_real else 'Nominal'})")
    fig_det = go.Figure()
    for res, color in zip(sc_results, _SC_COLORS):
        fig_det.add_trace(go.Scatter(
            x=[r["age"] for r in res["rows"]],
            y=[r[_det_col] for r in res["rows"]],
            name=res["name"],
            line=dict(color=color, width=2.5),
            hovertemplate=f"<b>{res['name']}</b><br>Age %{{x}}<br>%{{y:,.0f}} €<extra></extra>",
        ))
    fig_det.add_hline(y=0, line_dash="dot", line_color="rgba(239,68,68,0.6)")
    fig_det.update_layout(
        xaxis=dict(title="Age", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(title=_det_ylabel, showgrid=True,
                   gridcolor="rgba(255,255,255,0.06)", tickformat=",.0f"),
        template="plotly_dark", hovermode="x unified", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(t=60, b=50),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,25,1)",
    )
    st.plotly_chart(fig_det, use_container_width=True)

    # ── MC scenario comparison ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎲 Monte Carlo — Scenario Comparison")
    st.markdown(
        "<p style='color:#9ca3af;font-size:0.87rem'>"
        f"Common Random Numbers (seed=42) — differences reflect parameters, not noise. "
        f"Simulations per scenario: min({p['n_simulations']:,}, 500).</p>",
        unsafe_allow_html=True,
    )
    run_mc_cmp = st.checkbox(
        "Run Monte Carlo for all 3 scenarios",
        value=False, key="smc_run_mc",
        help="Runs stochastic simulations for each custom scenario using the same random seed.",
    )
    if run_mc_cmp:
        _n_sim = min(p["n_simulations"], 500)
        mc_sc_list = []
        with st.spinner(f"Running {_n_sim:,} × 3 scenarios…"):
            for res in sc_results:
                mc_sc_list.append(_cached_monte_carlo(
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
                ))

        # Summary KPIs per scenario
        sk_cols = st.columns(3)
        for res, mc_r, col, color in zip(sc_results, mc_sc_list, sk_cols, _SC_COLORS):
            with col:
                sp = mc_r["probability_solvent"] * 100
                sp_icon = "🟢" if sp >= 90 else ("🟡" if sp >= 70 else "🔴")
                ruin_str = "—" if sp >= 100 else f"{mc_r['avg_broke_age']:.0f}"
                st.markdown(
                    f"<div style='border-left:3px solid {color};padding-left:10px'>"
                    f"<b>{res['name']}</b><br>"
                    f"{sp_icon} Solvency: <b>{sp:.1f}%</b> &nbsp;|&nbsp; "
                    f"Avg ruin age: <b>{ruin_str}</b>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # Transposed percentile table: rows = percentiles, cols = scenarios
        st.markdown(f"#### Terminal wealth at age {p['target_age']} — full percentile distribution")
        _PCT_LABELS = [
            ("p5",  "P5  — Worst 5%"),
            ("p10", "P10 — Stress"),
            ("p25", "P25 — Bear"),
            ("p50", "P50 — Median"),
            ("p75", "P75 — Bull"),
            ("p90", "P90 — Strong"),
            ("p95", "P95 — Best 5%"),
        ]
        pct_cmp_rows = []
        for pkey, plabel in _PCT_LABELS:
            row = {"Percentile": plabel}
            for res, mc_r in zip(sc_results, mc_sc_list):
                row[res["name"]] = fmt_eur(mc_r["percentiles"][pkey][-1])
            pct_cmp_rows.append(row)
        # Append solvency row
        sol_row = {"Percentile": "P(Solvency)"}
        for res, mc_r in zip(sc_results, mc_sc_list):
            sol_row[res["name"]] = f"{mc_r['probability_solvent'] * 100:.1f}%"
        pct_cmp_rows.insert(0, sol_row)
        st.dataframe(pd.DataFrame(pct_cmp_rows), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# Tab 9: ETF Explorer
# ─────────────────────────────────────────────
def tab_etf():
    from modules.etf_data import (
        search_etfs, build_display_df,
        get_asset_classes, get_issuers, get_domiciles,
    )

    st.header("📈 ETF Explorer")
    st.caption(
        "Curated catalogue of EU-listed ETFs popular among Italian FIRE investors. "
        "Select any ETF to fetch live NAV, AUM, yield, holdings and allocation via yfinance."
    )

    # ── Search & Filter ───────────────────────────────────────────────────
    st.markdown("### 🔍 Search & Filter")
    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    with f1:
        query = st.text_input(
            "Search by name, ISIN, ticker, benchmark…",
            placeholder="e.g. VWCE, IE00BK5BQT80, MSCI World",
            key="etf_query",
        )
    with f2:
        selected_ac = st.multiselect("Asset class", get_asset_classes(), key="etf_ac")
    with f3:
        selected_issuers = st.multiselect("Issuer / Provider", get_issuers(), key="etf_issuer")
    with f4:
        selected_domiciles = st.multiselect("Domicile", get_domiciles(), key="etf_domicile")

    dist_filter = st.radio(
        "Distribution policy", ["All", "Accumulating", "Distributing"],
        index=0, horizontal=True, key="etf_dist",
    )
    dist_policies = None if dist_filter == "All" else [dist_filter]

    matching = search_etfs(
        query=query,
        asset_classes=selected_ac or None,
        issuers=selected_issuers or None,
        domiciles=selected_domiciles or None,
        dist_policies=dist_policies,
    )
    st.caption(f"{len(matching)} ETF{'s' if len(matching) != 1 else ''} found")

    if not matching:
        st.info("No ETFs match the current filters.")
        return

    # ── Results table ─────────────────────────────────────────────────────
    st.markdown("### 📋 Results")
    st.dataframe(build_display_df(matching), use_container_width=True, hide_index=True)

    # ── ETF detail selector ───────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔎 Detailed View — Live Data")

    etf_labels = [f"{e['ticker']}  ·  {e['name']}" for e in matching]
    selected_label = st.selectbox("Select an ETF", etf_labels, index=0, key="etf_detail")
    etf = matching[etf_labels.index(selected_label)]
    ticker_str = etf["ticker"]

    # Static metadata strip
    sm1, sm2, sm3, sm4, sm5 = st.columns(5)
    sm1.metric("TER", f"{etf['ter'] * 100:.2f}%")
    sm2.metric("Asset Class", etf["asset_class"])
    sm3.metric("Issuer", etf["issuer"])
    sm4.metric("Domicile", etf["domicile"])
    sm5.metric("Policy", etf["dist_policy"])
    st.caption(f"Benchmark: {etf['benchmark']}  ·  ISIN: {etf['isin']}")

    # ── Live data fetch ───────────────────────────────────────────────────
    st.markdown("#### Live data (yfinance · cached 1 h)")
    with st.spinner(f"Fetching {ticker_str}…"):
        info       = _cached_etf_info(ticker_str)
        history_df = _cached_etf_history(ticker_str)
        funds      = _cached_etf_funds_data(ticker_str)

    if not info:
        st.warning(
            f"yfinance returned no data for **{ticker_str}**. "
            "EU-listed tickers may occasionally time out — try again or check the ISIN on the issuer's site."
        )
    else:
        aum        = info.get("totalAssets")
        nav        = info.get("navPrice") or info.get("previousClose")
        etf_yield  = info.get("yield")
        ytd_return = info.get("ytdReturn")
        live_ter   = info.get("annualReportExpenseRatio")
        currency   = info.get("currency", "")
        wk52_hi    = info.get("fiftyTwoWeekHigh")
        wk52_lo    = info.get("fiftyTwoWeekLow")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("AUM", f"${aum / 1e9:.2f} B" if aum else "N/A",
                  help="Total assets under management in USD (Yahoo Finance)")
        k2.metric("NAV / Price", f"{nav:.4f} {currency}" if nav else "N/A")
        k3.metric("12-month Yield", f"{etf_yield * 100:.2f}%" if etf_yield else "N/A")
        k4.metric("YTD Return", f"{ytd_return * 100:.2f}%" if ytd_return else "N/A")

        if wk52_hi and wk52_lo:
            w1, w2 = st.columns(2)
            w1.metric("52-week High", f"{wk52_hi:.2f} {currency}")
            w2.metric("52-week Low",  f"{wk52_lo:.2f} {currency}")

        if live_ter is not None:
            delta = live_ter - etf["ter"]
            st.caption(
                f"Live TER (yfinance): {live_ter * 100:.2f}% — "
                f"{'matches catalogue' if abs(delta) < 0.0001 else f'differs {delta * 100:+.2f}% from catalogue'}"
            )

    # ── 5-year price history ──────────────────────────────────────────────
    st.markdown("#### 📈 5-Year Monthly Price History")
    if not history_df.empty and "Close" in history_df.columns:
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Scatter(
            x=history_df.index, y=history_df["Close"],
            name="Monthly Close",
            line=dict(color="#636EFA", width=2),
            hovertemplate="%{x|%b %Y}<br>%{y:.4f}<extra></extra>",
        ))
        fig_hist.update_layout(
            title=f"{ticker_str} — 5-Year Monthly Close",
            xaxis_title="Date",
            yaxis_title=f"Price ({info.get('currency', '') if info else ''})",
            template="plotly_dark", height=350, hovermode="x unified",
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Price history unavailable for this ticker.")

    # ── Holdings & Allocation ─────────────────────────────────────────────
    st.markdown("#### 🧩 Holdings & Allocation")
    st.caption(
        "Holdings data sourced from yfinance. Not all EU ETFs expose full holdings — "
        "refer to the issuer's website for authoritative data."
    )

    h_col, c_col = st.columns(2)

    with h_col:
        top = funds.get("top_holdings")
        if top is not None and not top.empty:
            st.markdown("**Top Holdings**")
            h_df = top.copy()
            rename = {}
            if "holdingName"    in h_df.columns: rename["holdingName"]    = "Holding"
            if "symbol"         in h_df.columns: rename["symbol"]         = "Symbol"
            if "holdingPercent" in h_df.columns:
                rename["holdingPercent"] = "Weight %"
                h_df["holdingPercent"] = (h_df["holdingPercent"] * 100).round(2)
            h_df = h_df.rename(columns=rename)
            st.dataframe(h_df[[v for v in rename.values() if v in h_df.columns]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Top holdings not available for this ETF.")

    with c_col:
        view = st.radio(
            "Allocation view", ["Sector weights", "Asset allocation"],
            horizontal=True, key="etf_alloc_view",
        )
        sector_data = funds.get("sector_weightings")
        asset_data  = funds.get("asset_classes")

        if view == "Sector weights" and sector_data:
            try:
                if isinstance(sector_data, list):
                    pairs = [(d.get("type", "?"), d.get("recentTW", 0) * 100) for d in sector_data]
                elif isinstance(sector_data, dict):
                    pairs = [(k, v * 100) for k, v in sector_data.items()]
                else:
                    raise ValueError
                pairs = [(l, v) for l, v in pairs if v > 0.01]
                if pairs:
                    labels, values = zip(*pairs)
                    fig_pie = go.Figure(go.Pie(
                        labels=list(labels), values=list(values),
                        hole=0.40, textinfo="label+percent",
                        hovertemplate="%{label}<br>%{value:.2f}%<extra></extra>",
                    ))
                    fig_pie.update_layout(
                        title="Sector Allocation", template="plotly_dark", height=380,
                        legend=dict(orientation="v", x=1.0, y=0.5),
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No non-zero sector weights available.")
            except Exception:
                st.info("Sector weights could not be parsed.")

        elif view == "Asset allocation" and asset_data:
            try:
                label_map = {
                    "cashPosition":       "Cash",
                    "stockPosition":      "Equity",
                    "bondPosition":       "Bonds",
                    "otherPosition":      "Other",
                    "preferredPosition":  "Preferred",
                    "convertiblePosition":"Convertible",
                }
                raw = asset_data if isinstance(asset_data, dict) else (
                    asset_data.to_dict() if hasattr(asset_data, "to_dict") else {}
                )
                labels = [lbl for k, lbl in label_map.items() if (raw.get(k) or 0) > 0.0001]
                values = [raw.get(k, 0) * 100 for k, lbl in label_map.items()
                          if (raw.get(k) or 0) > 0.0001]
                if labels:
                    fig_bar = go.Figure(go.Bar(
                        x=labels, y=values,
                        marker_color=["#636EFA","#FFA15A","#00CC96","#AB63FA","#EF553B","#19D3F3"][:len(labels)],
                        text=[f"{v:.1f}%" for v in values], textposition="outside",
                    ))
                    fig_bar.update_layout(
                        title="Asset Allocation", yaxis_title="Weight (%)",
                        template="plotly_dark", height=350, showlegend=False,
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Asset allocation not available.")
            except Exception:
                st.info("Asset allocation could not be parsed.")
        else:
            st.info("Allocation data not available for this ETF via yfinance.")

    # ── Use TER in FIRE model ─────────────────────────────────────────────
    st.divider()
    st.markdown("#### 🔥 Use This ETF's TER in Your FIRE Model")
    st.info(
        f"This ETF has **TER {etf['ter'] * 100:.2f}%**. "
        f"Update the *Annual TER (%)* field in the sidebar ← to use it in all projections."
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    st.title("🔥 FIRE Planning Tool — Italian Financial Independence Calculator")
    st.caption(
        "Models IRPEF 2025 (incl. Trattamento Integrativo), INPS contributory pension, "
        "supplementary pension fund, TFR. "
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
    )

    tabs = st.tabs([
        "💸 Expenses", "💰 Salary", "📊 Projections", "🔥 FIRE",
        "🏛️ Pension & NPV", "📋 Dashboard",
        "🔬 Sensitivity", "📊 Scenarios & MC", "📈 ETF Explorer",
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
        tab_pension(p, float(net_monthly_salary), pension_info, tax_result, rows)

    with tabs[5]:
        tab_dashboard(p, tax_result, monthly_expenses_val, pension_info, rows)

    with tabs[6]:
        tab_sensitivity(p, float(net_monthly_salary), monthly_expenses_val, pension_info)

    with tabs[7]:
        tab_scenarios_mc(p, float(net_monthly_salary), monthly_expenses_val, pension_info)

    with tabs[8]:
        tab_etf()


if __name__ == "__main__":
    main()
