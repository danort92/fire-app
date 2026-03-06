# FIRE Planning Tool 🔥 — Pianificazione Finanziaria per Lavoratori Italiani

Applicazione Streamlit per la pianificazione FIRE (Financial Independence, Retire Early) specificamente progettata per il contesto italiano.

## Funzionalità

- **IRPEF 2025**: Calcolo completo tasse, detrazioni lavoro dipendente, addizionali
- **Spese mensili**: Tracker per categoria con frequenza variabile (mensile/trimestrale/annuale)
- **Proiezioni patrimonio**: Simulazione anno per anno da età attuale a 90 (Conto + ETF + Fondo Pensione)
- **Analisi FIRE**: Età di pensionamento anticipato, PAC ottimale, analisi sensitività
- **Pensione INPS**: Calcolo metodo contributivo con coefficienti DM 436/2024
- **Confronto NPV**: Fondo pensione complementare vs ETF per il contributo volontario
- **Monte Carlo**: 1000 simulazioni con block bootstrap MSCI World 1970-2024

## Struttura

```
fire_app/
├── app.py                  # App principale Streamlit
├── modules/
│   ├── constants.py        # Dati MSCI, coefficienti INPS, default
│   ├── tax.py              # Calcolo IRPEF 2025
│   ├── expenses.py         # Gestione spese mensili
│   ├── projections.py      # Motore proiezione patrimonio
│   ├── fire_analysis.py    # Analisi FIRE (età minima, PAC ottimale)
│   ├── pension_state.py    # Pensione INPS contributiva
│   ├── pension_fund.py     # Fondo pensione complementare
│   ├── npv_comparison.py   # Confronto NPV fondo vs ETF
│   └── monte_carlo.py      # Simulazione Monte Carlo
└── requirements.txt
```

## Avvio

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Valori di Regressione Verificati

| Metrica | Valore Atteso | Stato |
|---------|---------------|-------|
| IRPEF netto annuo | € 26.976 | ✓ |
| Netto mensile ÷13 | € 2.075 | ✓ |
| Spese mensili totali | € 1.097,08 | ✓ |
| Pensione INPS netta (71 anni) | € 38.579,10/anno | ✓ |
| ETF a 34 anni | € 105.275 | ✓ |
| Conto a 50 anni | € 20.000 | ✓ |
| ETF a 50 anni | € 475.429,25 | ✓ |
| NPV Fondo Pensione | € 40.656,19 | ✓ |
| NPV ETF | € 16.044,62 | ✓ |
