import streamlit as st
import polars as pl
import pandas as pd
import plotly.express as px
import requests
from great_tables import GT
from data_sources import load_reference_stores

store_id = st.session_state.get('selected_store_id', 'ALL')
store_name = st.session_state.get('selected_store_name', 'All Corporate Stores (Aggregate)')

st.title("Store Demographics Profiler")

# --- CALCULATIONS ---

# Define the 11 Census Variables and their human-readable labels
CENSUS_VARS = {
    'B01003_001E': 'Total Population',
    'B01002_001E': 'Median Age',
    'B19013_001E': 'Median Household Income ($)',
    'B25077_001E': 'Median Home Value ($)',
    'B25003_002E': 'Owner Occupied Homes',
    'B25003_003E': 'Renter Occupied Homes',
    'B02001_002E': 'Pop - White',
    'B02001_003E': 'Pop - Black / African American',
    'B02001_004E': 'Pop - Native American',
    'B02001_005E': 'Pop - Asian',
    'B03002_012E': 'Pop - Hispanic/Latino',
    'B15003_001E': 'Education Population 25+',
    'B15003_017E': 'Education - High School Graduate',
    'B15003_022E': "Education - Bachelor's Degree",
    'B15003_023E': "Education - Master's Degree",
    'B15003_024E': 'Education - Professional School Degree',
    'B15003_025E': 'Education - Doctorate Degree',
    'B23025_001E': 'Employment Population 16+',
    'B23025_002E': 'Employment - In Labor Force',
    'B23025_003E': 'Employment - Employed',
    'B23025_005E': 'Employment - Unemployed',
    'B23025_007E': 'Employment - Not in Labor Force'
}


@st.cache_data
def load_store_locations():
    # Load the subset of stores that have valid geographic boundaries to map
    valid_ids = ['31631', '31632', '18191', '25255', '19075', '6385']
    df_stores = (
        load_reference_stores()
        .filter(pl.col('STORE_ID').cast(pl.Utf8).is_in(valid_ids))
        .drop_nulls(['LATITUDE', 'LONGITUDE', 'ZIP_CODE'])
    )
    
    # Pre-format Zip Codes nicely since they are sometimes parsed back as floats
    df_pd = df_stores.to_pandas()
    df_pd['STORE_ID'] = df_pd['STORE_ID'].astype(str)
    df_pd['ZIP_CODE'] = df_pd['ZIP_CODE'].astype(str).str.split('.').str[0].str.zfill(5)
    
    # Create a nice label format 
    df_pd['StoreLabel'] = df_pd['STORE_NAME'] + " (Zip: " + df_pd['ZIP_CODE'] + ")"
    return df_pd

stores_df = load_store_locations()

# Global-style store selector (same behavior pattern as data dictionary page)
st.markdown("### 🏪 Store Selection")
store_options_df = (
    stores_df[['STORE_ID', 'STORE_NAME']]
    .drop_duplicates()
    .sort_values('STORE_NAME')
)
store_options = {str(row['STORE_ID']): str(row['STORE_NAME']) for _, row in store_options_df.iterrows()}
store_options['ALL'] = "All Corporate Stores (Aggregate)"

current_selection_id = st.session_state.get('selected_store_id', 'ALL')
try:
    current_index = list(store_options.keys()).index(current_selection_id)
except ValueError:
    current_index = list(store_options.keys()).index('ALL')

selected_store_id = st.selectbox(
    "Select Store View:",
    options=list(store_options.keys()),
    format_func=lambda x: f"{store_options[x]} - #{x}" if x != 'ALL' else "All Corporate Stores (Aggregate)",
    index=current_index
)

st.session_state['selected_store_id'] = selected_store_id
st.session_state['selected_store_name'] = store_options[selected_store_id]
store_id = selected_store_id
store_name = st.session_state['selected_store_name']

st.markdown(f"*(Currently viewing data for: **{store_name}**)*")

@st.cache_data
def get_store_geography(lat, lon):
    geo_url = (
        "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
        f"?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json"
    )

    try:
        response = requests.get(geo_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            geos = data.get("result", {}).get("geographies", {})
            counties = geos.get("Counties", [])
            states = geos.get("States", [])

            county = counties[0] if counties else {}
            state = states[0] if states else {}

            return {
                "state_fips": state.get("STATE"),
                "state_name": state.get("BASENAME"),
                "county_fips": county.get("COUNTY"),
                "county_name": county.get("BASENAME")
            }
    except Exception:
        pass

    return {
        "state_fips": None,
        "state_name": None,
        "county_fips": None,
        "county_name": None
    }


@st.cache_data
def fetch_census_data(geography_scope, zip_code, state_fips, county_fips, api_key):
    var_keys = ",".join(CENSUS_VARS.keys())

    if geography_scope == "Store County":
        if not (state_fips and county_fips):
            return {label: None for label in CENSUS_VARS.values()}
        geo_query = f"for=county:{county_fips}&in=state:{state_fips}"
    elif geography_scope == "Store State":
        if not state_fips:
            return {label: None for label in CENSUS_VARS.values()}
        geo_query = f"for=state:{state_fips}"
    else:
        geo_query = f"for=zip%20code%20tabulation%20area:{zip_code}"

    # Retrieve ACS 5-year estimates for selected geography
    url = f"https://api.census.gov/data/2022/acs/acs5?get={var_keys}&{geo_query}&key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1:
                values = data[1][:-1]  # Exclude the zip code column label at the end
                
                parsed_values = {}
                for (code, label), val in zip(CENSUS_VARS.items(), values):
                    try:
                        v = float(val)
                        # API indicates missing/nulls natively with heavy negative values (-666666666.0)
                        parsed_values[label] = v if v > -1000000 else None
                    except:
                        parsed_values[label] = None
                return parsed_values
    except Exception as e:
        st.warning("Failed to fetch Census data. API rate bounds or network issue.")
        pass
    
    return {label: None for label in CENSUS_VARS.values()}


# --- UI LAYOUT ---

st.markdown("""
### Local Community Demographic Comparison
Provide the owners of the stores with detailed records and a comparison of customer demographics within a specified area around their store using the **live US Census API (ACS 5-Year Estimates)**.
Compare at least 10 unique variables including Income, Age, and varying demographic compositions surrounding each store location (by Zip Code).
""")

if 'census_api_key' not in st.session_state:
    st.session_state['census_api_key'] = ""

@st.dialog("Enter US Census API Key")
def census_api_key_dialog():
    st.write("Provide a valid Census API key to fetch live ACS demographics.")
    entered_key = st.text_input("Census API Key", type="password", key="census_api_key_input")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Key", use_container_width=True):
            st.session_state['census_api_key'] = entered_key.strip()
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

user_api_key = st.session_state.get('census_api_key', "")

if not user_api_key:
    st.warning("Please enter a Census API Key to view the demographics data.")
    if st.button("Enter Census API Key"):
        census_api_key_dialog()
else:
    st.success("Census API key loaded.")
    if st.button("Update Census API Key"):
        census_api_key_dialog()

    geography_scope = st.selectbox(
        "Area scope to analyze around each store:",
        options=["Store ZIP Code", "Store County", "Store State"],
        help="ZIP = immediate local area, County = broader local market, State = macro benchmark."
    )

    # Section: Demographic analysis for selected store area
    st.subheader("📊 Demographics by Area Around Selected Store")
    st.write("Choose an area scope to fetch ACS Census data around the currently selected store.")

    if store_id != 'ALL' and store_id in stores_df['STORE_ID'].values:
        with st.spinner("Fetching live metrics from US Census API..."):
            all_store_data = []

            store_row = stores_df[stores_df['STORE_ID'] == store_id].iloc[0]
            store_label = store_row['StoreLabel']
            zip_code = store_row['ZIP_CODE']

            store_geo = get_store_geography(store_row['LATITUDE'], store_row['LONGITUDE'])

            demo_data = fetch_census_data(
                geography_scope,
                zip_code,
                store_geo['state_fips'],
                store_geo['county_fips'],
                user_api_key
            )

            if geography_scope == "Store County":
                area_label = store_geo['county_name'] or "Unknown County"
            elif geography_scope == "Store State":
                area_label = store_geo['state_name'] or "Unknown State"
            else:
                area_label = f"ZIP {zip_code}"

            demo_record = {
                **demo_data,
                'Store': store_label,
                'Area Scope': geography_scope,
                'Area Used': area_label
            }
            all_store_data.append(demo_record)
                
            # 1. Transform raw dict list into tabular output
            demo_flat = pd.DataFrame(all_store_data)
            
            # KPI Header
            c1, c2, c3 = st.columns(3)
            med_inc_val = demo_flat['Median Household Income ($)'].iloc[0] if 'Median Household Income ($)' in demo_flat.columns else 0
            med_age_val = demo_flat['Median Age'].iloc[0] if 'Median Age' in demo_flat.columns else 0
            tot_pop_val = demo_flat['Total Population'].iloc[0] if 'Total Population' in demo_flat.columns else 0
            
            c1.metric("Median Income", f"${med_inc_val:,.0f}", help="Median household income in the selected area")
            c2.metric("Median Age", f"{med_age_val:,.1f}", help="Median age in the selected area")
            c3.metric("Total Population", f"{tot_pop_val:,.0f}", help="Population in the selected area")
            
            # Prepare transposed ACS data table (displayed at end of page)
            demo_table_source = demo_flat.drop(columns=['Area Scope', 'Area Used'], errors='ignore')
            demo_table = demo_table_source.set_index('Store').T
            demo_table_reset = demo_table.reset_index().rename(columns={"index": "Demographic Variable"})

            table_scope = demo_flat['Area Scope'].iloc[0] if 'Area Scope' in demo_flat.columns else geography_scope
            table_area = demo_flat['Area Used'].iloc[0] if 'Area Used' in demo_flat.columns else "Unknown Area"

            st.divider()
            st.subheader("Population Composition")
            total_pop = float(demo_flat['Total Population'].iloc[0]) if 'Total Population' in demo_flat.columns and pd.notna(demo_flat['Total Population'].iloc[0]) else 0
            pop_rows = [
                ('White', float(demo_flat['Pop - White'].iloc[0]) if 'Pop - White' in demo_flat.columns and pd.notna(demo_flat['Pop - White'].iloc[0]) else 0),
                ('Black / African American', float(demo_flat['Pop - Black / African American'].iloc[0]) if 'Pop - Black / African American' in demo_flat.columns and pd.notna(demo_flat['Pop - Black / African American'].iloc[0]) else 0),
                ('Native American', float(demo_flat['Pop - Native American'].iloc[0]) if 'Pop - Native American' in demo_flat.columns and pd.notna(demo_flat['Pop - Native American'].iloc[0]) else 0),
                ('Asian', float(demo_flat['Pop - Asian'].iloc[0]) if 'Pop - Asian' in demo_flat.columns and pd.notna(demo_flat['Pop - Asian'].iloc[0]) else 0),
                ('Hispanic/Latino', float(demo_flat['Pop - Hispanic/Latino'].iloc[0]) if 'Pop - Hispanic/Latino' in demo_flat.columns and pd.notna(demo_flat['Pop - Hispanic/Latino'].iloc[0]) else 0),
            ]
            pop_comp_df = pd.DataFrame(pop_rows, columns=['Group', 'Population'])
            pop_comp_df['Share (%)'] = (pop_comp_df['Population'] / total_pop * 100) if total_pop else 0

            col1, col2 = st.columns(2)
            with col1:
                fig_pop_share = px.bar(
                    pop_comp_df,
                    x='Group',
                    y='Share (%)',
                    color='Group',
                    title='Population Share by Group'
                )
                st.plotly_chart(fig_pop_share, width='stretch')

            with col2:
                fig_pop_count = px.bar(
                    pop_comp_df,
                    x='Group',
                    y='Population',
                    color='Group',
                    title='Population Count by Group'
                )
                st.plotly_chart(fig_pop_count, width='stretch')

            st.divider()
            st.subheader("Housing Occupancy Mix")
            owner_count = float(demo_flat['Owner Occupied Homes'].iloc[0]) if 'Owner Occupied Homes' in demo_flat.columns and pd.notna(demo_flat['Owner Occupied Homes'].iloc[0]) else 0
            renter_count = float(demo_flat['Renter Occupied Homes'].iloc[0]) if 'Renter Occupied Homes' in demo_flat.columns and pd.notna(demo_flat['Renter Occupied Homes'].iloc[0]) else 0
            housing_df = pd.DataFrame({
                'Occupancy': ['Owner Occupied', 'Renter Occupied'],
                'Homes': [owner_count, renter_count]
            })
            fig_housing = px.pie(
                housing_df,
                names='Occupancy',
                values='Homes',
                title='Owner vs Renter Occupied Homes',
                hole=0.45
            )
            st.plotly_chart(fig_housing, width='stretch')

            st.divider()
            st.subheader("Economic Snapshot")
            econ_df = pd.DataFrame({
                'Metric': ['Median Household Income ($)', 'Median Home Value ($)'],
                'Value': [
                    float(demo_flat['Median Household Income ($)'].iloc[0]) if 'Median Household Income ($)' in demo_flat.columns and pd.notna(demo_flat['Median Household Income ($)'].iloc[0]) else 0,
                    float(demo_flat['Median Home Value ($)'].iloc[0]) if 'Median Home Value ($)' in demo_flat.columns and pd.notna(demo_flat['Median Home Value ($)'].iloc[0]) else 0
                ]
            })
            fig_econ = px.bar(
                econ_df,
                x='Metric',
                y='Value',
                color='Metric',
                title='Income and Home Value Indicators'
            )
            st.plotly_chart(fig_econ, width='stretch')

            st.divider()
            st.subheader("Education & Employment Status")

            edu_pop_25 = float(demo_flat['Education Population 25+'].iloc[0]) if 'Education Population 25+' in demo_flat.columns and pd.notna(demo_flat['Education Population 25+'].iloc[0]) else 0
            hs_grad = float(demo_flat['Education - High School Graduate'].iloc[0]) if 'Education - High School Graduate' in demo_flat.columns and pd.notna(demo_flat['Education - High School Graduate'].iloc[0]) else 0
            bachelors_plus = (
                float(demo_flat["Education - Bachelor's Degree"].iloc[0]) if "Education - Bachelor's Degree" in demo_flat.columns and pd.notna(demo_flat["Education - Bachelor's Degree"].iloc[0]) else 0
            ) + (
                float(demo_flat["Education - Master's Degree"].iloc[0]) if "Education - Master's Degree" in demo_flat.columns and pd.notna(demo_flat["Education - Master's Degree"].iloc[0]) else 0
            ) + (
                float(demo_flat['Education - Professional School Degree'].iloc[0]) if 'Education - Professional School Degree' in demo_flat.columns and pd.notna(demo_flat['Education - Professional School Degree'].iloc[0]) else 0
            ) + (
                float(demo_flat['Education - Doctorate Degree'].iloc[0]) if 'Education - Doctorate Degree' in demo_flat.columns and pd.notna(demo_flat['Education - Doctorate Degree'].iloc[0]) else 0
            )

            emp_pop_16 = float(demo_flat['Employment Population 16+'].iloc[0]) if 'Employment Population 16+' in demo_flat.columns and pd.notna(demo_flat['Employment Population 16+'].iloc[0]) else 0
            labor_force = float(demo_flat['Employment - In Labor Force'].iloc[0]) if 'Employment - In Labor Force' in demo_flat.columns and pd.notna(demo_flat['Employment - In Labor Force'].iloc[0]) else 0
            employed = float(demo_flat['Employment - Employed'].iloc[0]) if 'Employment - Employed' in demo_flat.columns and pd.notna(demo_flat['Employment - Employed'].iloc[0]) else 0
            unemployed = float(demo_flat['Employment - Unemployed'].iloc[0]) if 'Employment - Unemployed' in demo_flat.columns and pd.notna(demo_flat['Employment - Unemployed'].iloc[0]) else 0
            not_in_labor_force = float(demo_flat['Employment - Not in Labor Force'].iloc[0]) if 'Employment - Not in Labor Force' in demo_flat.columns and pd.notna(demo_flat['Employment - Not in Labor Force'].iloc[0]) else 0

            hs_grad_share = (hs_grad / edu_pop_25 * 100) if edu_pop_25 else 0
            bachelors = float(demo_flat["Education - Bachelor's Degree"].iloc[0]) if "Education - Bachelor's Degree" in demo_flat.columns and pd.notna(demo_flat["Education - Bachelor's Degree"].iloc[0]) else 0
            masters = float(demo_flat["Education - Master's Degree"].iloc[0]) if "Education - Master's Degree" in demo_flat.columns and pd.notna(demo_flat["Education - Master's Degree"].iloc[0]) else 0
            professional = float(demo_flat['Education - Professional School Degree'].iloc[0]) if 'Education - Professional School Degree' in demo_flat.columns and pd.notna(demo_flat['Education - Professional School Degree'].iloc[0]) else 0
            doctorate = float(demo_flat['Education - Doctorate Degree'].iloc[0]) if 'Education - Doctorate Degree' in demo_flat.columns and pd.notna(demo_flat['Education - Doctorate Degree'].iloc[0]) else 0

            bachelors_share = (bachelors / edu_pop_25 * 100) if edu_pop_25 else 0
            masters_share = (masters / edu_pop_25 * 100) if edu_pop_25 else 0
            professional_share = (professional / edu_pop_25 * 100) if edu_pop_25 else 0
            doctorate_share = (doctorate / edu_pop_25 * 100) if edu_pop_25 else 0
            advanced_degree_share = ((masters + professional + doctorate) / edu_pop_25 * 100) if edu_pop_25 else 0
            bachelors_plus_share = (bachelors_plus / edu_pop_25 * 100) if edu_pop_25 else 0
            labor_participation = (labor_force / emp_pop_16 * 100) if emp_pop_16 else 0
            employed_share_16 = (employed / emp_pop_16 * 100) if emp_pop_16 else 0
            unemployed_share_16 = (unemployed / emp_pop_16 * 100) if emp_pop_16 else 0
            not_in_labor_force_share_16 = (not_in_labor_force / emp_pop_16 * 100) if emp_pop_16 else 0

            e1, e2, e3 = st.columns(3)
            e1.metric("HS Graduate Share (25+)", f"{hs_grad_share:.1f}%")
            e2.metric("Bachelor's+ Share (25+)", f"{bachelors_plus_share:.1f}%")
            e3.metric("Labor Participation", f"{labor_participation:.1f}%")

            education_df = pd.DataFrame({
                'Metric': [
                    'HS Graduate Share (25+)',
                    "Bachelor's Share (25+)",
                    "Master's Share (25+)",
                    'Professional Degree Share (25+)',
                    'Doctorate Share (25+)',
                    "Bachelor's+ Share (25+)",
                    'Advanced Degree Share (25+)'
                ],
                'Percent': [
                    hs_grad_share,
                    bachelors_share,
                    masters_share,
                    professional_share,
                    doctorate_share,
                    bachelors_plus_share,
                    advanced_degree_share
                ]
            })
            fig_edu = px.bar(
                education_df,
                x='Metric',
                y='Percent',
                color='Metric',
                title='Educational Attainment Snapshot (Population 25+)'
            )
            st.plotly_chart(fig_edu, width='stretch')

            employment_df = pd.DataFrame({
                'Metric': ['Employed Share (16+)', 'Unemployed Share (16+)', 'Not In Labor Force Share (16+)'],
                'Percent': [
                    employed_share_16,
                    unemployed_share_16,
                    not_in_labor_force_share_16
                ]
            })
            fig_emp = px.bar(
                employment_df,
                x='Metric',
                y='Percent',
                color='Metric',
                title='Employment Status Snapshot (Population 16+)'
            )
            st.plotly_chart(fig_emp, width='stretch')

            st.divider()
            st.subheader("Summary Table")
            gt_demo = GT(demo_table_reset).tab_header(
                title="Census Variable Comparison",
                subtitle=f"Compiled dynamically from US Census REST API | Scope: {table_scope} | Area: {table_area}"
            ).cols_align(align="center")
            st.html(gt_demo.as_raw_html())
    else:
        st.info("Select a specific store in the global store selector to view demographics for that location.")

st.divider()
with st.expander("🖥️ Logic and Code"):
    st.markdown("""
    This page fetches live ACS 5-year Census metrics for the selected store geography and visualizes population, housing, income, education, and employment.

    The workflow is: map store to ZIP/county/state, request ACS variables in one call, compute percentage-based education/employment indicators, and render the transposed ACS summary table at the end.
    """)
    st.code("""
# 0. Resolve selected store geography
stores_df = load_store_locations()
store_row = stores_df[stores_df['STORE_ID'] == store_id].iloc[0]
store_geo = get_store_geography(store_row['LATITUDE'], store_row['LONGITUDE'])

# 1. Fetch ACS values for selected scope
acs_values = fetch_census_data(
    geography_scope,
    zip_code=store_row['ZIP_CODE'],
    state_fips=store_geo['state_fips'],
    county_fips=store_geo['county_fips'],
    api_key=user_api_key,
)

# 2. Build dataframe and derive percentages
# Education percentages use population 25+
hs_grad_share = hs_grad / edu_pop_25 * 100 if edu_pop_25 else 0
bachelors_plus_share = bachelors_plus / edu_pop_25 * 100 if edu_pop_25 else 0

# Employment percentages use population 16+
employed_share_16 = employed / emp_pop_16 * 100 if emp_pop_16 else 0
unemployed_share_16 = unemployed / emp_pop_16 * 100 if emp_pop_16 else 0
not_in_labor_force_share_16 = not_in_labor_force / emp_pop_16 * 100 if emp_pop_16 else 0

# 3. Render transposed ACS summary table at bottom of page
demo_table = demo_flat.drop(columns=['Area Scope', 'Area Used'], errors='ignore').set_index('Store').T
demo_table_reset = demo_table.reset_index().rename(columns={'index': 'Demographic Variable'})
gt_demo = GT(demo_table_reset).tab_header(title='Census Variable Comparison')
st.html(gt_demo.as_raw_html())
    """, language="python")