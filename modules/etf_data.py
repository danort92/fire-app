"""
ETF catalogue for the FIRE Planning Tool.

Curated list of ~48 EU-listed ETFs popular among Italian FIRE investors.
Covers: World equity, EM, Europe, US, factors, bonds (global/EUR/corporate),
inflation-linked, multi-asset LifeStrategy-style.

Static data only. Live data is fetched in app.py via yfinance + st.cache_data.
"""
from __future__ import annotations
from typing import Any

# ─────────────────────────────────────────────
# Master catalogue
# ter stored as float fraction (0.0020 = 0.20%)
# ─────────────────────────────────────────────
ETF_CATALOGUE: list[dict[str, Any]] = [
    # ── World Equity ─────────────────────────────────────────────────────────
    {
        "isin": "IE00B4L5Y983", "ticker": "IWDA.AS",
        "name": "iShares Core MSCI World UCITS ETF USD Acc",
        "ter": 0.0020, "asset_class": "Equity", "sub_category": "World Developed",
        "issuer": "BlackRock", "benchmark": "MSCI World", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00B3RBWM25", "ticker": "VWRL.AS",
        "name": "Vanguard FTSE All-World UCITS ETF USD Dist",
        "ter": 0.0022, "asset_class": "Equity", "sub_category": "World All-Cap",
        "issuer": "Vanguard", "benchmark": "FTSE All-World", "domicile": "Ireland",
        "dist_policy": "Distributing",
    },
    {
        "isin": "IE00BK5BQT80", "ticker": "VWCE.DE",
        "name": "Vanguard FTSE All-World UCITS ETF USD Acc",
        "ter": 0.0022, "asset_class": "Equity", "sub_category": "World All-Cap",
        "issuer": "Vanguard", "benchmark": "FTSE All-World", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "LU0274208692", "ticker": "XDWD.DE",
        "name": "Xtrackers MSCI World Swap UCITS ETF 1C",
        "ter": 0.0019, "asset_class": "Equity", "sub_category": "World Developed",
        "issuer": "DWS", "benchmark": "MSCI World", "domicile": "Luxembourg",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00B52MJY50", "ticker": "SWDA.MI",
        "name": "iShares Core MSCI World UCITS ETF USD Acc (MI)",
        "ter": 0.0020, "asset_class": "Equity", "sub_category": "World Developed",
        "issuer": "BlackRock", "benchmark": "MSCI World", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00B3YLTY66", "ticker": "IMAE.MI",
        "name": "iShares MSCI World EUR Hedged UCITS ETF",
        "ter": 0.0055, "asset_class": "Equity", "sub_category": "World Dev. (EUR Hedged)",
        "issuer": "BlackRock", "benchmark": "MSCI World EUR Hedged", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    # ── Emerging Markets ─────────────────────────────────────────────────────
    {
        "isin": "IE00B4L5YC18", "ticker": "EIMI.AS",
        "name": "iShares Core MSCI EM IMI UCITS ETF USD Acc",
        "ter": 0.0018, "asset_class": "Equity", "sub_category": "Emerging Markets",
        "issuer": "BlackRock", "benchmark": "MSCI EM IMI", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "LU0635178014", "ticker": "XMEM.DE",
        "name": "Xtrackers MSCI Emerging Markets Swap UCITS ETF 1C",
        "ter": 0.0020, "asset_class": "Equity", "sub_category": "Emerging Markets",
        "issuer": "DWS", "benchmark": "MSCI Emerging Markets", "domicile": "Luxembourg",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00B3F81G20", "ticker": "VFEM.AS",
        "name": "Vanguard FTSE Emerging Markets UCITS ETF USD Dist",
        "ter": 0.0022, "asset_class": "Equity", "sub_category": "Emerging Markets",
        "issuer": "Vanguard", "benchmark": "FTSE Emerging", "domicile": "Ireland",
        "dist_policy": "Distributing",
    },
    {
        "isin": "IE00BKM4GZ66", "ticker": "IS3N.DE",
        "name": "iShares Core MSCI EM IMI UCITS ETF USD Acc (Xetra)",
        "ter": 0.0018, "asset_class": "Equity", "sub_category": "Emerging Markets",
        "issuer": "BlackRock", "benchmark": "MSCI EM IMI", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "LU2009202107", "ticker": "XMAW.DE",
        "name": "Xtrackers MSCI AC World Swap UCITS ETF 1C",
        "ter": 0.0025, "asset_class": "Equity", "sub_category": "World All-Cap (AC)",
        "issuer": "DWS", "benchmark": "MSCI ACWI", "domicile": "Luxembourg",
        "dist_policy": "Accumulating",
    },
    # ── Europe ────────────────────────────────────────────────────────────────
    {
        "isin": "IE00B4K48X80", "ticker": "IEUA.AS",
        "name": "iShares Core MSCI Europe UCITS ETF EUR Dist",
        "ter": 0.0012, "asset_class": "Equity", "sub_category": "Europe",
        "issuer": "BlackRock", "benchmark": "MSCI Europe", "domicile": "Ireland",
        "dist_policy": "Distributing",
    },
    {
        "isin": "LU0908500753", "ticker": "XESE.DE",
        "name": "Xtrackers Euro Stoxx 50 UCITS ETF 1D",
        "ter": 0.0009, "asset_class": "Equity", "sub_category": "Eurozone Large-Cap",
        "issuer": "DWS", "benchmark": "Euro Stoxx 50", "domicile": "Luxembourg",
        "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B60SX394", "ticker": "VEUR.AS",
        "name": "Vanguard FTSE Developed Europe UCITS ETF EUR Dist",
        "ter": 0.0010, "asset_class": "Equity", "sub_category": "Europe Developed",
        "issuer": "Vanguard", "benchmark": "FTSE Dev. Europe", "domicile": "Ireland",
        "dist_policy": "Distributing",
    },
    {
        "isin": "FR0010296061", "ticker": "CU2.PA",
        "name": "Amundi MSCI Europe UCITS ETF Dist",
        "ter": 0.0015, "asset_class": "Equity", "sub_category": "Europe",
        "issuer": "Amundi", "benchmark": "MSCI Europe", "domicile": "France",
        "dist_policy": "Distributing",
    },
    # ── US / North America ────────────────────────────────────────────────────
    {
        "isin": "IE00B52SFT06", "ticker": "CSPX.AS",
        "name": "iShares Core S&P 500 UCITS ETF USD Acc",
        "ter": 0.0007, "asset_class": "Equity", "sub_category": "US Large-Cap",
        "issuer": "BlackRock", "benchmark": "S&P 500", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "LU0490618542", "ticker": "XSPY.DE",
        "name": "Xtrackers S&P 500 Swap UCITS ETF 1C",
        "ter": 0.0015, "asset_class": "Equity", "sub_category": "US Large-Cap",
        "issuer": "DWS", "benchmark": "S&P 500", "domicile": "Luxembourg",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BFMXXD54", "ticker": "VUSA.AS",
        "name": "Vanguard S&P 500 UCITS ETF USD Dist",
        "ter": 0.0007, "asset_class": "Equity", "sub_category": "US Large-Cap",
        "issuer": "Vanguard", "benchmark": "S&P 500", "domicile": "Ireland",
        "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B3XXRP09", "ticker": "XNAS.DE",
        "name": "Xtrackers NASDAQ-100 UCITS ETF 1C",
        "ter": 0.0020, "asset_class": "Equity", "sub_category": "US Tech / NASDAQ",
        "issuer": "DWS", "benchmark": "NASDAQ-100", "domicile": "Luxembourg",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BMTX1Y45", "ticker": "EQQQ.DE",
        "name": "Invesco EQQQ NASDAQ-100 UCITS ETF",
        "ter": 0.0030, "asset_class": "Equity", "sub_category": "US Tech / NASDAQ",
        "issuer": "Invesco", "benchmark": "NASDAQ-100", "domicile": "Ireland",
        "dist_policy": "Distributing",
    },
    # ── Factor / Smart Beta ───────────────────────────────────────────────────
    {
        "isin": "IE00B42W4L06", "ticker": "IWSZ.AS",
        "name": "iShares Edge MSCI World Size Factor UCITS ETF",
        "ter": 0.0030, "asset_class": "Equity", "sub_category": "Factor — Size",
        "issuer": "BlackRock", "benchmark": "MSCI World Size", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BD45KH83", "ticker": "WSML.AS",
        "name": "iShares MSCI World Small Cap UCITS ETF",
        "ter": 0.0035, "asset_class": "Equity", "sub_category": "World Small-Cap",
        "issuer": "BlackRock", "benchmark": "MSCI World Small Cap", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BL25JM42", "ticker": "IQQW.DE",
        "name": "iShares Edge MSCI World Momentum Factor UCITS ETF",
        "ter": 0.0030, "asset_class": "Equity", "sub_category": "Factor — Momentum",
        "issuer": "BlackRock", "benchmark": "MSCI World Momentum", "domicile": "Ireland",
        "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BDBRDM35", "ticker": "ZPRV.DE",
        "name": "SPDR MSCI USA Small Cap Value Weighted UCITS ETF",
        "ter": 0.0030, "asset_class": "Equity", "sub_category": "US Small Value",
        "issuer": "State Street", "benchmark": "MSCI USA Small Cap Value Weighted",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00BSPLC298", "ticker": "ZPRX.DE",
        "name": "SPDR MSCI Europe Small Cap Value Weighted UCITS ETF",
        "ter": 0.0030, "asset_class": "Equity", "sub_category": "Europe Small Value",
        "issuer": "State Street", "benchmark": "MSCI Europe Small Cap Value Weighted",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    # ── Global Bonds ──────────────────────────────────────────────────────────
    {
        "isin": "IE00B14X4T88", "ticker": "AGGG.AS",
        "name": "iShares Core Global Aggregate Bond UCITS ETF USD Hedged Dist",
        "ter": 0.0010, "asset_class": "Bond", "sub_category": "Global Agg. (USD Hedged)",
        "issuer": "BlackRock", "benchmark": "Bloomberg Global Aggregate",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B9M2GW15", "ticker": "AGGH.MI",
        "name": "iShares Core Global Aggregate Bond UCITS ETF EUR Hedged Dist",
        "ter": 0.0010, "asset_class": "Bond", "sub_category": "Global Agg. (EUR Hedged)",
        "issuer": "BlackRock", "benchmark": "Bloomberg Global Agg. EUR Hedged",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "LU0378818131", "ticker": "DBZB.DE",
        "name": "Xtrackers Global Sovereign UCITS ETF 1D",
        "ter": 0.0025, "asset_class": "Bond", "sub_category": "Global Government",
        "issuer": "DWS", "benchmark": "FTSE World Govt Bond", "domicile": "Luxembourg",
        "dist_policy": "Distributing",
    },
    {
        "isin": "IE00BH04GL39", "ticker": "VAGF.AS",
        "name": "Vanguard Global Aggregate Bond UCITS ETF EUR Hedged Acc",
        "ter": 0.0010, "asset_class": "Bond", "sub_category": "Global Agg. (EUR Hedged)",
        "issuer": "Vanguard", "benchmark": "Bloomberg Global Agg. EUR Hedged",
        "domicile": "Ireland", "dist_policy": "Accumulating",
    },
    # ── Euro / European Bonds ─────────────────────────────────────────────────
    {
        "isin": "IE00B3F81R35", "ticker": "VGEA.AS",
        "name": "Vanguard Eurozone Government Bond UCITS ETF EUR Dist",
        "ter": 0.0007, "asset_class": "Bond", "sub_category": "Eurozone Govt",
        "issuer": "Vanguard", "benchmark": "Bloomberg Euro Agg. Govt",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B4WXJJ64", "ticker": "IEAG.AS",
        "name": "iShares Core Euro Government Bond UCITS ETF",
        "ter": 0.0009, "asset_class": "Bond", "sub_category": "Eurozone Govt",
        "issuer": "BlackRock", "benchmark": "Bloomberg Euro Govt All Maturity",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "LU0290358497", "ticker": "XGLE.DE",
        "name": "Xtrackers II Eurozone Government Bond UCITS ETF 1D",
        "ter": 0.0015, "asset_class": "Bond", "sub_category": "Eurozone Govt",
        "issuer": "DWS", "benchmark": "iBoxx EUR Sovereigns Eurozone",
        "domicile": "Luxembourg", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B00FV128", "ticker": "IBCI.AS",
        "name": "iShares EUR Inflation Linked Govt Bond UCITS ETF",
        "ter": 0.0009, "asset_class": "Bond", "sub_category": "Eurozone Inflation-Linked",
        "issuer": "BlackRock", "benchmark": "Bloomberg EUR Govt Inflation-Linked",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    # ── Corporate Bonds ───────────────────────────────────────────────────────
    {
        "isin": "IE00B3F81409", "ticker": "IEAC.AS",
        "name": "iShares Core EUR Corporate Bond UCITS ETF EUR Dist",
        "ter": 0.0020, "asset_class": "Bond", "sub_category": "EUR Corporate IG",
        "issuer": "BlackRock", "benchmark": "Bloomberg Euro Corp",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00BH04DY62", "ticker": "VCPA.AS",
        "name": "Vanguard EUR Corporate Bond UCITS ETF EUR Dist",
        "ter": 0.0009, "asset_class": "Bond", "sub_category": "EUR Corporate IG",
        "issuer": "Vanguard", "benchmark": "Bloomberg Euro Corp",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B4L60045", "ticker": "SHYG.MI",
        "name": "iShares EUR High Yield Corp Bond UCITS ETF EUR Dist",
        "ter": 0.0050, "asset_class": "Bond", "sub_category": "EUR High Yield",
        "issuer": "BlackRock", "benchmark": "Markit iBoxx EUR High Yield",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    # ── Multi-Asset / LifeStrategy ────────────────────────────────────────────
    {
        "isin": "IE00BMVB5R75", "ticker": "V20A.DE",
        "name": "Vanguard LifeStrategy 20% Equity UCITS ETF Acc",
        "ter": 0.0025, "asset_class": "Multi-Asset", "sub_category": "20/80 Equity/Bond",
        "issuer": "Vanguard", "benchmark": "Composite (20% FTSE All-World / 80% Global Agg.)",
        "domicile": "Ireland", "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BMVB5P51", "ticker": "V40A.DE",
        "name": "Vanguard LifeStrategy 40% Equity UCITS ETF Acc",
        "ter": 0.0025, "asset_class": "Multi-Asset", "sub_category": "40/60 Equity/Bond",
        "issuer": "Vanguard", "benchmark": "Composite (40/60)",
        "domicile": "Ireland", "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BMVB5Q68", "ticker": "V60A.DE",
        "name": "Vanguard LifeStrategy 60% Equity UCITS ETF Acc",
        "ter": 0.0025, "asset_class": "Multi-Asset", "sub_category": "60/40 Equity/Bond",
        "issuer": "Vanguard", "benchmark": "Composite (60/40)",
        "domicile": "Ireland", "dist_policy": "Accumulating",
    },
    {
        "isin": "IE00BMVB5S82", "ticker": "V80A.DE",
        "name": "Vanguard LifeStrategy 80% Equity UCITS ETF Acc",
        "ter": 0.0025, "asset_class": "Multi-Asset", "sub_category": "80/20 Equity/Bond",
        "issuer": "Vanguard", "benchmark": "Composite (80/20)",
        "domicile": "Ireland", "dist_policy": "Accumulating",
    },
    # ── Sector / Thematic ─────────────────────────────────────────────────────
    {
        "isin": "IE00B3WJKG14", "ticker": "INRG.AS",
        "name": "iShares Global Clean Energy UCITS ETF USD Dist",
        "ter": 0.0065, "asset_class": "Equity", "sub_category": "Sector — Clean Energy",
        "issuer": "BlackRock", "benchmark": "S&P Global Clean Energy",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B2NPKV68", "ticker": "IWRD.AS",
        "name": "iShares MSCI World UCITS ETF USD Dist",
        "ter": 0.0050, "asset_class": "Equity", "sub_category": "World Developed (Dist)",
        "issuer": "BlackRock", "benchmark": "MSCI World",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
    {
        "isin": "IE00B4L5YB33", "ticker": "IQQH.DE",
        "name": "iShares Global Water UCITS ETF USD Dist",
        "ter": 0.0065, "asset_class": "Equity", "sub_category": "Sector — Water",
        "issuer": "BlackRock", "benchmark": "S&P Global Water",
        "domicile": "Ireland", "dist_policy": "Distributing",
    },
]


# ─────────────────────────────────────────────
# Pure helper functions — no Streamlit, no yfinance
# ─────────────────────────────────────────────

def get_asset_classes() -> list[str]:
    return sorted({e["asset_class"] for e in ETF_CATALOGUE})


def get_issuers() -> list[str]:
    return sorted({e["issuer"] for e in ETF_CATALOGUE})


def get_domiciles() -> list[str]:
    return sorted({e["domicile"] for e in ETF_CATALOGUE})


def search_etfs(
    query: str = "",
    asset_classes: list[str] | None = None,
    issuers: list[str] | None = None,
    domiciles: list[str] | None = None,
    dist_policies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Filter catalogue by free-text query and optional dimension filters.
    Query matches name, ISIN, ticker, sub_category, benchmark (case-insensitive).
    Filters are OR-within-dimension, AND-across-dimensions.
    """
    results = ETF_CATALOGUE

    if query:
        q = query.strip().lower()
        results = [
            e for e in results
            if q in e["isin"].lower()
            or q in e["ticker"].lower()
            or q in e["name"].lower()
            or q in e["sub_category"].lower()
            or q in e["benchmark"].lower()
        ]

    if asset_classes:
        results = [e for e in results if e["asset_class"] in asset_classes]
    if issuers:
        results = [e for e in results if e["issuer"] in issuers]
    if domiciles:
        results = [e for e in results if e["domicile"] in domiciles]
    if dist_policies:
        results = [e for e in results if e["dist_policy"] in dist_policies]

    return results


def build_display_df(etfs: list[dict[str, Any]]) -> "pd.DataFrame":
    """Convert ETF list to a pandas DataFrame ready for st.dataframe."""
    import pandas as pd
    rows = [
        {
            "ISIN":        e["isin"],
            "Ticker":      e["ticker"],
            "Name":        e["name"],
            "TER":         f"{e['ter'] * 100:.2f}%",
            "Asset Class": e["asset_class"],
            "Category":    e["sub_category"],
            "Issuer":      e["issuer"],
            "Benchmark":   e["benchmark"],
            "Domicile":    e["domicile"],
            "Policy":      e["dist_policy"],
        }
        for e in etfs
    ]
    return pd.DataFrame(rows)
