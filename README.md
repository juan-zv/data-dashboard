# Data Dashboard Demo

Interactive Streamlit dashboard for exploring retail performance across five Idaho stores.

The app is deployed on Streamlit Community Cloud at https://idaho-data-dashboard.streamlit.app/.

## Purpose

This project provides a small set of business-facing analytics views over local parquet datasets stored in the repository's [data](data) folder. It is designed to help compare store performance, surface product and category trends, and provide a lightweight demographic view for selected store locations.

## Pages

- **Landing**: store selector used to set the active store context for the rest of the app.
- **Top Five**: weekly and all-time top-selling products, excluding fuels, with category filtering and trend summaries.
- **Beverages**: packaged beverage brand analysis focused on identifying low-performing brands that could be dropped.
- **Cash & Credit**: compares customer behavior between cash and credit transactions, including top products, categories, and totals.
- **Demographics**: fetches live US Census ACS data for the selected store area and compares population, housing, education, and employment indicators.
- **Data Dictionary**: standalone data dictionary module in the repo; it is not currently wired into the app navigation.

## Folder Structure

```text
data-dashboard/
├── data/
│   ├── cstore_master_ctin.parquet
│   ├── cstore_stores.parquet
│   ├── cstore_discounts.parquet
│   ├── cstore_payments.parquet
│   ├── cstore_shopper.parquet
│   ├── cstore_store_status.parquet
│   ├── cstore_transactions_daily_agg.parquet
│   ├── cstore_transaction_sets.parquet
│   └── transaction_items/
├── landing.py
├── top_five.py
├── beverages.py
├── cash_credit.py
├── demographics.py
├── data_dictionary.py
├── data_sources.py
├── streamlit.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml
└── README.md
```

## Stack

- **Python** for the application code.
- **Streamlit** for the UI and page navigation.
- **Polars** for fast dataframe loading and transformation.
- **Plotly** for charts and visualizations.
- **Great Tables** for formatted tabular output.
- **Pandas** for a few page-level data shaping steps.
- **Requests** for the live Census API calls on the demographics page.
- **PyArrow** for parquet support.

## Data Source

The application now reads directly from the checked-in local parquet files under [data](data) instead of a Supabase S3 bucket.

## Entry Point

Run the app through [streamlit.py](streamlit.py), which wires together the page navigation and launches the Streamlit pages.
