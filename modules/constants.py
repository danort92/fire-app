"""
Constants: INPS coefficients, MSCI returns, default values.
"""

INPS_COEFFICIENTS = {
    57: 0.04204, 58: 0.04308, 59: 0.04419, 60: 0.04536,
    61: 0.04661, 62: 0.04795, 63: 0.04936, 64: 0.05088,
    65: 0.0525,  66: 0.05423, 67: 0.05608, 68: 0.05808,
    69: 0.06024, 70: 0.06258, 71: 0.0651
}

MSCI_WORLD_RETURNS = [
    0.002,   0.1718,  0.2176,  -0.1465, -0.2361,
    0.3469,  0.0328,  0.0121,   0.1571,  0.0991,
    0.2513,  -0.0476,  0.0983,  0.2269,  0.0482,
    0.4156,  0.4218,  0.1632,   0.2372,  0.1695,
    -0.1669,  0.1888,  -0.049,  0.2343,  0.0559,
    0.2123,  0.1438,  0.1613,   0.2472,  0.2502,
    -0.1262, -0.1619, -0.1945,  0.3372,  0.1522,
    0.1046,  0.2036,  0.0935,  -0.4062,  0.3002,
    0.1193,  -0.0507,  0.1573,  0.2727,  0.0523,
    -0.0032,  0.0802,  0.2283,  -0.0844,  0.2804,
    0.159,   0.2182,  -0.178,   0.238,   0.19
]

MSCI_MEAN_GROSS = 0.1073
MSCI_STD_DEV = 0.1722

DEFAULT_ASSUMPTIONS = {
    "personal": {"current_age": 33, "target_age": 90, "age_started_working": 26},
    "salary": {"ral": 35600, "company_benefits": 2000, "inps_employee_rate": 0.0919, "surcharges_rate": 0.02},
    "etf": {"current_value": 85000, "monthly_pac": 1300, "ter": 0.003, "ivafe": 0.002,
            "expected_gross_return": 0.06, "capital_gains_tax": 0.26},
    "bank": {"current_balance": 35000, "interest_rate": 0.01, "emergency_fund": 20000, "stamp_duty": 34.2},
    "pension_fund": {"current_value": 22000, "tfr_contribution": 1993, "employer_contribution": 1079,
                     "personal_contribution": 228, "voluntary_extra": 3850, "max_deductible": 5164.57,
                     "fund_return": 0.04, "annuity_rate": 0.05, "age_joined": 30,
                     "tfr_destination": "fund", "tfr_company_value": 0},
    "macro": {"inflation": 0.02, "ral_growth": 0.005, "inps_contribution_rate": 0.33, "gdp_revaluation_rate": 0.02},
    "fire_scenario": {"stop_working_age": 50, "part_time": True, "part_time_salary": 900,
                      "part_time_monthly_gross": 0, "part_time_until_age": 60, "safe_withdrawal_rate": 0.035},
    "pension_options": {"early_pension_years": 0, "defer_to_71": False},
    "monte_carlo": {"n_simulations": 1000, "etf_volatility": 0.16, "pension_fund_volatility": 0.05,
                    "inflation_std": 0.01, "scenario": "Hybrid"}
}

DEFAULT_EXPENSES = {
    "Housing": [
        {"name": "Rent / Mortgage", "frequency": "Monthly", "amount": 175},
        {"name": "Condo fees", "frequency": "Monthly", "amount": 10},
        {"name": "Electricity", "frequency": "Monthly", "amount": 70},
        {"name": "Heating", "frequency": "Monthly", "amount": 100},
        {"name": "Water", "frequency": "Quarterly", "amount": 50},
        {"name": "Internet / Landline", "frequency": "Monthly", "amount": 25},
        {"name": "Home insurance", "frequency": "Annual", "amount": 0},
        {"name": "Other utilities", "frequency": "Annual", "amount": 120},
        {"name": "Furniture / Appliances", "frequency": "Annual", "amount": 50},
    ],
    "Groceries": [
        {"name": "Food shopping", "frequency": "Monthly", "amount": 150},
        {"name": "Restaurants / Takeaway", "frequency": "Monthly", "amount": 50},
        {"name": "Household / Cleaning products", "frequency": "Monthly", "amount": 20},
    ],
    "Transport": [
        {"name": "Car payment / Leasing", "frequency": "Monthly", "amount": 0},
        {"name": "Fuel", "frequency": "Monthly", "amount": 40},
        {"name": "Car insurance", "frequency": "Annual", "amount": 300},
        {"name": "Road tax", "frequency": "Annual", "amount": 100},
        {"name": "Car service / Maintenance", "frequency": "Annual", "amount": 300},
        {"name": "MOT / Inspection", "frequency": "Annual", "amount": 80},
        {"name": "Parking / Tolls", "frequency": "Monthly", "amount": 5},
        {"name": "Public transport", "frequency": "Monthly", "amount": 5},
    ],
    "Health": [
        {"name": "Medical visits", "frequency": "Annual", "amount": 150},
        {"name": "Medications", "frequency": "Monthly", "amount": 5},
        {"name": "Dentist", "frequency": "Annual", "amount": 50},
        {"name": "Health insurance", "frequency": "Annual", "amount": 0},
    ],
    "Pet": [
        {"name": "Pet food", "frequency": "Monthly", "amount": 25},
        {"name": "Vet / Care", "frequency": "Annual", "amount": 25},
        {"name": "Pet insurance", "frequency": "Annual", "amount": 0},
    ],
    "Personal": [
        {"name": "Clothing / Shoes", "frequency": "Annual", "amount": 100},
        {"name": "Personal care", "frequency": "Monthly", "amount": 10},
        {"name": "Mobile phone", "frequency": "Monthly", "amount": 10},
        {"name": "Gym / Sports", "frequency": "Monthly", "amount": 50},
    ],
    "Entertainment & Social": [
        {"name": "Travel / Holidays", "frequency": "Annual", "amount": 500},
        {"name": "Hobbies / Entertainment", "frequency": "Monthly", "amount": 10},
        {"name": "Gifts", "frequency": "Annual", "amount": 400},
        {"name": "Streaming subscriptions", "frequency": "Monthly", "amount": 10},
    ],
    "Education": [
        {"name": "Courses / Certifications", "frequency": "Annual", "amount": 1000},
        {"name": "Books", "frequency": "Annual", "amount": 30},
    ],
    "Other": [
        {"name": "Donations / Charity", "frequency": "Annual", "amount": 100},
        {"name": "Unexpected expenses", "frequency": "Annual", "amount": 300},
        {"name": "Other", "frequency": "Monthly", "amount": 10},
    ],
}
