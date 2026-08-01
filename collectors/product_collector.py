"""
collectors/product_collector.py — discovers product URLs from collection pages.
"""

import logging
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def get_product_urls(collection_url: str, headers: dict, timeout: int, delay: float) -> list:
    """
    Paginates through a Shopify collection page and returns all product URLs found.
    Stops when a page returns zero product links (end of pagination).
    """
    product_urls = []
    seen = set()
    page = 1

    while True:
        url = f"{collection_url}?page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch collection page {url}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select("a[href*='/products/']")
        page_urls = sorted({
            requests.compat.urljoin(collection_url, a["href"].split("?")[0])
            for a in links if a.get("href")
        })

        # Shopify returns an empty page (no product links) once pagination ends
        if not page_urls:
            logger.info(f"Page {page}: no products found — stopping pagination")
            break

        new_urls = [u for u in page_urls if u not in seen]

        # If a page returns the exact same products as before, we've looped — stop
        if not new_urls:
            logger.info(f"Page {page}: no new products — stopping pagination")
            break

        seen.update(new_urls)
        product_urls.extend(new_urls)
        logger.info(f"Page {page}: found {len(new_urls)} new product URLs (total {len(product_urls)})")

        page += 1
        time.sleep(delay)

        if page > 100:  # safety cap
            logger.warning("Reached safety cap of 100 pages — stopping")
            break

    return product_urls
