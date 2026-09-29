"""Config-driven regex transforms applied to markdown before upsert."""

import re


def apply_transforms(text, rules):
    """Apply [{pattern, replacement}] substitution rules in order."""
    for rule in rules or []:
        text = re.sub(rule["pattern"], rule["replacement"], text)
    return text
