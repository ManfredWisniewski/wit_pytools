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

def load_replacements(sourcedir):
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str  # Read the values case-sensitive
    with open(sourcedir + r'\aufmass.ini', encoding='utf-8') as f:
        config.read_file(f)    
    replacements = {key: value for key, value in config.items('REPLACEMENTS')}
    return replacements


def parse_xls_to_csv(xls_file, csv_file):

    replacestr = "-"

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
                    print(df[df[column].str.contains(old_str, na=False)])  # Print matching entries
                df[column] = df[column].replace(old_str, new_str, regex=True)

    # Write the sanitized data to a CSV file
    df.to_csv(csv_file, index=False)
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