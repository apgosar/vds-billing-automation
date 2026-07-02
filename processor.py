import pandas as pd
import io
import zipfile

def process_mis_data(mis_df, config_data, target_month, target_year, date_column="Visit Date", bank_column="Bank Name"):
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
                
            logs.append(f"  -> ✅ Success: Found {len(bank_data)} records.")
            output_df = pd.DataFrame(index=bank_data.index)
            
            # Auto-populate Serial Number as the first column
            output_df['Sr No'] = range(1, len(bank_data) + 1)
            
            for conf in configs:
                parts = [p.strip() for p in conf.split(':')]
                bank_col_name = parts[0]
                
                if len(parts) == 1:
                    # Bank Column Name only -> implies same name in MIS
                    mis_col_name = bank_col_name
                    if mis_col_name in bank_data.columns:
                        output_df[bank_col_name] = bank_data[mis_col_name]
                    else:
                        output_df[bank_col_name] = None
                        
                elif len(parts) == 2:
                    if parts[1].lower() == 'blank':
                        output_df[bank_col_name] = None
                    else:
                        mis_col_name = parts[1]
                        if mis_col_name in bank_data.columns:
                            output_df[bank_col_name] = bank_data[mis_col_name]
                        else:
                            output_df[bank_col_name] = None
                            
                elif len(parts) == 3:
                    if parts[1].lower() == 'fixed':
                        fixed_value = parts[2]
                        output_df[bank_col_name] = fixed_value
                    else:
                        # Fallback or unknown format
                        output_df[bank_col_name] = None
            
            # Create Excel file in memory
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter', datetime_format='dd-mm-yyyy') as writer:
                # Write data without header so we can manually style the header
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
                    # Use conditional formatting to apply borders to all cells in the data range
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
            
            excel_buffer.seek(0)
            generated_files.append((bank_name, excel_buffer.getvalue()))
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
