import pandas as pd
import re
import os
# requirements:
# pip install wheel
# pip install pandas
# pip install xlrd

print("Current Working Directory:", os.getcwd())

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

    # Write the sanitized data to a CSV file
    df.to_csv(csv_file, index=False)
    # Write the sanitized data to a CSV file
    df['Verbaut'] = "0"  # Add your new column here
    df.to_csv(csv_file, index=False)

# Example usage
parse_xls_to_csv('p:/git/wittools/parsexml/test.xls', 'p:/git/wittools/parsexml/output.csv')