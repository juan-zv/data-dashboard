import streamlit as st
import polars as pl
import plotly.express as px
from great_tables import GT, md, style, loc
from data_sources import load_daily_agg

store_id = st.session_state.get('selected_store_id', 'ALL')
store_name = st.session_state.get('selected_store_name', 'All Corporate Stores (Aggregate)')

@st.cache_data
def load_beverages_data(filter_store_id):
    df = load_daily_agg(filter_store_id)
    
    if filter_store_id != 'ALL':
        df = df.filter(pl.col('STORE_ID') == filter_store_id)
        
    # Filter to Packaged Beverages and drop null/empty brands
    df_beverages = df.filter(
        pl.col('CATEGORY') == 'Packaged Beverages'
    ).drop_nulls('BRAND').filter(pl.col('BRAND') != "")
    
    return df_beverages

# Load all beverages data
df_bev_all = load_beverages_data(store_id)

# Extract and get available months
df_bev_all = df_bev_all.with_columns(
    pl.col('DATE').cast(pl.Date).dt.strftime('%Y-%m').alias('MONTH')
)

available_months = sorted(df_bev_all.select('MONTH').unique().to_series().to_list(), reverse=True)
all_time_label = "All Time (Aggregate)"
period_options = [all_time_label] + available_months

# Sidebar month selector
st.sidebar.header("Filters")
selected_period = st.sidebar.selectbox("Select Month", period_options, index=0)

# Filter to selected month
df_bev = df_bev_all if selected_period == all_time_label else df_bev_all.filter(pl.col('MONTH') == selected_period)
period_label = selected_period
is_all_time = selected_period == all_time_label

st.title("In the packaged beverage category, which brands should I drop if I must drop some from the store?")
st.markdown(f"*(Currently viewing data for: **{store_name}** | Period: **{period_label}**)*")
st.markdown("Use the selection box in the sidebar to choose a specific month or view all-time aggregated data.")
st.markdown("Use the slider in the sidebar to adjust how many of the lowest-performing brands to display.")

# Aggregate performance by brand
brand_performance = (
    df_bev.group_by('BRAND')
    .agg(
        pl.sum('TOTAL_REVENUE_AMOUNT').alias('Total Sales ($)'),
        pl.sum('QUANTITY').alias('Total Quantity Sold'),
        pl.sum('TRANSACTION_COUNT').alias('Total Transactions')
    )
    .sort('Total Sales ($)', descending=False)  # sort ascending to see lowest first
)

st.sidebar.divider()
num_brands_to_show = st.sidebar.slider("Number of bottom brands to show", min_value=5, max_value=25, value=15, step=5)

bottom_brands = brand_performance.head(num_brands_to_show)

st.subheader(f"📉 Bottom {num_brands_to_show} Brands to Consider Dropping")

# --- KPIs ---
total_bev_sales = brand_performance.select(pl.sum("Total Sales ($)")).item()
bottom_brands_sales = bottom_brands.select(pl.sum("Total Sales ($)")).item()
bottom_pct = (bottom_brands_sales / total_bev_sales) * 100 if total_bev_sales else 0

total_brands_count = brand_performance.height

k1, k2, k3 = st.columns(3)
k1.metric(
    "All-Time Packaged Bev Sales" if is_all_time else "Monthly Packaged Bev Sales",
    f"${total_bev_sales:,.2f}",
    help=f"Total beverage revenue for {period_label}"
)
k2.metric(
    f"Bottom {num_brands_to_show} Sales",
    f"${bottom_brands_sales:,.2f}",
    delta=f"{bottom_pct:.2f}% of {'All-Time' if is_all_time else 'Monthly'} Revenue",
    delta_color="inverse",
    help=f"Revenue from the worst {num_brands_to_show} performers in {period_label}"
)
k3.metric(
    "Unique Brands Checked",
    total_brands_count,
    help=f"Total number of unique brands in {period_label}"
)

# Bar chart for the lowest performing brands
fig = px.bar(
    bottom_brands.to_pandas(), 
    x='Total Sales ($)', 
    y='BRAND', 
    orientation='h',
    title=f"Bottom {num_brands_to_show} Packaged Beverage Brands by Revenue",
    color='Total Quantity Sold',
    labels={'BRAND': 'Brand', 'Total Sales ($)': 'Total Revenue ($)'},
    color_continuous_scale='Reds_r'  # Red scale to imply warning/low performance
)
fig.update_layout(yaxis={'categoryorder':'total descending'})
st.plotly_chart(fig, width='stretch')

st.subheader("Data Table (Worst Performers)")
gt_bottom = (
    GT(bottom_brands.to_pandas())
    .tab_header(title=f"Bottom {num_brands_to_show} Brands Output")
    .cols_align(align="center")
    .fmt_currency(columns=["Total Sales ($)"])
    .fmt_number(columns=["Total Quantity Sold", "Total Transactions"], decimals=0)
    .tab_style(
        style=style.fill(color="#ffcccc"),
        locations=loc.body(rows=list(range(0, min(5, num_brands_to_show)))) # Highlight the absolute top 5 worst
    )
)
st.html(gt_bottom.as_raw_html())

st.markdown("""
**Recommendation:**
The brands listed above generate the least revenue and have the lowest total sales volume in the *Packaged Beverages* category. 
If inventory space needs to be freed up, these brands are the strongest candidates to drop.
""")

st.divider()
with st.expander("🖥️ Logic and Code"):
    st.markdown("""
    This page ranks the lowest-performing packaged beverage brands for the selected store and time period.

    It filters the aggregate transactions to Packaged Beverages, optionally scopes to a selected month, aggregates revenue/quantity/transactions by brand, then sorts ascending to surface drop candidates.
    """)
    st.code("""
# 0. Load aggregate transactions and scope to store
df = load_daily_agg(store_id)

# 1. Restrict to packaged beverages and selected period
df_bev = (
    df.filter(pl.col('CATEGORY') == 'Packaged Beverages')
      .drop_nulls('BRAND')
      .filter(pl.col('BRAND') != '')
)
if selected_period != 'All Time (Aggregate)':
    df_bev = df_bev.filter(pl.col('MONTH') == selected_period)

# 2. Aggregate brand performance and rank low to high
brand_performance = (
    df_bev.group_by('BRAND')
    .agg(
        pl.sum('TOTAL_REVENUE_AMOUNT').alias('Total Sales ($)'),
        pl.sum('QUANTITY').alias('Total Quantity Sold'),
        pl.sum('TRANSACTION_COUNT').alias('Total Transactions')
    )
    .sort('Total Sales ($)', descending=False)
)

# 3. Return bottom-N candidates from slider
bottom_brands = brand_performance.head(num_brands_to_show)
    """, language="python")