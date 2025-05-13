import os
import sys
import unittest

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdftools import pdf_to_markdown


class PdfToolsTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdftools')
        self.test_pdf = os.path.join(self.test_dir, 'pdf_sanitizer_metro_de24.pdf')
        
    def test_pdf_to_markdown(self):
        # Check if the test file exists
        self.assertTrue(os.path.exists(self.test_pdf), f"Test PDF file not found: {self.test_pdf}")
        
        # Convert PDF to markdown
        markdown_text = pdf_to_markdown(self.test_pdf)
        
        # Check if the result is not empty
        self.assertTrue(markdown_text, "PDF to markdown conversion returned empty text")
        
        # Check if the result contains some expected text (adjust based on actual PDF content)
        self.assertIsInstance(markdown_text, str, "Result should be a string")
        
        # Print the first 200 characters for debugging
        print(f"First 200 characters of extracted text: {markdown_text[:200]}")
        
        # Additional checks based on the specific PDF content
        # For example, check for keywords that should be in the PDF
        # self.assertIn("expected keyword", markdown_text.lower())


if __name__ == '__main__':
    unittest.main()
