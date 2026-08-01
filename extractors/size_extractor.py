"""
extractors/size_extractor.py

Extracts product name, images, currency, and per-size pricing
(current price + pre-discount compare-at price) from a Represent
product page (Shopify-based storefront).

Compatible with Python 3.8+.
"""

import re
import logging
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_product_data(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    name = _extract_name(soup)
    images = _extract_images(soup)
    currency = _extract_currency(soup)
    variants = extract_sizes(soup, url)

    return {
        "url": url,
        "name": name,
        "currency": currency,
        "images": images,
        "variants": variants,
    }


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    tag = soup.find("meta", {"property": "og:title"})
    if tag and tag.get("content"):
        return tag["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.split("|")[0].strip()
    return None


def _clean_image_url(raw_url: str) -> Optional[str]:
    """
    The Represent site sometimes serves og:image content wrapped by a
    Speedsize proxy with a malformed double-protocol prefix, e.g.:

        http:https://sfycdn.speedsize.com/<id>/uk.representclo.com/cdn/shop/files/...

    This function strips the bad "http:" (or "https:") prefix that
    precedes a second, valid "http://" or "https://" scheme, so the
    URL becomes directly fetchable:

        https://sfycdn.speedsize.com/<id>/uk.representclo.com/cdn/shop/files/...
    """
    if not raw_url:
        return None

    raw_url = raw_url.strip()

    # Fix double-protocol prefix: "http:https://..." or "https:http://..."
    match = re.search(r"(https?://.+)$", raw_url)
    if match:
        candidate = match.group(1)
        # If there's still a second embedded protocol further in (proxy-wrapped
        # original URL), keep the first valid one — Speedsize proxy URLs are
        # themselves directly fetchable and will resolve to the real image.
        return candidate

    return raw_url


def _extract_images(soup: BeautifulSoup) -> List[str]:
    tags = soup.find_all("meta", {"property": "og:image"})
    cleaned = []
    for t in tags:
        content = t.get("content")
        if not content:
            continue
        fixed = _clean_image_url(content)
        if fixed:
            cleaned.append(fixed)
    return cleaned


def _extract_currency(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", {"property": "og:price:currency"})
    return tag["content"] if tag and tag.get("content") else "GBP"


def extract_sizes(soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
    select = (
        soup.find("select", {"class": "product-select-data"})
        or soup.find("select", attrs={"id": re.compile(r"^ProductSelectData-")})
    )

    if not select:
        logger.warning(f"No sizes found for {url}")
        return []

    variants = []
    for opt in select.find_all("option"):
        size = opt.get("data-option-1")
        if not size:
            continue

        available = not opt.has_attr("disabled")

        price_cents = opt.get("data-variant-price")
        compare_cents = opt.get("data-variant-price-compare")

        price = _cents_to_float(price_cents)
        compare_at_price = _cents_to_float(compare_cents)

        discount_pct = None
        if price is not None and compare_at_price and compare_at_price > price:
            discount_pct = round((1 - price / compare_at_price) * 100, 1)

        variants.append({
            "size": size,
            "available": available,
            "price": price,
            "compare_at_price": compare_at_price,
            "discount_pct": discount_pct,
            "variant_id": opt.get("value"),
        })

    return variants


def _cents_to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(int(value) / 100, 2)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            html = f.read()
        data = extract_product_data(html, url="local-test")
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))
