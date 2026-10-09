"""Site-specific automations for webtools.

Each module in this package is one site and exposes:
- COMMAND: the CLI subcommand name
- DESCRIPTION: help text for the subcommand
- add_arguments(parser): adds the site's CLI flags
- run(args): executes the automation, returns saved file paths
"""

import importlib
import pkgutil
import sys


def load_sites():
    """Discover site modules and return {COMMAND: module}."""
    sites = {}
    for info in pkgutil.iter_modules(__path__):
        try:
            module = importlib.import_module(f"{__name__}.{info.name}")
        except ImportError as error:
            print(
                f"webtools: skipping site '{info.name}': {error}",
                file=sys.stderr,
            )
            continue
        if hasattr(module, "COMMAND"):
            sites[module.COMMAND] = module
    return sites
