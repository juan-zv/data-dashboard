import streamlit as st
import polars as pl
import plotly.express as px
from great_tables import GT, md, style, loc
from data_sources import load_reference_gtin_master, load_transaction_items, load_transaction_sets

store_id = st.session_state.get('selected_store_id', 'ALL')
store_name = st.session_state.get('selected_store_name', 'All Corporate Stores (Aggregate)')
all_time_label = "All Time (Aggregate)"

st.title("How do cash customers and credit customers compare?")

@st.cache_data
def get_available_months(filter_store_id):
    month_df = load_transaction_sets(filter_store_id).with_columns(
        pl.col('DATE_TIME').dt.strftime('%Y-%m').alias('MONTH')
    )

    months = month_df.select('MONTH').drop_nulls('MONTH').unique().to_series().to_list()
    return sorted(months, reverse=True)


st.sidebar.header("Filters")
available_months = get_available_months(store_id)
period_options = [all_time_label] + available_months
selected_period = st.sidebar.selectbox("Select Month", period_options, index=0)

st.markdown(f"*(Currently viewing data for: **{store_name}** | Period: **{selected_period}**)*")
st.markdown("Use the selection box in the sidebar to choose a specific month or view all-time aggregated data.")
st.markdown("Use the tabs below to compare cash vs credit transactions, or to dive deeper into each payment type individually.")

# --- CALCULATIONS ---

@st.cache_data
def load_cash_credit_data(filter_store_id, selected_period):
    # Load and filter only CASH and CREDIT from transaction sets
    df_sets = load_transaction_sets(filter_store_id).select([
        'STORE_ID', 'TRANSACTION_SET_ID', 'PAYMENT_TYPE', 'GRAND_TOTAL_AMOUNT', 'DATE_TIME'
    ])
    
    if selected_period != all_time_label:
        df_sets = df_sets.with_columns(
            pl.col('DATE_TIME').cast(pl.Datetime, strict=False).dt.strftime('%Y-%m').alias('MONTH')
        ).filter(pl.col('MONTH') == selected_period)
        
    df_sets = df_sets.filter(pl.col('PAYMENT_TYPE').is_in(['CASH', 'CREDIT']))
    
    # Load individual purchased items Details
    df_items = load_transaction_items(filter_store_id).select([
        'STORE_ID', 'TRANSACTION_SET_ID', 'GTIN', 'POS_DESCRIPTION', 'UNIT_QUANTITY', 'GRAND_TOTAL_AMOUNT'
    ])
    
    # Calculate Total Totals (from Sets to avoid duplicate sums)
    sets_agg = df_sets.group_by('PAYMENT_TYPE').agg(
        pl.sum('GRAND_TOTAL_AMOUNT').round(2).alias('Total Revenue ($)'),
        pl.count('TRANSACTION_SET_ID').alias('Number of Transactions')
    )
    
    # Perform inner join to attach Payment Type to each Item scanned
    joined_items = df_items.join(df_sets.select(['TRANSACTION_SET_ID', 'PAYMENT_TYPE']), on='TRANSACTION_SET_ID', how='inner')
    
    # Count total physical items
    items_agg = joined_items.group_by('PAYMENT_TYPE').agg(
        pl.sum('UNIT_QUANTITY').alias('Total Items Purchased')
    )
    
    # Combine Totals
    overall_totals = sets_agg.join(items_agg, on='PAYMENT_TYPE')
    
    # Calculate Top Products by Payment Type
    top_products = (
        joined_items.group_by(['PAYMENT_TYPE', 'POS_DESCRIPTION'])
        .agg(pl.sum('UNIT_QUANTITY').alias('Quantity_Sold'))
        .filter(pl.col('POS_DESCRIPTION').is_not_null() & (pl.col('POS_DESCRIPTION') != ""))
    )

    # Calculate Top Categories by Payment Type
    df_categories = joined_items.join(
        load_reference_gtin_master().select(['GTIN', 'CATEGORY']),
        on='GTIN',
        how='left'
    )

    category_totals = (
        df_categories
        .filter(pl.col('CATEGORY').is_not_null() & (pl.col('CATEGORY') != ""))
        .group_by(['PAYMENT_TYPE', 'CATEGORY'])
        .agg(
            pl.sum('GRAND_TOTAL_AMOUNT').alias('Total Revenue ($)'),
            pl.sum('UNIT_QUANTITY').alias('Total Items Purchased')
        )
        .sort('Total Revenue ($)', descending=True)
    )
    
    # Extract top 15 for each
    top_cash = top_products.filter(pl.col('PAYMENT_TYPE') == 'CASH').sort('Quantity_Sold', descending=True).head(15)
    top_credit = top_products.filter(pl.col('PAYMENT_TYPE') == 'CREDIT').sort('Quantity_Sold', descending=True).head(15)
    
    return overall_totals, top_cash, top_credit, category_totals

with st.spinner("Crunching payment datasets..."):
    totals_df, top_cash_df, top_credit_df, category_df = load_cash_credit_data(store_id, selected_period)


# --- UI LAYOUT ---

st.markdown("""
This page provides a direct comparison between **Cash** and **Credit** transactions to uncover purchasing habits, overall monetary value, and the most popular products for each payment type.
""")

def payment_row(df, payment_type):
    row_df = df.filter(pl.col('PAYMENT_TYPE') == payment_type)
    if row_df.height == 0:
        return {"Total Revenue ($)": 0.0, "Number of Transactions": 0, "Total Items Purchased": 0}
    return row_df.row(0, named=True)


cash_row = payment_row(totals_df, 'CASH')
credit_row = payment_row(totals_df, 'CREDIT')

compare_tab, cash_tab, credit_tab = st.tabs([
    "Compare Cash vs Credit",
    "Cash Only",
    "Credit Only"
])

with compare_tab:
    rev_delta = cash_row["Total Revenue ($)"] - credit_row["Total Revenue ($)"]
    rev_diff_pct = (rev_delta / credit_row["Total Revenue ($)"]) * 100 if credit_row["Total Revenue ($)"] else 0
    tx_delta = cash_row["Number of Transactions"] - credit_row["Number of Transactions"]
    tx_diff_pct = (tx_delta / credit_row["Number of Transactions"]) * 100 if credit_row["Number of Transactions"] else 0
    item_delta = cash_row["Total Items Purchased"] - credit_row["Total Items Purchased"]
    item_diff_pct = (item_delta / credit_row["Total Items Purchased"]) * 100 if credit_row["Total Items Purchased"] else 0

    st.subheader("KPI Summary")
    k1, k2, k3 = st.columns(3)
    k1.metric("Cash Revenue", f"${cash_row['Total Revenue ($)']:,.2f}", delta=f"{rev_diff_pct:+.1f}% vs Card")
    k1.metric("Card Revenue", f"${credit_row['Total Revenue ($)']:,.2f}", delta=f"{(-rev_diff_pct):+.1f}% vs Cash")
    k2.metric("Cash Transactions", f"{cash_row['Number of Transactions']:,}", delta=f"{tx_diff_pct:+.1f}% vs Card")
    k2.metric("Card Transactions", f"{credit_row['Number of Transactions']:,}", delta=f"{(-tx_diff_pct):+.1f}% vs Cash")
    k3.metric("Cash Items", f"{cash_row['Total Items Purchased']:,}", delta=f"{item_diff_pct:+.1f}% vs Card")
    k3.metric("Card Items", f"{credit_row['Total Items Purchased']:,}", delta=f"{(-item_diff_pct):+.1f}% vs Cash")

    st.divider()
    st.subheader("1. Products Most Often Bought")

    col_cash, col_credit = st.columns(2)

    with col_cash:
        st.markdown("**Top 15 Products Bought with Cash**")
        fig_cash = px.bar(
            top_cash_df.to_pandas(),
            x='Quantity_Sold',
            y='POS_DESCRIPTION',
            orientation='h',
            color='Quantity_Sold',
            color_continuous_scale='Greens',
            labels={'Quantity_Sold': 'Quantity', 'POS_DESCRIPTION': 'Product'}
        )
        fig_cash.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_cash, width='stretch', key='compare_cash_products_chart')

    with col_credit:
        st.markdown("**Top 15 Products Bought with Credit**")
        fig_credit = px.bar(
            top_credit_df.to_pandas(),
            x='Quantity_Sold',
            y='POS_DESCRIPTION',
            orientation='h',
            color='Quantity_Sold',
            color_continuous_scale='Blues',
            labels={'Quantity_Sold': 'Quantity', 'POS_DESCRIPTION': 'Product'}
        )
        fig_credit.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_credit, width='stretch', key='compare_credit_products_chart')

    st.divider()
    st.subheader("2. Total Purchase Amount")
    fig_revenue = px.bar(
        totals_df.to_pandas(),
        x='PAYMENT_TYPE',
        y='Total Revenue ($)',
        color='PAYMENT_TYPE',
        labels={'PAYMENT_TYPE': 'Payment Type', 'Total Revenue ($)': 'Total Revenue ($)'},
        title="Total Purchase Amount by Payment Type",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    st.plotly_chart(fig_revenue, width='stretch', key='compare_revenue_chart')

    st.divider()
    st.subheader("3. Total Number of Items")
    fig_items = px.bar(
        totals_df.to_pandas(),
        x='PAYMENT_TYPE',
        y='Total Items Purchased',
        color='PAYMENT_TYPE',
        labels={'PAYMENT_TYPE': 'Payment Type', 'Total Items Purchased': 'Total Items Purchased'},
        title="Total Number of Items by Payment Type",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    st.plotly_chart(fig_items, width='stretch', key='compare_items_chart')

    st.divider()
    st.subheader("Summary Table")
    gt_payment = (
        GT(totals_df.to_pandas())
        .tab_header(title="Monetary Value and Quantity by Payment Method")
        .cols_align(align="center")
        .fmt_currency(columns=["Total Revenue ($)"])
        .fmt_number(columns=["Total Items Purchased", "Number of Transactions"], decimals=0)
    )
    st.html(gt_payment.as_raw_html())

with cash_tab:
    st.subheader("Cash Performance")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Revenue", f"${cash_row['Total Revenue ($)']:,.2f}")
    c2.metric("Number of Transactions", f"{cash_row['Number of Transactions']:,}")
    c3.metric("Total Items Purchased", f"{cash_row['Total Items Purchased']:,}")

    st.divider()
    st.subheader("Averages")
    cash_avg_revenue = cash_row['Total Revenue ($)'] / cash_row['Number of Transactions'] if cash_row['Number of Transactions'] else 0
    cash_avg_items = cash_row['Total Items Purchased'] / cash_row['Number of Transactions'] if cash_row['Number of Transactions'] else 0
    a1, a2 = st.columns(2)
    a1.metric("Average Revenue per Transaction", f"${cash_avg_revenue:,.2f}")
    a2.metric("Average Items per Transaction", f"{cash_avg_items:,.2f}")

    st.divider()
    st.markdown("##### Top 15 Products Bought with Cash")
    fig_cash = px.bar(
        top_cash_df.to_pandas(),
        x='Quantity_Sold',
        y='POS_DESCRIPTION',
        orientation='h',
        color='Quantity_Sold',
        color_continuous_scale='Greens',
        labels={'Quantity_Sold': 'Quantity', 'POS_DESCRIPTION': 'Product'}
    )
    fig_cash.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_cash, width='stretch', key='cash_only_products_chart')

    st.divider()
    st.subheader("Top Categories")
    cash_categories = category_df.filter(pl.col('PAYMENT_TYPE') == 'CASH').sort('Total Revenue ($)', descending=True).head(10)
    fig_cash_categories = px.bar(
        cash_categories.to_pandas(),
        x='Total Revenue ($)',
        y='CATEGORY',
        orientation='h',
        color='Total Revenue ($)',
        color_continuous_scale='Greens',
        labels={'CATEGORY': 'Category', 'Total Revenue ($)': 'Revenue ($)'}
    )
    fig_cash_categories.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_cash_categories, width='stretch', key='cash_only_categories_chart')

with credit_tab:
    st.subheader("Credit Performance")
    cr1, cr2, cr3 = st.columns(3)
    cr1.metric("Total Revenue", f"${credit_row['Total Revenue ($)']:,.2f}")
    cr2.metric("Number of Transactions", f"{credit_row['Number of Transactions']:,}")
    cr3.metric("Total Items Purchased", f"{credit_row['Total Items Purchased']:,}")

    st.divider()
    st.subheader("Averages")
    credit_avg_revenue = credit_row['Total Revenue ($)'] / credit_row['Number of Transactions'] if credit_row['Number of Transactions'] else 0
    credit_avg_items = credit_row['Total Items Purchased'] / credit_row['Number of Transactions'] if credit_row['Number of Transactions'] else 0
    a1, a2 = st.columns(2)
    a1.metric("Average Revenue per Transaction", f"${credit_avg_revenue:,.2f}")
    a2.metric("Average Items per Transaction", f"{credit_avg_items:,.2f}")

    st.divider()
    st.markdown("##### Top 15 Products Bought with Credit")
    fig_credit = px.bar(
        top_credit_df.to_pandas(),
        x='Quantity_Sold',
        y='POS_DESCRIPTION',
        orientation='h',
        color='Quantity_Sold',
        color_continuous_scale='Blues',
        labels={'Quantity_Sold': 'Quantity', 'POS_DESCRIPTION': 'Product'}
    )
    fig_credit.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_credit, width='stretch', key='credit_only_products_chart')

    st.divider()
    st.subheader("Top Categories")
    credit_categories = category_df.filter(pl.col('PAYMENT_TYPE') == 'CREDIT').sort('Total Revenue ($)', descending=True).head(10)
    fig_credit_categories = px.bar(
        credit_categories.to_pandas(),
        x='Total Revenue ($)',
        y='CATEGORY',
        orientation='h',
        color='Total Revenue ($)',
        color_continuous_scale='Blues',
        labels={'CATEGORY': 'Category', 'Total Revenue ($)': 'Revenue ($)'}
    )
    fig_credit_categories.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_credit_categories, width='stretch', key='credit_only_categories_chart')

st.divider()
with st.expander("🖥️ Logic and Code"):
    st.markdown("""
    This page compares cash vs credit behavior using raw transaction headers and item-level scans.

    It filters to CASH/CREDIT, applies store and optional monthly scope, aggregates totals from transaction headers, joins to item scans for quantity/product/category analysis, and then renders compare and single-payment tabs.
    """)
    st.code("""
# 0. Scan transaction sets (headers) and apply store/period filters
    df_sets = load_transaction_sets(store_id).select([
    'STORE_ID', 'TRANSACTION_SET_ID', 'PAYMENT_TYPE', 'GRAND_TOTAL_AMOUNT', 'DATE_TIME'
])
if selected_period != 'All Time (Aggregate)':
    df_sets = df_sets.with_columns(pl.col('DATE_TIME').dt.strftime('%Y-%m').alias('MONTH'))
    df_sets = df_sets.filter(pl.col('MONTH') == selected_period)
df_sets = df_sets.filter(pl.col('PAYMENT_TYPE').is_in(['CASH', 'CREDIT']))

# 1. Scan item-level rows and join to payment type from sets
    df_items = load_transaction_items(store_id).select([
    'STORE_ID', 'TRANSACTION_SET_ID', 'GTIN', 'POS_DESCRIPTION', 'UNIT_QUANTITY', 'GRAND_TOTAL_AMOUNT'
])

joined_items = df_items.join(
    df_sets.select(['TRANSACTION_SET_ID', 'PAYMENT_TYPE']),
    on='TRANSACTION_SET_ID',
    how='inner'
)

# 2. Aggregate totals and build top products/categories by payment type
totals_df = df_sets.group_by('PAYMENT_TYPE').agg(
    pl.sum('GRAND_TOTAL_AMOUNT').alias('Total Revenue ($)'),
    pl.count('TRANSACTION_SET_ID').alias('Number of Transactions')
).collect()

items_agg = joined_items.group_by('PAYMENT_TYPE').agg(
    pl.sum('UNIT_QUANTITY').alias('Total Items Purchased')
).collect()

totals_df = totals_df.join(items_agg, on='PAYMENT_TYPE')
    """, language="python")