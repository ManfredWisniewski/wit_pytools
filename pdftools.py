import os
from markitdown import MarkItDown
from pdf2image import convert_from_path
import pytesseract

# For Tesseract-OCR (scanning via PDF-Image)
# https://github.com/tesseract-ocr/tesseract/releases
# https://github.com/oschwartz10612/poppler-windows/releases/
# PATH:
# C:\Users\$USER\AppData\Local\Programs\Tesseract-OCR
# C:\tools\poppler\Library\bin
# https://github.com/tesseract-ocr/tessdata/blob/main/deu.traineddata
# to: 
# C:\Users\$USER\AppData\Local\Programs\Tesseract-OCR\tessdata

def sanitize_markdown_norisbank_kontoauszug(text):
    """Sanitize and format text from Norisbank account statements (Kontoauszug).
    Tested for account statements years 2020-2025
    
    Extracts relevant transaction data, and creates a CSV file for importing.
    """
    import re
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
    text = text.replace(";;" , ";")

    
    # Append year to date patterns (extract from filename or use current year)
    def append_year_to_dates(text, year):
        # Replace date patterns with dates including year, but only if they don't already have a year
        # Pattern: DD.MM.; -> DD.MM.YYYY;
        return re.sub(r'(\d{1,2})\.(\d{1,2})\.(;)', f'\\1.\\2.{year}\\3', text)
    
    # Use the specified year
    current_year = "2024"
    
    # Append the year to all dates once
    text = append_year_to_dates(text, current_year)
    
    # Clean up any duplicate years that might have been added
    text = re.sub(r'(\d{4});(\d{4});', r'\1;', text)
    
    # Add line breaks before double-date patterns with semicolons and years
    text = re.sub(r'(\d{1,2}\.\d{1,2}\.\d{4};)\s*(\d{1,2}\.\d{1,2}\.\d{4};)', r'\n\1\2', text)
    
    return text.strip()

def ocr_pdf_to_markdown(pdf_path):
    """Convert PDF pages to images and extract text using OCR (pytesseract). Also saves images to the PDF directory."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
    images = convert_from_path(pdf_path)
    text = ""
    pdf_dir = os.path.dirname(pdf_path)
    pdf_base = os.path.splitext(os.path.basename(pdf_path))[0]
    for i, img in enumerate(images, 1):
        img_filename = f"{pdf_base}_page{i}.png"
        img_path = os.path.join(pdf_dir, img_filename)
        img.save(img_path, "PNG")
        text += pytesseract.image_to_string(img, lang='deu')
        text += f"\n\n[Image: {img_filename}]\n\n"
    return sanitize_markdown_norisbank_kontoauszug(text)

def convert_pdf_to_markdown(pdf_path):
    """Convert a PDF file to Markdown using MarkItDown."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
    md = MarkItDown(enable_plugins=False, enable_ocr=True)
    result = md.convert(pdf_path)
    return result.text_content

def process_all_pdfs_in_directory(directory_path, output_csv_path):
    """Process all PDFs in the specified directory and concatenate results to a single CSV file."""
    if not os.path.exists(directory_path):
        print(f"Directory not found: {directory_path}")
        return
    
    # Get all PDF files in the directory
    pdf_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in {directory_path}")
        return
    
    # Process each PDF and collect results
    all_results = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(directory_path, pdf_file)
        print(f"Processing: {pdf_path}")
        
        try:
            # Extract and process text from PDF
            md_text = ocr_pdf_to_markdown(pdf_path)
            processed_text = sanitize_markdown_norisbank_kontoauszug(md_text)
            
            # Add to results
            all_results.append(processed_text)
            
            # Also save individual file for reference
            individual_csv = os.path.join(directory_path, os.path.splitext(pdf_file)[0] + ".csv")
            with open(individual_csv, "wb") as f:
                f.write(processed_text.encode('utf-8'))
            print(f"  Individual CSV written to {individual_csv}")
            
        except Exception as e:
            print(f"  Error processing {pdf_file}: {str(e)}")
    
    # Combine all results and write to output CSV
    combined_text = '\n'.join(all_results)
    
    with open(output_csv_path, "wb") as f:
        f.write(combined_text.encode('utf-8'))
    
    print(f"\nAll results combined and written to {output_csv_path}")
    print(f"Total PDFs processed: {len(pdf_files)}")

if __name__ == "__main__":
    # Directory containing PDF files
    pdf_directory = os.path.join(os.path.dirname(__file__), "tests", "pdftools", "pdf")
    
    # Output CSV file path
    output_csv = os.path.join(os.path.dirname(__file__), "tests", "pdftools", "combined_results.csv")
    
    # Process all PDFs and create combined CSV
    process_all_pdfs_in_directory(pdf_directory, output_csv)
