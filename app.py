import streamlit as st
import pandas as pd
from sheets_api import get_sheets_client_from_file, fetch_data_from_sheet
from processor import process_mis_data, create_zip_file
import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SPREADSHEET_URL = os.getenv("SPREADSHEET_URL")
MIS_TAB_NAME = os.getenv("MIS_TAB_NAME", "MIS")
CONFIG_TAB_NAME = os.getenv("CONFIG_TAB_NAME", "Configuration")
DATE_COLUMN_NAME = os.getenv("DATE_COLUMN_NAME", "Visit Date")
BANK_COLUMN_NAME = os.getenv("BANK_COLUMN_NAME", "Bank Name")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "service_account.json")

st.set_page_config(page_title="MIS Data Extraction", layout="wide")
st.title("MIS Billing Automation")

st.sidebar.header("Data Filters")
current_year = datetime.datetime.now().year
target_month = st.sidebar.selectbox("Target Month", range(1, 13), format_func=lambda x: datetime.date(1900, x, 1).strftime('%B'))
target_year = st.sidebar.selectbox("Target Year", range(current_year - 5, current_year + 2), index=5)

if st.button("Generate Billing Sheets"):
    if not SPREADSHEET_URL or SPREADSHEET_URL == "https://docs.google.com/spreadsheets/d/your_spreadsheet_id_here":
        st.error("Please set a valid SPREADSHEET_URL in your environment variables.")
    elif not GOOGLE_CREDENTIALS_JSON and not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        st.error(f"Credentials not found. Please set GOOGLE_CREDENTIALS_JSON or provide the file at: '{GOOGLE_CREDENTIALS_PATH}'.")
    else:
        with st.spinner("Authenticating and Fetching Data..."):
            try:
                # 1. Authenticate using JSON string or file path
                if GOOGLE_CREDENTIALS_JSON:
                    from sheets_api import get_sheets_client
                    client = get_sheets_client(GOOGLE_CREDENTIALS_JSON)
                else:
                    client = get_sheets_client_from_file(GOOGLE_CREDENTIALS_PATH)
                
                # 2. Fetch Data
                mis_df = fetch_data_from_sheet(client, SPREADSHEET_URL, MIS_TAB_NAME, as_records=True)
                config_data = fetch_data_from_sheet(client, SPREADSHEET_URL, CONFIG_TAB_NAME, as_records=False)
                st.success("Successfully fetched data from Google Sheets.")
                
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                st.stop()
                
        with st.spinner("Processing Data..."):
            try:
                # 3. Process Data
                files, logs = process_mis_data(mis_df, config_data, target_month, target_year, DATE_COLUMN_NAME, BANK_COLUMN_NAME)
                
                # Show execution logs
                st.subheader("Execution Log")
                with st.container(border=True):
                    for log in logs:
                        st.text(log)
                        
                if not files:
                    st.warning("No data found for the given month/year or matching bank configurations.")
                else:
                    # 4. Create ZIP
                    zip_bytes = create_zip_file(files)
                    
                    st.success(f"Successfully generated files for {len(files)} banks!")
                    st.download_button(
                        label="⬇️ Download All as ZIP",
                        data=zip_bytes,
                        file_name=f"Billing_Sheets_{target_month}_{target_year}.zip",
                        mime="application/zip",
                        type="primary"
                    )
                            
            except Exception as e:
                st.error(f"Error processing data: {e}")
