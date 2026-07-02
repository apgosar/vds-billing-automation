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
CONFIG_SPREADSHEET_URL = os.getenv("CONFIG_SPREADSHEET_URL")
CONFIG_TAB_NAME = os.getenv("CONFIG_TAB_NAME", "Configuration")
CUSTOM_RULES_TAB_NAME = os.getenv("CUSTOM_RULES_TAB_NAME", "Custom Rules")
DATE_COLUMN_NAME = os.getenv("DATE_COLUMN_NAME", "Visit Date")
BANK_COLUMN_NAME = os.getenv("BANK_COLUMN_NAME", "Bank Name")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "service_account.json")

st.set_page_config(page_title="MIS Data Extraction", layout="wide")
st.title("MIS Billing Automation")

st.sidebar.header("Data Filters")
now = datetime.datetime.now()
default_month = now.month - 1
default_year = now.year

if default_month == 0:
    default_month = 12
    default_year -= 1

month_index = default_month - 1
year_options = list(range(now.year - 5, now.year + 2))
try:
    year_index = year_options.index(default_year)
except ValueError:
    year_index = 5

target_month = st.sidebar.selectbox("Target Month", range(1, 13), index=month_index, format_func=lambda x: datetime.date(1900, x, 1).strftime('%B'))
target_year = st.sidebar.selectbox("Target Year", year_options, index=year_index)

col1, col2 = st.columns(2)
with col1:
    btn_billing = st.button("Generate Billing Sheets", use_container_width=True)
with col2:
    btn_final = st.button("Generate Final Bills", use_container_width=True)

if btn_billing or btn_final:
    if not SPREADSHEET_URL or SPREADSHEET_URL == "https://docs.google.com/spreadsheets/d/your_spreadsheet_id_here":
        st.error("Please set a valid SPREADSHEET_URL in your environment variables.")
    elif not CONFIG_SPREADSHEET_URL or CONFIG_SPREADSHEET_URL == "https://docs.google.com/spreadsheets/d/your_config_spreadsheet_id_here":
        st.error("Please set a valid CONFIG_SPREADSHEET_URL in your environment variables.")
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
                
                # Fetch Config Data (using get_all_values so it's a list of lists)
                config_data_raw = fetch_data_from_sheet(client, CONFIG_SPREADSHEET_URL, CONFIG_TAB_NAME, as_records=False)
                st.success("Successfully fetched data from Google Sheets.")
                
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                st.stop()
                
        with st.spinner("Processing Data..."):
            try:
                # Parse config sections
                billing_config = []
                final_bill_config = []
                current_section = "BILLING"
                
                for row in config_data_raw:
                    if not row:
                        continue
                    first_col = str(row[0]).strip().upper()
                    if first_col == "[BILLING SHEETS]":
                        current_section = "BILLING"
                        continue
                    elif first_col == "[FINAL BILLS]":
                        current_section = "FINAL"
                        continue
                        
                    if current_section == "BILLING":
                        billing_config.append(row)
                    elif current_section == "FINAL":
                        final_bill_config.append(row)
                        
                # Determine which config to use
                if btn_billing:
                    target_config = billing_config
                    action_name = "Billing Sheets"
                    suffix = "_Billing"
                    zip_name = f"Billing_Sheets_{target_month}_{target_year}.zip"
                else:
                    target_config = final_bill_config
                    action_name = "Final Bills"
                    suffix = "_Final_Bill"
                    zip_name = f"Final_Bills_{target_month}_{target_year}.zip"
                    
                if not target_config:
                    st.warning(f"No configuration found for {action_name}. Ensure you have added rows under the correct marker.")
                else:
                    # 3. Process Data
                    custom_rules_df = pd.DataFrame()
                    try:
                        custom_rules_df = fetch_data_from_sheet(client, CONFIG_SPREADSHEET_URL, CUSTOM_RULES_TAB_NAME, as_records=True)
                    except Exception as e:
                        st.warning(f"Could not load the '{CUSTOM_RULES_TAB_NAME}' tab from Configuration sheet. Ensure the name is exactly matching. ({e})")
                        
                    files, logs = process_mis_data(mis_df, target_config, target_month, target_year, DATE_COLUMN_NAME, BANK_COLUMN_NAME, custom_rules_df)
                    
                    # Show execution logs
                    st.subheader(f"Execution Log: {action_name}")
                    with st.container(border=True):
                        for log in logs:
                            st.text(log)
                            
                    if not files:
                        st.warning("No data found for the given month/year or matching bank configurations.")
                    else:
                        # 4. Create ZIP
                        zip_bytes = create_zip_file(files, suffix=suffix)
                        
                        st.success(f"Successfully generated files for {len(files)} banks!")
                        st.download_button(
                            label=f"⬇️ Download {action_name} as ZIP",
                            data=zip_bytes,
                            file_name=zip_name,
                            mime="application/zip",
                            type="primary"
                        )
                            
            except Exception as e:
                st.error(f"Error processing data: {e}")
