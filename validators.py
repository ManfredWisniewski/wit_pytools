"""Validation utilities for email addresses and other data."""
import re


def valid_email_address(email_string):
    """
    Check if a string contains a valid email address with domain.
    
    Args:
        email_string: String to check for valid email
        
    Returns:
        bool: True if valid email found, False otherwise
    """
    # Pattern: @ + domain name (letters, numbers, dots, hyphens) + . + TLD (1-8 letters)
    email_pattern = r'@[\w.-]+\.[a-zA-Z]{1,8}'
    return bool(re.search(email_pattern, email_string))
