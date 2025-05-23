import re


# specialized sanitizers for PDF extracted data

def sanitize_markdown_norisbank_kontoauszug(text):
    """Sanitize and format text from Norisbank account statements (Kontoauszug).
    Extracts relevant transaction data from pdf, and creates a CSV file for importing.
    
    Tested for account statements years 2020-2025. Some manual adjustments may be required.
    """
    # Replace null bytes, normalize line endings, strip trailing whitespace
    text = text.replace('\x00', '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove trailing spaces on each line
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    # Optionally, collapse multiple blank lines
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    # Remove everything before and including the line starting with 'Buchung'
    lines = text.split('\n')
    for idx, line in enumerate(lines):
        if line.startswith('Buchung'):
            lines = lines[idx+1:]
            break
    # Remove the line starting with 'Filialnummer' and everything after it
    for idx, line in enumerate(lines):
        if line.startswith('Filialnummer'):
            lines = lines[:idx]
            break
    # Join lines with a space
    text = ' '.join(lines)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Process with separators
    csv_separator = ';'
    
    # Add separator after date occurrences
    text = re.sub(r'(\b\d{1,2}\.\d{1,2}\.)', r'\1' + csv_separator, text)
    
    # Add separator after numbers ending in ,XX (comma followed by two digits)
    text = re.sub(r'(\b\d+,\d{2})(?!\d)', r'\1' + csv_separator, text)
    
    # Replace "Verwendungszweck/ Kundenreferenz" with a separator
    text = text.replace("Verwendungszweck/ Kundenreferenz", csv_separator)
    text = text.replace("Verwendungszweck/ Kund enreferenz", csv_separator)
    
    # Remove everything after "[Image:" in each line
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if "[Image:" in line:
            # Keep only the part before "[Image:"
            line = line.split("[Image:")[0]
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Replace "von + " or "von - " with the separator while maintaining the sign
    text = re.sub(r'von \+ ', csv_separator + '+ ', text)
    text = re.sub(r'an - ', csv_separator + '- ', text)

    # Replace "; " and " ; " with ";"
    text = text.replace("; ", ";")
    text = text.replace(" ;", ";")
    text = text.replace(";;", ";")

    # Append year to date patterns (extract from filename or use current year)
    def append_year_to_dates(text, year):
        # Replace date patterns with dates including year, but only if they don't already have a year
        # Pattern: DD.MM.; -> DD.MM.YYYY;
        return re.sub(r'(\d{1,2})\.(\d{1,2})\.(;)', f'\\1.\\2.{year}\\3', text)
    
    # Append the specified year (required in years before 2023 as no year provided)
    current_year = "2024"
    
    # Append the year to all dates once
    text = append_year_to_dates(text, current_year)
    
    # Clean up any duplicate years that might have been added
    text = re.sub(r'(\d{4});(\d{4});', r'\1;', text)
    
    # Add line breaks before double-date patterns with semicolons and years
    text = re.sub(r'(\d{1,2}\.\d{1,2}\.\d{4};)\s*(\d{1,2}\.\d{1,2}\.\d{4};)', r'\n\1\2', text)
    
    return text.strip()