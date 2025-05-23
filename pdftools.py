import os
import re

# For Tesseract-OCR (scanning via PDF-Image)
# https://github.com/tesseract-ocr/tesseract/releases
# https://github.com/oschwartz10612/poppler-windows/releases/
# PATH:
# C:\Users\$USER\AppData\Local\Programs\Tesseract-OCR
# C:\tools\poppler\Library\bin
# https://github.com/tesseract-ocr/tessdata/blob/main/deu.traineddata
# to: 
# C:\Users\$USER\AppData\Local\Programs\Tesseract-OCR\tessdata


## Convert a PDF file to Markdown using MarkItDown.
def pdf_to_markdown(pdf_path):
    from markitdown import MarkItDown
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
    md = MarkItDown(enable_plugins=False, enable_ocr=True)
    result = md.convert(pdf_path)
    return result.text_content

## Convert PDF pages to images and extract text using OCR (pytesseract).
def pdf_to_markdown_ocr(pdf_path):
    from pdf2image import convert_from_path
    import pytesseract
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
    return text



def process_all_pdfs_in_directory(directory_path, output_csv_path, combine_results=False, sanitizer_func=None):
    """Process all PDFs in the specified directory and optionally concatenate results to a single CSV file.
    
    Args:
        directory_path: Path to directory containing PDF files
        output_csv_path: Path to output CSV file
        combine_results: If True, combine all results into a single CSV file (default: False)
        sanitizer_func: Function to sanitize the extracted text (default: None)
    """
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
            md_text = pdf_to_markdown(pdf_path)
            
            # Sanitize the text
            if sanitizer_func:
                processed_text = sanitizer_func(md_text)
            else:
                processed_text = sanitize_pdf_text(md_text)
            
            # Add to results
            all_results.append(processed_text)
            
            # Also save individual file for reference
            individual_csv = os.path.join(directory_path, os.path.splitext(pdf_file)[0] + ".csv")
            with open(individual_csv, "wb") as f:
                f.write(processed_text.encode('utf-8'))
            print(f"  Individual CSV written to {individual_csv}")
            
        except Exception as e:
            print(f"  Error processing {pdf_file}: {str(e)}")
    
    # Combine all results and write to output CSV if requested
    if combine_results:
        combined_text = '\n'.join(all_results)
        
        with open(output_csv_path, "wb") as f:
            f.write(combined_text.encode('utf-8'))
        
        print(f"\nAll results combined and written to {output_csv_path}")
    
    print(f"Total PDFs processed: {len(pdf_files)}")

if __name__ == "__main__":
    # Directory containing PDF files
    pdf_directory = "M:\\encode\\pdf\\metro"
    
    # Output CSV file path
    output_csv = "M:\\encode\\pdf\\combined_results.csv"
    
    # Process all PDFs and create combined CSV
    from sanitizers_special import sanitize_markdown_metro_invoice
    process_all_pdfs_in_directory(pdf_directory, output_csv, combine_results=False, sanitizer_func=sanitize_markdown_metro_invoice)
