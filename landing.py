import streamlit as st
import polars as pl
from data_sources import load_reference_stores

st.title("Landing Page")

# Setup global store context selector
st.markdown("### 🏪 Global Store Selection")
st.markdown("Select a store here to filter data across **all pages** in this application.")

@st.cache_data
def get_stores_with_data():
    valid_ids = ['31631', '31632', '18191', '25255', '19075', '6385']
    stores_df = load_reference_stores().filter(
        pl.col('STORE_ID').cast(pl.Utf8).is_in(valid_ids)
    )
    # Sort stores alphabetically for easier reading in the UI
    return stores_df.select(['STORE_ID', 'STORE_NAME']).sort('STORE_NAME').to_pandas()

stores_pd = get_stores_with_data()
store_options = {str(row['STORE_ID']): str(row['STORE_NAME']) for _, row in stores_pd.iterrows()}
store_options['ALL'] = "All Corporate Stores (Aggregate)"

# Get existing selection or default to ALL
current_selection_id = st.session_state.get('selected_store_id', 'ALL')
try:
    current_index = list(store_options.keys()).index(current_selection_id)
except ValueError:
    current_index = list(store_options.keys()).index('ALL')

# Selection interface
selected_store_id = st.selectbox(
    "Select Store View:",
    options=list(store_options.keys()),
    format_func=lambda x: f"{store_options[x]} - #{x}" if x != 'ALL' else "All Corporate Stores (Aggregate)",
    index=current_index
)

# Update session state with choice
st.session_state['selected_store_id'] = selected_store_id
st.session_state['selected_store_name'] = store_options[selected_store_id]
store_name = st.session_state['selected_store_name']

st.markdown(f"*(Currently viewing data for: **{store_name}**)*")
# st.info("The data dictionary has been moved to a separate standalone page file and is not linked in the app navigation for now.")
