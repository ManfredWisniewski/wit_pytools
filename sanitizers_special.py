import re


# specialized sanitizers for PDF extracted data

# TEMPLATE FUNCTION FOR PDF SANITIZATION
def sanitize_pdf_text(text):
    """Sanitize text extracted from PDF files.
    
    Args:
        text: Text content extracted from PDF
        
    Returns:
        Sanitized text content
    """
    # Replace null bytes
    text = text.replace('\x00', '')
    
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove trailing spaces on each line
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    
    # Collapse multiple blank lines
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    
    # Remove everything after "[Image:" in each line
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if "[Image:" in line:
            # Keep only the part before "[Image:"
            line = line.split("[Image:")[0]
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    return text.strip()



def sanitize_markdown_metro_invoice(text):
    """Sanitize and format markup generated from Metro pdf invoices
    
    Tested for invoices years 2023.
    
    Args:
        text: Text content extracted from PDF
        
    Returns:
        Sanitized text content
    """
    # Replace null bytes
    text = text.replace('\x00', '')
    
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove trailing spaces on each line
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    
    # Collapse multiple blank lines
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    
    # Remove all text before the third line containing "--------------------"
    lines = text.split('\n')
    dash_count = 0
    start_index = 0
    
    for i, line in enumerate(lines):
        if "--------------------" in line:
            dash_count += 1
            if dash_count == 3:
                start_index = i + 1  # Start after the third dash line
                break
    
    if start_index > 0 and start_index < len(lines):
        lines = lines[start_index:]
    
    # Remove content from SEITENSUMME until the third dash line after it
    seitensumme_index = -1
    for i, line in enumerate(lines):
        if "SEITENSUMME" in line:
            seitensumme_index = i
            break
    
    if seitensumme_index >= 0:
        # Find the third dash line after SEITENSUMME
        dash_count = 0
        end_index = len(lines)
        
        for i in range(seitensumme_index, len(lines)):
            if "--------------------" in lines[i]:
                dash_count += 1
                if dash_count == 3:
                    end_index = i + 1  # Include the third dash line
                    break
        
        # Remove the section
        if seitensumme_index < end_index:
            lines = lines[:seitensumme_index] + lines[end_index:]
    
    # Remove lines containing "ÜBERTRAG SEITENSUMME" (handling different encodings/variations)
    filtered_lines = []
    for line in lines:
        # Skip lines with ÜBERTRAG SEITENSUMME
        if "ÜBERTRAG" in line and "SEITENSUMME" in line:
            continue
        if "BERTRAG" in line and "SEITENSUMME" in line:  # In case of encoding issues
            continue
        
        # Skip lines with leading whitespace (10 or more spaces)
        if line.startswith("       "):
            continue
            
        filtered_lines.append(line)
    lines = filtered_lines
    
    # Find the next line containing "--------------------" and remove it and everything after
    dash_index = -1
    for i, line in enumerate(lines):
        if "--------------------" in line:
            dash_index = i
            break
    
    if dash_index >= 0:
        lines = lines[:dash_index]  # Remove the dash line and everything after
    
    # Process lines starting with **** and prepend text to following lines
    processed_lines = []
    current_prefix = ""
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        if line.strip().startswith("****") and "****" in line[4:]:
            # Extract text between **** and ****
            start_idx = line.find("****") + 4
            end_idx = line.find("****", start_idx)
            
            if end_idx > start_idx:
                prefix_text = line[start_idx:end_idx].strip()
                # Remove trailing colon if it exists
                if prefix_text.endswith(":"):
                    prefix_text = prefix_text[:-1].strip()
                current_prefix = prefix_text
            i += 1  # Skip this line
        else:
            # Add the current line with prefix if it's not empty
            if line.strip():
                processed_lines.append(current_prefix + line)
            i += 1
    
    lines = processed_lines
    
    # Convert lines to CSV format with semicolons as separators
    csv_lines = []
    for line in lines:
        if line.strip():
            # First split by multiple spaces
            parts = [part for part in re.split(r'\s{2,}', line) if part.strip()]
            
            # Special handling for product codes and names
            if len(parts) >= 2:
                # Check if the second part contains a product code pattern (digits followed by space and more digits)
                product_code_match = re.match(r'^(\d+\.\d+\s+\d+)', parts[1])
                if product_code_match:
                    # Split the product code from the product name
                    product_code = product_code_match.group(1)
                    product_name = parts[1][len(product_code):].strip()
                    
                    # Replace the original part with two separate parts
                    new_parts = [parts[0], product_code]
                    if product_name:  # Only add if there's something after the product code
                        new_parts.append(product_name)
                    new_parts.extend(parts[2:])  # Add the rest of the parts
                    parts = new_parts
            
            # Fix country code issue - if we have a two-letter country code as a separate column
            # and it's followed by unit codes like BT, KG, PG, etc.
            if len(parts) >= 4 and len(parts[3]) == 2 and parts[3].upper() == parts[3]:
                # Check if the next part is a typical unit code
                if len(parts) >= 5 and re.match(r'^[A-Z]{2}$', parts[4]):
                    # Merge the product name with the country code
                    parts[2] = parts[2] + " " + parts[3]
                    # Remove the country code part
                    parts.pop(3)
            
            # Clean up the 11th column (index 10) - remove Â and * characters
            if len(parts) >= 11:
                # Remove Â and * characters from the value
                parts[10] = parts[10].replace('Â', '').replace('*', '').strip()
            
            # Join parts with semicolons
            csv_line = ";".join(parts)
            csv_lines.append(csv_line)
        else:
            csv_lines.append(line)
    
    # Remove everything after "[Image:" in each line
    cleaned_lines = []
    for line in csv_lines:
        if "[Image:" in line:
            # Keep only the part before "[Image:"
            line = line.split("[Image:")[0]
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    return text.strip()

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