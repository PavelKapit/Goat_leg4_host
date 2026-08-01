"""
config.py — central configuration for the Represent scraper.
"""

BASE_URL = "https://uk.representclo.com"

# Default category/collection pages to crawl for product URLs,
# used only if no URL is passed on the command line.
COLLECTION_URLS = [
    f"{BASE_URL}/collections/all",
]

# Default catalog name, used only if no --name is passed on the command line.
DEFAULT_CATALOG_NAME = "catalog"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15          # seconds
REQUEST_DELAY = 0.5           # seconds between requests, be polite
MAX_RETRIES = 3


def get_run_paths(catalog_name: str, date_str: str) -> dict:
    """
    Builds all output paths for a given catalog run, so each scraping run
    (different catalog name + date) gets its own isolated output file
    and never overwrites previous results.

    File naming pattern: "<catalog_name> - <date>.xlsx"
    Example: "Чудокаталог - 01.01.1991.xlsx"
    """
    safe_name = catalog_name.strip()
    output_dir = "outputs"
    base_filename = f"{safe_name} - {date_str}"
    return {
        "output_dir": output_dir,
        "xlsx_path": f"{output_dir}/{base_filename}.xlsx",
        "csv_path": f"{output_dir}/{base_filename}.csv",
        "log_path": f"logs/{base_filename}.log",
    }
