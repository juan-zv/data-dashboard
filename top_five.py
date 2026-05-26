import streamlit as st
import polars as pl
import plotly.express as px
import datetime
from great_tables import GT, md, style, loc
from data_sources import load_daily_agg

store_id = st.session_state.get('selected_store_id', 'ALL')
store_name = st.session_state.get('selected_store_name', 'All Corporate Stores (Aggregate)')


st.title("Excluding fuels, what are the top five products with the highest weekly sales?")
st.markdown(f"*(Currently viewing data for: **{store_name}**)*")
st.markdown("Select a date on the sidebar to change the week displayed.")

# Cache data loading so the dashboard remains fast, unique per store
@st.cache_data
def load_data(filter_store_id):
    df = load_daily_agg(filter_store_id)
    
    if filter_store_id != 'ALL':
        df = df.filter(pl.col('STORE_ID').cast(pl.Utf8) == str(filter_store_id))
        
    # Fill in product name using SCAN descriptions
    # and dropping any items with absolutely no name
    df_clean = df.with_columns(
        pl.col('SKUPOS_DESCRIPTION').cast(pl.Utf8).alias('ProductName')
    ).drop_nulls(['ProductName', 'DATE']).filter(
        pl.col('ProductName').str.strip_chars() != ""
    )
    
    # Filter out Fuels
    df_no_fuel = df_clean.filter(
        (pl.col('NONSCAN_CATEGORY').fill_null("") != 'FUEL')
    )
    return df_no_fuel

df = load_data(store_id)

st.sidebar.header("Filters")

if df.height > 0:
    min_date = df.select(pl.min("DATE")).item()
    max_date = df.select(pl.max("DATE")).item()
else:
    min_date = datetime.date(2022, 9, 1)
    max_date = datetime.date(2024, 8, 29)

selected_date = st.sidebar.date_input(
    "Query Specific Week (Select Date):",
    value=max_date,
    min_value=min_date,
    max_value=max_date
)

# Dynamic category exclusion filter
available_categories = sorted([c for c in df['CATEGORY'].unique().to_list() if c is not None])
# Default select Lottery and Tobacco to exclude since they dominate revenue
default_exclusions = [c for c in ["Lottery/Gaming", "Cigarettes", "Other Tobacco Products"] if c in available_categories]

categories_to_exclude = st.sidebar.multiselect(
    "Categories to Exclude:",
    options=available_categories,
    default=default_exclusions,
    help="Select any specific categories you want to completely remove from the ranking (e.g., 'Lottery/Gaming', 'Beer')."
)

df_filtered = df
if categories_to_exclude:
    df_filtered = df_filtered.filter(
        pl.col('CATEGORY').fill_null("").is_in(categories_to_exclude).not_()
    )
    # Extra robustness: if "Lottery/Gaming" was selected to be excluded, 
    # strictly drop non-scan lottery items too that might lack a proper CATEGORY.
    if "Lottery/Gaming" in categories_to_exclude:
        df_filtered = df_filtered.filter(
            (pl.col('NONSCAN_CATEGORY').fill_null("") != 'LOTTERY') &
            (pl.col('ProductName').str.to_uppercase().str.contains("LOTTERY|SCRATCH").not_().fill_null(True))
        )

# --- CALCULATIONS ---

# 0. Specific week calculations
start_of_week = selected_date - datetime.timedelta(days=selected_date.weekday())
end_of_week = start_of_week + datetime.timedelta(days=6)

df_weekly = df_filtered.filter(
    (pl.col("DATE") >= start_of_week) & 
    (pl.col("DATE") <= end_of_week)
)

df_weekly_unexcluded = df.filter(
    (pl.col("DATE") >= start_of_week) &
    (pl.col("DATE") <= end_of_week)
)

top_5_specific_week = None
if df_weekly.height > 0:
    top_5_specific_week = (
        df_weekly
        .group_by("ProductName", "CATEGORY")
        .agg(
            pl.sum("TOTAL_REVENUE_AMOUNT").alias("Weekly Sales ($)"),
            pl.sum("QUANTITY").alias("Quantity Sold")
        )
        .sort("Weekly Sales ($)", descending=True)
        .head(5)
    )

# 1. Group by product to find the top 5 overall highest revenue generators
top_5_overall = (
    df_filtered
    .group_by("ProductName", "CATEGORY")
    .agg(
        pl.sum("TOTAL_REVENUE_AMOUNT").alias("Total Sales ($)"),
        pl.sum("QUANTITY").alias("Total Quantity Sold")
    )
    .sort("Total Sales ($)", descending=True)
    .head(5)
)

# 2. Get the names of the top 5 to filter our weekly trend data
top_5_names = top_5_overall.get_column("ProductName").to_list()

# Filter full dataset for only top 5 products and aggregate to Weekly level
top_5_weekly = (
    df_filtered
    .filter(pl.col("ProductName").is_in(top_5_names))
    .with_columns(
        pl.col("DATE").dt.year().alias("year"),
        pl.col("DATE").dt.week().alias("week")
    )
    .with_columns(
        pl.format("{}-W{}", pl.col("year"), pl.col("week").cast(pl.Utf8).str.zfill(2)).alias("Year_Week")
    )
    .group_by("Year_Week", "ProductName")
    .agg(
        pl.sum("TOTAL_REVENUE_AMOUNT").alias("Weekly Sales ($)"),
        pl.sum("QUANTITY").alias("Weekly Quantity")
    )
    .sort("Year_Week")
)

# 3. Calculate Average Weekly metrics for the overall top 5
top_5_avg_weekly = (
    top_5_weekly
    .group_by("ProductName")
    .agg(
        pl.mean("Weekly Sales ($)").round(2).alias("Average Weekly Sales ($)"),
        pl.mean("Weekly Quantity").round(0).cast(pl.Int32).alias("Average Weekly Quantity Sold")
    )
    .sort("Average Weekly Sales ($)", descending=True)
)


# --- UI LAYOUT ---

st.header(f"📅 Week in Review: {start_of_week.strftime('%b %d')} - {end_of_week.strftime('%b %d, %Y')}")

st.divider()

if top_5_specific_week is not None and top_5_specific_week.height > 0:
    # --- KPIs ---
    total_week_sales = df_weekly.select(pl.sum("TOTAL_REVENUE_AMOUNT")).item()
    top_5_week_sales = top_5_specific_week.select(pl.sum("Weekly Sales ($)")).item()
    week_pct = (top_5_week_sales / total_week_sales) * 100 if total_week_sales else 0
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Weekly Total Sales", f"${total_week_sales:,.2f}", help="Total revenue for all filtered products this week")
    kpi2.metric("Top 5 Products Revenue", f"${top_5_week_sales:,.2f}", delta=f"{week_pct:.1f}% of Weekly Total", delta_color="normal")
    top_product_name = top_5_specific_week.get_column("ProductName")[0]
    kpi3.metric("🏆 #1 Product of the Week", top_product_name, help="Highest grossing product of the week")

    st.subheader("📈 Selected Week Sales Comparison")
    fig = px.bar(
        top_5_specific_week.to_pandas(), 
        x='ProductName', 
        y='Weekly Sales ($)', 
        color='CATEGORY',
        title=f"Top 5 Products Sales: Week of {start_of_week.strftime('%b %d')} - {end_of_week.strftime('%b %d, %Y')}",
        labels={'ProductName': 'Product', 'Weekly Sales ($)': 'Weekly Sales ($)'},
        template="plotly_white"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, width='stretch')

    st.subheader("📋 Top 5 Products Summary (Selected Week)")
    gt_specific = (
        GT(top_5_specific_week.to_pandas())
        .tab_header(title="Top 5 Products of the Week", subtitle=f"{start_of_week.strftime('%b %d, %Y')} to {end_of_week.strftime('%b %d, %Y')}")
        .fmt_currency(columns=["Weekly Sales ($)"])
        .fmt_number(columns=["Quantity Sold"], decimals=0)
        .tab_style(
            style=style.fill(color="lightgreen"),
            locations=loc.body(rows=[0])
        )
        .cols_align(align="center")
    )
    st.html(gt_specific.as_raw_html())
else:
    if df_weekly_unexcluded.height > 0 and categories_to_exclude:
        st.info("No data available for the selected week after applying category exclusions. Try removing one or more excluded categories in the sidebar.")
    else:
        st.info("No data available to chart or display for the selected week.")

st.divider()

st.header("🏆 All-Time Top Performers")
st.markdown("Comparing the absolute best-selling products across the entire database timeframe.")

overall_col1, overall_col2 = st.columns(2)

with overall_col1:
    st.subheader("⚖️ Average Weekly Performance")
    gt_avg = (
        GT(top_5_avg_weekly.to_pandas())
        .tab_header(title="Weekly Pacing for Top Products")
        .fmt_currency(columns=["Average Weekly Sales ($)"])
        .fmt_number(columns=["Average Weekly Quantity Sold"], decimals=0)
        .cols_align(align="center")
    )
    st.html(gt_avg.as_raw_html())

with overall_col2:
    st.subheader("🥇 Top 5 Overall (Total Sales)")
    gt_overall = (
        GT(top_5_overall.to_pandas())
        .tab_header(title="All-Time Revenue Leaders")
        .fmt_currency(columns=["Total Sales ($)"])
        .fmt_number(columns=["Total Quantity Sold"], decimals=0)
        .cols_align(align="center")
    )
    st.html(gt_overall.as_raw_html())

st.divider()
with st.expander("🖥️ Logic and Code"):
    st.markdown("""
    This page calculates top-selling products from daily aggregate transaction data, scoped to the selected store.

    It builds three views: the selected week's top 5 products, all-time top 5 products, and average weekly pace for those top products.
    """)
    st.code("""
# 0. Load and store-filter data
df = load_daily_agg(store_id)

# 1. Apply non-fuel/category exclusions, then compute selected week top 5
df_weekly = df.filter((pl.col('DATE') >= start_of_week) & (pl.col('DATE') <= end_of_week))
top_5_specific_week = (
    df_weekly
    .group_by('ProductName', 'CATEGORY')
    .agg(
        pl.sum('TOTAL_REVENUE_AMOUNT').alias('Weekly Sales ($)'),
        pl.sum('QUANTITY').alias('Quantity Sold')
    )
    .sort('Weekly Sales ($)', descending=True)
    .head(5)
)

# 2. Compute all-time top 5 and weekly trend table for those products
top_5_overall = (
    df
    .group_by('ProductName', 'CATEGORY')
    .agg(
        pl.sum('TOTAL_REVENUE_AMOUNT').alias('Total Sales ($)'),
        pl.sum('QUANTITY').alias('Total Quantity Sold')
    )
    .sort('Total Sales ($)', descending=True)
    .head(5)
)

top_5_names = top_5_overall.get_column('ProductName').to_list()
top_5_weekly = (
    df.filter(pl.col('ProductName').is_in(top_5_names))
      .group_by('Year_Week', 'ProductName')
      .agg(
          pl.sum('TOTAL_REVENUE_AMOUNT').alias('Weekly Sales ($)'),
          pl.sum('QUANTITY').alias('Weekly Quantity')
      )
)

# 3. Average weekly pace for the all-time leaders
top_5_avg_weekly = (
    top_5_weekly.group_by('ProductName')
    .agg(
        pl.mean('Weekly Sales ($)').alias('Average Weekly Sales ($)'),
        pl.mean('Weekly Quantity').alias('Average Weekly Quantity Sold')
    )
)
    """, language="python")