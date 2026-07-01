import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

def get_sheets_client(credentials_json_str):
    """Authenticates with Google Sheets API and returns a client."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(credentials_json_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def get_sheets_client_from_file(credentials_file_path):
    """Authenticates using a credentials JSON file path."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file_path, scope)
    return gspread.authorize(creds)

def fetch_data_from_sheet(client, spreadsheet_url, worksheet_name, as_records=True):
    """Fetches data from a specific worksheet."""
    try:
        sheet = client.open_by_url(spreadsheet_url)
        worksheet = sheet.worksheet(worksheet_name)
        if as_records:
            data = worksheet.get_all_values()
            if not data:
                return pd.DataFrame()
            
            raw_headers = data[0]
            headers = []
            seen = {}
            for h in raw_headers:
                if h in seen:
                    seen[h] += 1
                    headers.append(f"{h}_{seen[h]}")
                else:
                    seen[h] = 0
                    headers.append(h)
                    
            df = pd.DataFrame(data[1:], columns=headers)
            return df
        else:
            data = worksheet.get_all_values()
            return data
    except Exception as e:
        raise Exception(f"Failed to fetch data from '{worksheet_name}': {str(e)}")
