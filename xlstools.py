import pandas as pd
import re
import os
import configparser
# requirements:
# pip install wheel
# pip install pandas
# pip install xlrd

# print("Current Working Directory:", os.getcwd())
sourcedir = r'P:\git\nc_aufmass'
replacestr = "-"

def load_replacements(sourcedir):
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str  # Read the values case-sensitive
    with open(sourcedir + r'\aufmass.ini', encoding='utf-8') as f:
        config.read_file(f)    
    replacements = {key: value for key, value in config.items('REPLACEMENTS')}
    return replacements


def parse_xls_to_csv(xls_file, csv_file):

    # Read the XLS file
    df = pd.read_excel(xls_file, skiprows=5)  # Skip the first x rows

    # Sanitize data
    #df = df.applymap(lambda x: "-" if isinstance(x, str) and x.strip() == "" else re.sub(r'\s{2,}', ' ', x).strip() if isinstance(x, str) else x)

    # Convert all entries to strings
    df = df.applymap(lambda x: replacestr if pd.isna(x) else str(x))

    # Replace empty entries with replacestr
    df = df.applymap(lambda x: replacestr if x.strip() == "" else x)

    # Reduce multiple spaces and strip leading and trailing whitespace
    df = df.applymap(lambda x: re.sub(r'\s{2,}', ' ', x))
    df = df.applymap(lambda x: x.strip() if x != " " else x)

    # Step 5: Replace double commas with ,"-
#    df = df.applymap(lambda x: x.replace(',,', ',"-'))
    
    # Replace known abbreviations
    replacements = load_replacements(sourcedir)

    replace_in_columns = ['Beschreibung', 'Kbez']
    for column in replace_in_columns:
        if column in df.columns:
            for old_str, new_str in replacements.items():
                if df[column].str.contains(old_str, na=False).any():
##                    print(df[df[column].str.contains(old_str, na=False)])  # Print matching entries
                    df[column] = df[column].replace(old_str, new_str, regex=True)

    #  Consider only rows where 'Anz' is a number
    df = df[pd.to_numeric(df['Anz'], errors='coerce').notna()]

    # Check for single unique values in 'l1', 'l2', or 'l3'
    if 'l1' in df.columns and 'l2' in df.columns and 'l3' in df.columns:
        # Create a mask for rows where 'd1' has a value and 'd2' and 'd3' contain replacestr
        mask = (df['d1'].notna()) & (df['d2'] == replacestr) & (df['d3'] == replacestr)

        # Sum up l1 columns with Anz for the filtered rows
        if 'l1' in df.columns and 'Anz' in df.columns:
            df['l1'] = pd.to_numeric(df['l1'], errors='coerce')  # Convert l1 to numeric
            df['Anz'] = pd.to_numeric(df['Anz'], errors='coerce')  # Convert Anz to numeric

            # Now perform the multiplication only on the rows that match the mask
            df.loc[mask, 'l1'] = df.loc[mask, 'l1'] * df.loc[mask, 'Anz']
            # Set 'Anz' to 1 only for those rows where 'l1' has a value
            df.loc[mask & df['l1'].notna(), 'Anz'] = 1  # Set 'Anz' to 1 for those rows with valid 'l1'
       
        # Create a composite key for grouping (Kbez + d1)
        if 'Kbez' in df.columns and 'd1' in df.columns:
            # Convert l1 to numeric first to identify valid numeric values
            if 'l1' in df.columns:
                df['l1'] = pd.to_numeric(df['l1'], errors='coerce')
            
            # Only proceed with rows that have valid numeric l1 values
            df_valid_l1 = df[df['l1'].notna()]
            df_invalid_l1 = df[df['l1'].isna()]
            
            # Convert d1 to string to safely combine (only for valid l1 rows)
            df_valid_l1['d1_str'] = df_valid_l1['d1'].astype(str)
            df_valid_l1['group_key'] = df_valid_l1['Kbez'] + '_' + df_valid_l1['d1_str']
            
            # Get the group_key values that have duplicates
            duplicated_keys = df_valid_l1['group_key'][df_valid_l1['group_key'].duplicated(keep=False)]
            
            # Create mask for rows with duplicate group_keys
            duplicate_mask = df_valid_l1['group_key'].isin(duplicated_keys)
            
            # Keep rows without duplicates
            df_unique = df_valid_l1[~duplicate_mask]
            
            # Create aggregation dictionary
            agg_dict = {
                'l1': 'sum',
                'Anz': 'first',
                'Kbez': 'first',
                'd1': 'first'
            }
            
            # Add 'first' aggregation for all other columns
            for col in df_valid_l1.columns:
                if col not in agg_dict and col != 'group_key' and col != 'd1_str':
                    agg_dict[col] = 'first'
            
            # Aggregate only the duplicate rows
            df_agg = df_valid_l1[duplicate_mask].groupby('group_key', as_index=False).agg(agg_dict)
            
            # Drop the temporary columns from both dataframes
            if 'group_key' in df_unique.columns and 'd1_str' in df_unique.columns:
                df_unique = df_unique.drop(['group_key', 'd1_str'], axis=1)
            elif 'group_key' in df_unique.columns:
                df_unique = df_unique.drop(['group_key'], axis=1)
                
            if 'group_key' in df_agg.columns and 'd1_str' in df_agg.columns:
                df_agg = df_agg.drop(['group_key', 'd1_str'], axis=1)
            elif 'group_key' in df_agg.columns:
                df_agg = df_agg.drop(['group_key'], axis=1)
            
            # Combine unique rows with aggregated rows and rows with invalid l1
            df = pd.concat([df_unique, df_agg, df_invalid_l1], ignore_index=True)
            
            # Sort the dataframe by Kbez column alphabetically
            if 'Beschreibung' in df.columns:
                df = df.sort_values(by='Beschreibung')

            if 'Kbez' in df.columns:
                # Convert d1, d2, d3 to numeric for proper numerical sorting
                for col in ['d1', 'd2', 'd3']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Create sort columns list with Kbez first, then d1, d2, d3
                sort_columns = ['Kbez']
                for col in ['d1', 'd2', 'd3']:
                    if col in df.columns:
                        sort_columns.append(col)
                
                # Sort by Kbez first, then numerically by d1, d2, d3
                df = df.sort_values(by=sort_columns)

    # Write the sanitized data to a CSV file
    df['Verbaut'] = "0"  # Add your new column here
    df.to_csv(csv_file, index=False)

# Example usage

def parseall_xls_to_csv(sourcedir):
    # List all .xls files
    xls_files = [f for f in os.listdir(sourcedir) if f.endswith('.xls')]
    
    # Parse each xls file
    for file in xls_files:
        file_path = os.path.join(sourcedir, file)
        parse_xls_to_csv(file_path, file_path.replace('.xls', '.csv'))

# Call the function
parseall_xls_to_csv(sourcedir)

# parse_xls_to_csv('p:/git/wittools/parsexml/test.xls', 'p:/git/wittools/parsexml/output.csv')