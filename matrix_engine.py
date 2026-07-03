import pandas as pd
import re

def match_range(value, range_str):
    """
    Evaluates if a numeric value falls within a string-defined range.
    Supported formats: '0 - 30', '> 60', '>= 60', '< 30', 'Default', 'Other'
    """
    range_str = str(range_str).strip().lower()
    
    if not range_str or range_str in ['default', 'else', 'other', 'any']:
        return True
        
    try:
        val = float(value)
    except (ValueError, TypeError):
        return False
        
    # Check 'A - B'
    match = re.match(r'^([\d\.]+)\s*-\s*([\d\.]+)$', range_str)
    if match:
        a, b = float(match.group(1)), float(match.group(2))
        return a <= val <= b
        
    # Check '>= X' or '> X'
    match = re.match(r'^>=\s*([\d\.]+)$', range_str)
    if match: return val >= float(match.group(1))
    
    match = re.match(r'^>\s*([\d\.]+)$', range_str)
    if match: return val > float(match.group(1))
    
    # Check '<= X' or '< X'
    match = re.match(r'^<=\s*([\d\.]+)$', range_str)
    if match: return val <= float(match.group(1))
    
    match = re.match(r'^<\s*([\d\.]+)$', range_str)
    if match: return val < float(match.group(1))
    
    # Check exact match if it's just a number
    try:
        target = float(range_str)
        return val == target
    except ValueError:
        pass
        
    # String fallback match
    return str(value).strip().lower() == range_str

def parse_cost_matrices(raw_data):
    """
    Parses the Google Sheets nested list format into a structured dictionary.
    Format expects:
    Row 1: [Bank Name, Row_Dim, Col_Dim]
    Row 2: [None, None, Col_Header1, Col_Header2...]
    Row 3: [None, Row_Header1, Val1, Val2...]
    """
    matrices = {}
    current_bank = None
    
    i = 0
    while i < len(raw_data):
        row = raw_data[i]
        if not row:
            i += 1
            continue
            
        # Is this a bank declaration row? (Has value in first column)
        col0 = str(row[0]).strip()
        if col0:
            current_bank = col0
            row_col_name = str(row[1]).strip() if len(row) > 1 else ""
            col_col_name = str(row[2]).strip() if len(row) > 2 else ""
            
            # Next row should be headers
            i += 1
            if i < len(raw_data):
                header_row = raw_data[i]
                # Headers start from index 2
                col_headers = [str(c).strip() for c in header_row[2:]] if len(header_row) > 2 else []
                
                matrices[current_bank] = {
                    'row_col': row_col_name,
                    'col_col': col_col_name,
                    'col_headers': col_headers,
                    'data': {}
                }
        elif current_bank:
            # This is a data row for the current bank
            row_name = str(row[1]).strip() if len(row) > 1 else ""
            if row_name:
                values = [str(c).strip() for c in row[2:]] if len(row) > 2 else []
                # Pad values to match header length
                col_headers = matrices[current_bank]['col_headers']
                while len(values) < len(col_headers):
                    values.append("")
                    
                matrices[current_bank]['data'][row_name.upper()] = values
                
        i += 1
        
    return matrices

def evaluate_matrix(df, matrix_def, amount_col_name='Amount'):
    """
    Evaluates the dataframe using the parsed matrix definition.
    Injects 'Amount' column. Missing matches default to 0.
    """
    row_col = matrix_def['row_col']
    col_col = matrix_def['col_col']
    col_headers = matrix_def['col_headers']
    data = matrix_def['data']
    
    # Initialize Amount column with 0
    df[amount_col_name] = 0
    
    if row_col not in df.columns or col_col not in df.columns:
        return df, [f"⚠️ Missing required columns: '{row_col}' or '{col_col}' in uploaded file."]
        
    logs = [f"Evaluating matrix using Row: '{row_col}', Col: '{col_col}'"]
    match_count = 0
    
    for idx, df_row in df.iterrows():
        r_val = str(df_row[row_col]).strip().upper()
        c_val = df_row[col_col]
        
        # 1. Match Row
        if r_val in data:
            row_amounts = data[r_val]
            
            # 2. Match Column Bucket
            matched_amount = 0
            for col_idx, header in enumerate(col_headers):
                if match_range(c_val, header):
                    # We found the bucket!
                    amt_str = row_amounts[col_idx]
                    try:
                        matched_amount = float(amt_str)
                    except ValueError:
                        matched_amount = 0
                    break
                    
            if matched_amount > 0:
                df.at[idx, amount_col_name] = matched_amount
                match_count += 1
                
    logs.append(f"Successfully applied matrix pricing to {match_count} rows.")
    return df, logs
