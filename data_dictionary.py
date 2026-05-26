import streamlit as st
import polars as pl

st.title("Data Dictionary")
st.markdown("This standalone file contains the data dictionary content that was moved out of the main app navigation.")

@st.cache_data
def load_preview_data():
    return {
        'gtin': pl.read_parquet('data/cstore_master_ctin.parquet'),
        'discounts': pl.read_parquet('data/cstore_discounts.parquet'),
        'stores': pl.read_parquet('data/cstore_stores.parquet'),
        'payments': pl.read_parquet('data/cstore_payments.parquet'),
        'daily': pl.read_parquet('data/cstore_transactions_daily_agg.parquet'),
        'shopper': pl.read_parquet('data/cstore_shopper.parquet'),
        'sets': pl.read_parquet('data/cstore_transaction_sets.parquet'),
        'status': pl.read_parquet('data/cstore_store_status.parquet'),
        'items': pl.scan_parquet('data/transaction_items').head(100).collect()
    }

preview_data = load_preview_data()

st.markdown("""
### Overview
This page provides a detailed breakdown of the schema and columns present in the `.parquet` data files used to power this dashboard, along with a preview of the datasets themselves.
""")

st.markdown("""
### 1. `cstore_master_ctin` (Product Master Data)
Details related to product items and GTINs (barcodes).
*   **GTIN**: String. Global Trade Item Number (unique product identifier barcode).
*   **CATEGORY / SUBCATEGORY**: String. Top-level and secondary level classifications of the product.
*   **MANUFACTURER_PARENT / MANUFACTURER**: String. Entity making or owning the brand.
*   **BRAND**: String. Product brand name.
*   **PRODUCT_TYPE / SUB_PRODUCT_TYPE**: String. Detailed class level of the items.
*   **FLAVOR**: String. Flavor variation (e.g., Cherry, Cola).
*   **UNIT_SIZE / PACK_SIZE**: String. Dimensions, volume, or weight per unit/pack.
*   **PACKAGE**: String. Packaging type (e.g., Can, Bottle, Bag).
*   **SKUPOS_DESCRIPTION**: String. Standard description used strictly by POS systems.
*   **CREATED_AT / UPDATED_AT**: Datetime. Record timestamps.
""")
with st.expander("Preview `cstore_master_ctin` (First 5 Rows)"):
    st.dataframe(preview_data['gtin'].head(5).to_pandas())

st.markdown("""
### 2. `cstore_stores` & `cstore_store_status` (Store Location & Demographics Context)
Details describing individual convenience store locations.
*   **STORE_ID**: Decimal/String. Unique identifier for the store.
*   **STORE_NAME**: String. Name/designation of the store.
*   **STORE_CHAIN_ID / STORE_CHAIN_NAME**: Decimal/String. Identifying numbers and names for corporate chains vs independent.
*   **STREET_ADDRESS / CITY / STATE / ZIP_CODE**: String. Store physical location.
*   **LATITUDE / LONGITUDE**: Float. GPS coordinates.
*   **START_DATE / START_WEEK_CONTINUOUS_DATA**: Date. Milestones marking when the store started piping data into the system.
*   **CHAIN_SIZE**: Decimal. Contextual indicator of how big the chain is.
*   *(Status specific)* **STORE_FLAG / ACTIVE_STATUS**: String. Indicators if a store is currently active.
""")
with st.expander("Preview `cstore_stores` & `cstore_store_status` (First 5 Rows)"):
    st.write("Stores:")
    st.dataframe(preview_data['stores'].head(5).to_pandas())
    st.write("Store Status:")
    st.dataframe(preview_data['status'].head(5).to_pandas())

st.markdown("""
### 3. `transaction_items` (Individual items purchased inside a transaction)
Provides the most granular details of *what* was bought on each ticket.
*   **TRANSACTION_ITEM_ID**: String. Unique identifier for the line item inside a cart.
*   **TRANSACTION_SET_ID**: String. Uniquely links back to the individual checkout iteration (cart level).
*   **GTIN**: String. Links item to the `cstore_master_ctin` table.
*   **DATE_TIME**: Datetime. Exact time the item was scanned.
*   **POS_DESCRIPTION**: String. Raw string description from the cash register.
*   **UNIT_PRICE / UNIT_QUANTITY**: Float/Int. Quantity bought and base price.
*   **DISCOUNT_AMOUNT / TAXABLE_AMOUNT / TAX_RATE / GRAND_TOTAL_AMOUNT**: Float. Financial metrics on this specific item.
*   **SCAN_TYPE / NONSCAN_CATEGORY**: String. Indicates if it was normally barcode scanned vs manually entered.
""")
with st.expander("Preview `transaction_items` (First 5 Rows)"):
    st.dataframe(preview_data['items'].head(5).to_pandas())

st.markdown("""
### 4. `cstore_transaction_sets` (Receipt / Cart Header)
Summary of the entire checkout transaction (Header level).
*   **TRANSACTION_SET_ID**: String. The unique "Receipt ID".
*   **POS_TYPE_ID**: String. Identifier for the register terminal.
*   **DATE_TIME / TIME_ZONE**: Datetime/String. Complete timestamp context.
*   **PAYMENT_TYPE**: String. Usually categorized as 'Cash', 'Credit', 'EBT', etc.
*   **SUBTOTAL_AMOUNT / GRAND_TOTAL_AMOUNT / TAX_AMOUNT**: Float. Total checkout amounts.
*   **TENDER_RECEIVED_AMOUNT / TENDER_GIVEN_AMOUNT**: Float. Specifically handles how much exact cash/money was handed to the clerk and how much change was given.
""")
with st.expander("Preview `cstore_transaction_sets` (First 5 Rows)"):
    st.dataframe(preview_data['sets'].head(5).to_pandas())

st.markdown("""
### 5. `cstore_payments` (Tender/Payment records)
Additional detailed information tied to the transaction payment method.
*   **PAYMENT_ID**: String. Unique payment iteration.
*   **TRANSACTION_SET_ID**: String. Links back to the receipt header.
*   **PAYMENT_NUMBER / PAYMENT_TYPE / PAYMENT_ENTRY / CARD_TYPE**: String. Defines type of payment and method.
*   **TENDER / CHANGE**: Float. Value processed by this payment type and change returned.
""")
with st.expander("Preview `cstore_payments` (First 5 Rows)"):
    st.dataframe(preview_data['payments'].head(5).to_pandas())

st.markdown("""
### 6. `cstore_shopper`
Tracks anonymous or loyalty shopper identifiers across transactions.
*   **SHOPPER_ID**: String. High-level unique mask for a customer entity.
*   **TRANSACTION_SET_ID / PAYMENT_ID**: String. Transaction map links linking back to the transaction header.
""")
with st.expander("Preview `cstore_shopper` (First 5 Rows)"):
    st.dataframe(preview_data['shopper'].head(5).to_pandas())

st.markdown("""
### 7. `cstore_discounts`
Provides the mapping of any promotions/loyalty markdowns.
*   **DISCOUNT_ID / DISCOUNT_TYPE / DISCOUNT_NAME**: String/Integer. Classification of what promo triggered.
*   **QUANTITY / ADJUSTMENT_AMOUNT / DISCOUNT_AMOUNT**: Float/Integer. Metrics on how much was discounted.
*   **TRANSACTION_ITEM_ID**: String. Maps back to the line item in `transaction_items`.
""")
with st.expander("Preview `cstore_discounts` (First 5 Rows)"):
    st.dataframe(preview_data['discounts'].head(5).to_pandas())

st.markdown("""
### 8. `cstore_transactions_daily_agg`
Pre-aggregated rollups by day. Speeds up total sales/product queries.
*   **STORE_ID / GTIN / DATE / DAY_OF_WEEK**: Group-by metrics linking store, product, and timeline.
*   **CATEGORY / BRAND / PRODUCT_TYPE / SKU_DESCRIPTION**: String. Roll up metadata attached to the record to avoid extra joins.
*   **QUANTITY / TRANSACTION_COUNT / TOTAL_REVENUE_AMOUNT**: Int/Float. Aggregate metrics for that day for that item.
*   **QUANTITY_WITH_DISCOUNT / TRANSACTION_COUNT_WITH_DISCOUNT**: Int. Promotion aggregates for the day.
""")
with st.expander("Preview `cstore_transactions_daily_agg` (First 5 Rows)"):
    st.dataframe(preview_data['daily'].head(5).to_pandas())
