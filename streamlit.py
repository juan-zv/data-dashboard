import streamlit as st

# Define the pages
data_dict_page = st.Page("landing.py", title="Data Dictionary & Landing", icon="🏠")
page_2 = st.Page("top_five.py", title="Top Five", icon="🏆")
page_3 = st.Page("beverages.py", title="Beverages", icon="🥤")
page_4 = st.Page("cash_credit.py", title="Cash & Credit", icon="💳")
page_5 = st.Page("demographics.py", title="Demographics", icon="🗺️")

# Set up navigation
pg = st.navigation([data_dict_page, page_2, page_3, page_4, page_5])

# Run the selected page
pg.run()
