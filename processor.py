import pandas as pd
import io
import zipfile

def process_mis_data(mis_df, config_data, target_month, target_year, date_column="Visit Date", bank_column="Bank Name", custom_rules_df=None):
    """
    Processes the MIS data based on the configuration and filters by month/year.
    config_data is a list of lists representing rows in the config sheet.
    Returns a list of tuples: (bank_name, excel_bytes)
    """
    # Filter out empty rows if any
    mis_df = mis_df.dropna(how='all')

    # Filter by Month and Year
    if date_column in mis_df.columns:
        # Try converting to datetime
        mis_df[date_column] = pd.to_datetime(mis_df[date_column], errors='coerce', dayfirst=True)
        # Filter
        mask = (mis_df[date_column].dt.month == target_month) & (mis_df[date_column].dt.year == target_year)
        filtered_df = mis_df[mask]
    else:
        filtered_df = mis_df

    generated_files = []
    logs = []
    
    # Iterate through configuration
    for row in config_data:
        if not row:
            continue
            
        # The first column is the bank name
        bank_name = str(row[0]).strip()
        if not bank_name:
            continue
            
        logs.append(f"Processing Bank: '{bank_name}'...")
        # The rest of the columns are configs
        configs = [str(c).strip() for c in row[1:] if str(c).strip()]
        
        # Filter MIS data for this bank
        if bank_column in filtered_df.columns:
            bank_data = filtered_df[filtered_df[bank_column].astype(str).str.strip() == bank_name].copy()
            
            if bank_data.empty:
                logs.append(f"  -> ❌ Skipped: No records found for '{bank_name}' in this month/year.")
                continue
                
            # --- CUSTOM RULES ENGINE ---
            if custom_rules_df is not None and not custom_rules_df.empty:
                # Filter rules for this specific bank
                bank_rules = custom_rules_df[custom_rules_df['Bank Name'].astype(str).str.strip() == bank_name]
                
                for _, rule in bank_rules.iterrows():
                    target_col = str(rule.get('Target Column', '')).strip()
                    condition_col = str(rule.get('Condition Column', '')).strip()
                    condition_val = str(rule.get('Condition Value', '')).strip()
                    result_val = str(rule.get('Result Value', '')).strip()
                    fallback_val = str(rule.get('Fallback Value', '')).strip()
                    
                    if not target_col or not condition_col:
                        continue
                        
                    # Initialize the target column with fallback value if it doesn't exist yet
                    if target_col not in bank_data.columns:
                        bank_data[target_col] = fallback_val
                        
                    # Apply the condition
                    if condition_col in bank_data.columns:
                        mask = bank_data[condition_col].astype(str).str.strip() == condition_val
                        bank_data.loc[mask, target_col] = result_val
            # ---------------------------

            logs.append(f"  -> ✅ Success: Found {len(bank_data)} records.")
            
            # Parse configs once for this bank
            parsed_configs = []
            split_mis_col_name = None
            
            for conf in configs:
                parts = [p.strip() for p in conf.split(':')]
                
                is_highlight = False
                is_number = False
                is_split = False
                
                while len(parts) > 1:
                    last_flag = parts[-1].lower()
                    if last_flag == 'highlight':
                        is_highlight = True
                        parts.pop()
                    elif last_flag == 'number':
                        is_number = True
                        parts.pop()
                    elif last_flag == 'split':
                        is_split = True
                        parts.pop()
                    else:
                        break
                        
                if is_split:
                    if len(parts) == 1:
                        split_mis_col_name = parts[0]
                    elif len(parts) >= 2:
                        split_mis_col_name = parts[1]
                    continue # Skip adding split column to actual output
                else:
                    parsed_configs.append({
                        'parts': parts,
                        'is_highlight': is_highlight,
                        'is_number': is_number
                    })
            
            # Determine groups based on Split flag
            groups = []
            if split_mis_col_name and split_mis_col_name in bank_data.columns:
                for group_name, group_data in bank_data.groupby(split_mis_col_name):
                    groups.append((group_name, group_data))
            else:
                groups.append(("", bank_data))
                
            for group_name, group_data in groups:
                output_df = pd.DataFrame(index=group_data.index)
                
                # Auto-populate Serial Number as the first column
                output_df['Sr No'] = range(1, len(group_data) + 1)
                
                columns_to_highlight = set()
                
                for p_conf in parsed_configs:
                    parts = p_conf['parts']
                    is_highlight = p_conf['is_highlight']
                    is_number = p_conf['is_number']
                    
                    bank_col_name = parts[0]
                    if is_highlight:
                        columns_to_highlight.add(bank_col_name)
                        
                    if len(parts) == 1:
                        mis_col_name = bank_col_name
                        if mis_col_name in group_data.columns:
                            output_df[bank_col_name] = group_data[mis_col_name]
                        else:
                            output_df[bank_col_name] = None
                    elif len(parts) == 2:
                        if parts[1].lower() == 'blank':
                            output_df[bank_col_name] = None
                        else:
                            mis_col_name = parts[1]
                            if mis_col_name in group_data.columns:
                                output_df[bank_col_name] = group_data[mis_col_name]
                            else:
                                output_df[bank_col_name] = None
                    elif len(parts) == 3:
                        if parts[1].lower() == 'fixed':
                            output_df[bank_col_name] = parts[2]
                        else:
                            output_df[bank_col_name] = None
                            
                    # Apply numeric conversion if requested
                    if is_number and bank_col_name in output_df.columns:
                        series = output_df[bank_col_name].astype(str).str.replace(',', '', regex=False)
                        series = series.replace({'None': pd.NA, 'nan': pd.NA})
                        output_df[bank_col_name] = pd.to_numeric(series, errors='coerce')
                
                # Create Excel file in memory
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter', datetime_format='dd-mm-yyyy') as writer:
                    output_df.to_excel(writer, index=False, header=False, startrow=1, sheet_name='Billing Data')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Billing Data']
                    
                    # Format Header
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#9BC2E6',
                        'border': 1,
                        'valign': 'vcenter'
                    })
                    worksheet.set_row(0, 35)
                    for col_idx, col_name in enumerate(output_df.columns):
                        worksheet.write(0, col_idx, col_name, header_format)
                        
                    # Format Data Borders
                    if not output_df.empty:
                        border_format = workbook.add_format({'border': 1})
                        worksheet.conditional_format(1, 0, len(output_df), len(output_df.columns) - 1,
                                                     {'type': 'no_blanks', 'format': border_format})
                        worksheet.conditional_format(1, 0, len(output_df), len(output_df.columns) - 1,
                                                     {'type': 'blanks', 'format': border_format})
                    
                    wrap_format = workbook.add_format({'text_wrap': True})
                    
                    for col_idx, col_name in enumerate(output_df.columns):
                        if str(col_name).strip() in ["Property Address", "Address"]:
                            worksheet.set_column(col_idx, col_idx, 40, wrap_format)
                        else:
                            max_len = len(str(col_name))
                            if not output_df.empty:
                                col_max_len = output_df[col_name].astype(str).str.len().max()
                                if pd.notna(col_max_len):
                                    max_len = max(max_len, col_max_len)
                            
                            adjusted_width = max_len + 2
                            if adjusted_width > 60:
                                adjusted_width = 60
                                
                            worksheet.set_column(col_idx, col_idx, adjusted_width)
                            
                    # Apply conditional formatting for duplicates
                    duplicate_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                    if not output_df.empty:
                        for col_idx, col_name in enumerate(output_df.columns):
                            if str(col_name).strip() in columns_to_highlight:
                                worksheet.conditional_format(1, col_idx, len(output_df), col_idx,
                                                             {'type': 'duplicate', 'format': duplicate_format})
                
                excel_buffer.seek(0)
                if group_name:
                    final_bank_name = f"{bank_name}_{str(group_name).strip()}"
                else:
                    final_bank_name = bank_name
                generated_files.append((final_bank_name, excel_buffer.getvalue()))
        else:
            logs.append(f"  -> ❌ Error: The MIS sheet is missing the '{bank_column}' column.")
            
    return generated_files, logs

def create_zip_file(files, suffix="_Billing"):
    """
    Creates a ZIP file containing the generated Excel files.
    files: list of tuples (bank_name, excel_bytes)
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for bank_name, excel_bytes in files:
            # Clean bank name for filename
            clean_bank_name = "".join([c for c in bank_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            filename = f"{clean_bank_name}{suffix}.xlsx"
            zip_file.writestr(filename, excel_bytes)
            
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
