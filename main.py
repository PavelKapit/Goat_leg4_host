"""
main.py — entry point for the Represent scraper pipeline.

This version does NOT download product images. It only collects the
image URL (cleaned of any malformed proxy prefix) and stores it in the
report, so Google Sheets can render it via =IMAGE() after import.

URL source priority (highest to lowest):
    1. Command-line arguments (http:// or https:// URLs)
    2. TARGET.txt (one URL per line, lines starting with # are ignored)
    3. config.COLLECTION_URLS (hardcoded fallback)

This lets the scraper run unattended (e.g. via GitHub Actions on a daily
schedule) by simply editing TARGET.txt — no command-line arguments needed.

Usage:
    python main.py
        Reads target URL(s) from TARGET.txt (or config.py if TARGET.txt
        is missing/empty). Catalog name and date default automatically.

    python main.py <url>
        Overrides TARGET.txt with a specific collection/category URL.

    python main.py <url> --name "<catalog_name>"
        Also sets a custom catalog name for the output file.

    python main.py <url> --name "<catalog_name>" --date <DD.MM.YYYY>
        Also sets an explicit date instead of today's date.
        Example: --date 01.01.1991

Examples:
    python main.py
    python main.py --name "Чудокаталог"
    python main.py https://uk.representclo.com/collections/shorts --name "Shorts"
    python main.py https://uk.representclo.com/collections/all --name "Чудокаталог" --date 01.01.1991
"""

import os
import sys
import logging
import time
from datetime import datetime
import requests
from tqdm import tqdm

import config
from collectors.product_collector import get_product_urls
from extractors.size_extractor import extract_product_data
from reporting.excel_builder import rows_to_dataframe, save_csv, save_excel_with_formulas

TARGET_FILE = "TARGET.txt"


def read_target_file(path: str = TARGET_FILE) -> list:
    """
    Reads target URLs from TARGET.txt — one URL per line.
    Lines that are blank or start with '#' are ignored (comments).
    Returns an empty list if the file doesn't exist or has no valid URLs.
    """
    if not os.path.exists(path):
        return []

    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
    return urls


def parse_args():
    """
    Parses sys.argv for collection URLs, an optional --name flag, and an
    optional --date flag.

    URL resolution order: command-line args > TARGET.txt > config.py

    Returns (collection_urls: list, catalog_name: str, date_str: str, url_source: str)
    """
    args = sys.argv[1:]
    catalog_name = config.DEFAULT_CATALOG_NAME
    date_str = datetime.now().strftime("%d.%m.%Y")
    urls = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--name":
            if i + 1 < len(args):
                catalog_name = args[i + 1]
                i += 2
                continue
            i += 1
            continue
        if arg == "--date":
            if i + 1 < len(args):
                date_str = args[i + 1]
                i += 2
                continue
            i += 1
            continue
        if arg.startswith("http://") or arg.startswith("https://"):
            urls.append(arg)
        i += 1

    url_source = "command line"

    if not urls:
        urls = read_target_file()
        url_source = f"{TARGET_FILE}"

    if not urls:
        urls = config.COLLECTION_URLS
        url_source = "config.py (fallback)"

    return urls, catalog_name, date_str, url_source


def scrape_product(url: str, logger: logging.Logger) -> list:
    """
    Scrapes a single product page and returns a list of flat row dicts,
    one per size variant, ready for the report. No images are downloaded —
    only the (cleaned) image URL is kept.
    """
    try:
        resp = requests.get(url, headers=config.REQUEST_HEADERS, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch product page {url}: {e}")
        return []

    data = extract_product_data(resp.text, url)
    image_url = data["images"][0] if data["images"] else None

    if not data["variants"]:
        return [{
            "product_url": url,
            "name": data["name"],
            "size": None,
            "available": None,
            "price": None,
            "compare_at_price": None,
            "image_url": image_url,
        }]

    rows = []
    for variant in data["variants"]:
        rows.append({
            "product_url": url,
            "name": data["name"],
            "size": variant["size"],
            "available": variant["available"],
            "price": variant["price"],
            "compare_at_price": variant["compare_at_price"],
            "image_url": image_url,
        })
    return rows


def main():
    collection_urls, catalog_name, date_str, url_source = parse_args()
    paths = config.get_run_paths(catalog_name, date_str)

    os.makedirs(paths["output_dir"], exist_ok=True)
    os.makedirs(os.path.dirname(paths["log_path"]), exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(paths["log_path"], encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    logger = logging.getLogger(__name__)

    logger.info(f"Catalog: '{catalog_name}' — Date: {date_str}")
    logger.info(f"Output file: {paths['xlsx_path']}")
    logger.info(f"URL source: {url_source}")
    logger.info(f"Collection URL(s) to scrape: {collection_urls}")

    logger.info("Collecting product URLs...")
    all_product_urls = []
    for collection_url in collection_urls:
        urls = get_product_urls(
            collection_url, config.REQUEST_HEADERS,
            config.REQUEST_TIMEOUT, config.REQUEST_DELAY
        )
        all_product_urls.extend(urls)

    all_product_urls = sorted(set(all_product_urls))
    logger.info(f"Found {len(all_product_urls)} unique product URLs")

    if not all_product_urls:
        logger.warning("No product URLs found — nothing to scrape. Check the collection URL.")
        return

    all_rows = []
    for url in tqdm(all_product_urls, desc=f"Scraping products [{catalog_name}]"):
        rows = scrape_product(url, logger)
        all_rows.extend(rows)
        time.sleep(config.REQUEST_DELAY)

    df = rows_to_dataframe(all_rows)
    save_csv(df, paths["csv_path"])
    save_excel_with_formulas(df, paths["xlsx_path"])

    logger.info(f"Done. Saved {len(df)} rows to {paths['csv_path']} and {paths['xlsx_path']}")


if __name__ == "__main__":
    main()
