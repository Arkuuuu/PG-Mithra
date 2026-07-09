"""
Detail Extractor -- Clicks into a Google Maps listing and extracts full details.

Extracts: full name, address, phone, website, rating, reviews, category,
hours, plus code, price level, lat/lng, photos count, and Maps URL.
"""

import re
import random
import logging
from datetime import datetime

from anti_detect import random_delay, random_mouse_move, random_page_interaction

logger = logging.getLogger(__name__)


async def extract_listing_detail(page, card_element, area: str, query: str) -> dict | None:
    """
    Click a listing card, wait for the detail pane, extract all fields,
    then navigate back to the results.

    Args:
        page: Playwright Page object
        card_element: The listing card Locator/ElementHandle to click
        area: The area being searched (for metadata)
        query: The search query used (for metadata)

    Returns:
        dict with all extracted fields, or None if extraction failed
    """
    data = {
        "name": "",
        "rating": "",
        "review_count": "",
        "category": "",
        "address_short": "",
        "address_full": "",
        "phone": "",
        "website": "",
        "hours": "",
        "price_level": "",
        "plus_code": "",
        "latitude": "",
        "longitude": "",
        "google_maps_url": "",
        "photos_count": "",
        "search_query": query,
        "area": area,
        "scraped_at": datetime.now().isoformat(),
    }

    try:
        # -- Click the listing card --
        await card_element.click()
        await random_delay(2.0, 4.0)

        # -- Wait for detail pane to load --
        # h1.DUwDvf is the specific business name heading in the detail pane.
        # We must NOT match the generic "Results" h1 from the search page.
        try:
            await page.wait_for_selector(
                "h1.DUwDvf",
                timeout=10000,
            )
        except Exception:
            # Fallback: try other detail pane indicators
            try:
                await page.wait_for_selector(
                    "h1.fontHeadlineLarge",
                    timeout=5000,
                )
            except Exception:
                logger.warning("  [!] Detail pane didn't load, skipping listing")
                return None

        # Occasional random interaction to look human
        if random.random() < 0.3:
            await random_page_interaction(page)

        # -- Extract Name --
        # Try the most specific selector first
        data["name"] = await _safe_text(page, "h1.DUwDvf")
        if not data["name"] or data["name"].lower() in ("results", "search", ""):
            data["name"] = await _safe_text(page, "h1.fontHeadlineLarge")
        if not data["name"] or data["name"].lower() in ("results", "search", ""):
            # Last resort: try aria-label on the main section
            data["name"] = await _safe_attr(page, "div[role='main']", "aria-label")
        if data["name"] and data["name"].lower() in ("results", "search"):
            data["name"] = ""  # Clear garbage names

        # -- Extract Rating --
        data["rating"] = await _safe_attr(
            page,
            "div.fontDisplayLarge, span.ceNzKf, div.F7nice span[aria-hidden]",
            "text",
        )
        if not data["rating"]:
            # Try aria-label approach
            rating_text = await _safe_attr(
                page, "span[role='img']", "aria-label"
            )
            if rating_text:
                match = re.search(r"([\d.]+)", rating_text)
                if match:
                    data["rating"] = match.group(1)

        # -- Extract Review Count --
        review_text = await _safe_text(
            page, "span.UY7F9, button[jsaction*='review'] span"
        )
        if review_text:
            match = re.search(r"([\d,]+)", review_text.replace(",", ""))
            if match:
                data["review_count"] = match.group(1)

        # -- Extract Category --
        data["category"] = await _safe_text(
            page, "button[jsaction*='category'], span.DkEaL"
        )

        # -- Extract Full Address --
        data["address_full"] = await _safe_info_field(page, "address")
        if not data["address_full"]:
            data["address_full"] = await _safe_attr(
                page, "button[data-item-id='address']", "aria-label"
            )
            if data["address_full"]:
                # Strip "Address: " prefix if present
                data["address_full"] = re.sub(
                    r"^Address:\s*", "", data["address_full"]
                )

        # -- Extract Phone --
        data["phone"] = await _safe_info_field(page, "phone")
        if not data["phone"]:
            phone_label = await _safe_attr(
                page, "button[data-item-id^='phone']", "aria-label"
            )
            if phone_label:
                # Extract phone number from aria-label like "Phone: 040-12345678"
                data["phone"] = re.sub(r"^Phone:\s*", "", phone_label)

        # -- Extract Website --
        data["website"] = await _safe_attr(
            page, "a[data-item-id='authority']", "href"
        )
        if not data["website"]:
            data["website"] = await _safe_info_field(page, "authority")

        # -- Extract Hours --
        try:
            hours_el = page.locator(
                "div[aria-label*='hour' i], div[aria-label*='Hours' i], "
                "table.eK4R0e, div.t39EBf"
            ).first
            if await hours_el.count() if hasattr(hours_el, 'count') else True:
                hours_text = await hours_el.inner_text(timeout=3000)
                data["hours"] = hours_text.strip().replace("\n", " | ")
        except Exception:
            pass

        # -- Extract Plus Code --
        data["plus_code"] = await _safe_info_field(page, "oloc")
        if not data["plus_code"]:
            data["plus_code"] = await _safe_attr(
                page, "button[data-item-id='oloc']", "aria-label"
            )

        # -- Extract Price Level --
        price_text = await _safe_text(
            page, "span[aria-label*='Price' i], span.mgr77e"
        )
        if price_text:
            data["price_level"] = price_text.strip()

        # -- Extract Lat/Lng from URL --
        current_url = page.url
        data["google_maps_url"] = current_url
        coords = _parse_coords_from_url(current_url)
        if coords:
            data["latitude"] = coords[0]
            data["longitude"] = coords[1]

        # -- Extract Photos Count --
        try:
            photos = page.locator(
                "button[aria-label*='photo' i], div.RZ66Rb"
            )
            photos_count = await photos.count()
            data["photos_count"] = str(photos_count) if photos_count > 0 else ""
        except Exception:
            pass

        # -- Extract Image URL --
        try:
            img_el = page.locator("button[jsaction*='hero'] img, button[aria-label*='photo' i] img, div.RZ66Rb img").first
            if await img_el.is_visible(timeout=2000):
                src = await img_el.get_attribute("src")
                if src:
                    data["image_url"] = src.strip()
        except Exception:
            pass

        # -- Extract Review Tags / Keywords --
        try:
            tags_els = page.locator("button.t752Kc, button[jsaction*='clickReviewFilter']")
            count = await tags_els.count()
            tags = []
            for idx in range(min(count, 8)):
                txt = await tags_els.nth(idx).inner_text()
                if txt:
                    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", txt).strip()
                    if cleaned:
                        tags.append(cleaned)
            if tags:
                data["review_tags"] = ", ".join(tags)
        except Exception:
            pass

        logger.info(f"  [OK] Extracted: {data['name']} | {data['phone']} | {data['address_full'][:40]}...")
        return data

    except Exception as e:
        logger.error(f"  [ERR] Detail extraction error: {e}")
        return None


# ---------------------------------------------
# Helper Functions
# ---------------------------------------------

async def _safe_text(page, selector: str) -> str:
    """Safely extract inner text from the first matching element."""
    try:
        el = page.locator(selector).first
        text = await el.inner_text(timeout=3000)
        return text.strip() if text else ""
    except Exception:
        return ""


async def _safe_attr(page, selector: str, attr: str) -> str:
    """Safely extract an attribute or text from the first matching element."""
    try:
        el = page.locator(selector).first
        if attr == "text":
            text = await el.inner_text(timeout=3000)
            return text.strip() if text else ""
        else:
            val = await el.get_attribute(attr, timeout=3000)
            return val.strip() if val else ""
    except Exception:
        return ""


async def _safe_info_field(page, data_item_id: str) -> str:
    """
    Extract text from a Google Maps info field identified by data-item-id.
    These are the address/phone/website/etc. buttons in the detail pane.
    """
    try:
        selector = f"button[data-item-id='{data_item_id}'], " \
                   f"a[data-item-id='{data_item_id}']"
        el = page.locator(selector).first
        text = await el.inner_text(timeout=3000)
        return text.strip() if text else ""
    except Exception:
        return ""


def _parse_coords_from_url(url: str) -> tuple | None:
    """
    Parse latitude and longitude from a Google Maps URL.
    Prioritizes !3d/!4d (exact listing pinpoint) over @lat,lng (map center view).
    """
    # Pattern 1: !3dlat!4dlng (exact pinpoint coordinate)
    match = re.search(r"!3d(-?[\d.]+)!4d(-?[\d.]+)", url)
    if match:
        return (match.group(1), match.group(2))

    # Pattern 2: @lat,lng,zoom (map center coordinate)
    match = re.search(r"@(-?[\d.]+),(-?[\d.]+),", url)
    if match:
        return (match.group(1), match.group(2))

    return None


async def go_back_to_results(page) -> bool:
    """
    Navigate back from the detail pane to the results list.
    Tries the back button first, then browser back.
    """
    try:
        # Try clicking the back arrow in the detail pane
        back_btn = page.locator(
            "button[aria-label='Back'], button[jsaction*='back'], "
            "button.hYBOP"
        ).first
        if await back_btn.is_visible(timeout=2000):
            await back_btn.click()
            await random_delay(1.5, 3.0)
            return True
    except Exception:
        pass

    try:
        # Fallback: browser back
        await page.go_back()
        await random_delay(2.0, 3.5)
        return True
    except Exception as e:
        logger.warning(f"  [!] Could not navigate back: {e}")
        return False
