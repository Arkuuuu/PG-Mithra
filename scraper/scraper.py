"""
Core Scraper -- Search → Scroll → Extract loop for Google Maps.

Navigates to Google Maps, runs each search query, scrolls the results feed
to load all listings, then extracts card-level data and detail-level data.
"""

import random
import asyncio
import logging

import config as cfg
from config import (
    MAPS_URL,
    DELAY_AFTER_SEARCH,
    DELAY_BETWEEN_ACTIONS,
    DELAY_BETWEEN_LISTINGS,
    DELAY_BETWEEN_SCROLLS,
    DELAY_BETWEEN_AREAS,
    DELAY_PAGE_LOAD,
    SCROLL_STEP_MIN,
    SCROLL_STEP_MAX,
    MAX_SCROLLS,
    SCROLL_STABLE_CHECKS,
    SEARCH_TEMPLATES,
)
from anti_detect import (
    random_delay,
    random_typing,
    random_scroll,
    random_mouse_move,
    random_page_interaction,
    random_pause_between_listings,
    jitter_click,
)
from detail_extractor import extract_listing_detail, go_back_to_results

logger = logging.getLogger(__name__)

# -- Results feed panel selector (Google Maps) --
FEED_SELECTOR = "div[role='feed']"
FEED_FALLBACK = "div.m6QErb[aria-label]"

# -- Search box selectors (try multiple) --
SEARCH_BOX_SELECTORS = [
    "input#searchboxinput",
    "input[name='q']",
    "input[aria-label*='Search']",
    "input[aria-label*='search']",
    "#searchbox input",
]


async def _handle_consent(page) -> None:
    """Dismiss Google consent / cookie banners if present."""
    consent_selectors = [
        "button:has-text('Accept all')",
        "button:has-text('Accept All')",
        "button:has-text('Reject all')",
        "button:has-text('I agree')",
        "form[action*='consent'] button",
        "button[aria-label*='Accept']",
        "button[jsname='higCR']",
        "button[jsname='b3VHJd']",
    ]
    for sel in consent_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                logger.info(f"  [OK] Dismissed consent dialog")
                await random_delay(1.5, 3.0)
                return
        except Exception:
            continue


async def _find_search_box(page) -> str | None:
    """
    Try multiple selectors to find the Google Maps search box.
    Returns the first matching selector, or None.
    """
    # Give Maps JS a moment to render
    await asyncio.sleep(2)
    for sel in SEARCH_BOX_SELECTORS:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=10000):
                logger.debug(f"  Found search box: {sel}")
                return sel
        except Exception:
            continue
    return None


async def scrape_area(page, area: str, all_results: list) -> int:
    """
    Run all search queries for a given area, scraping every listing found.

    Args:
        page: Playwright page (already stealth-patched)
        area: Locality name (e.g. "Madhapur")
        all_results: Shared list to append results to

    Returns:
        Number of new listings scraped for this area
    """
    area_count = 0

    for template in SEARCH_TEMPLATES:
        query = template.format(area=area)
        logger.info(f"\n{'='*60}")
        logger.info(f"[SEARCH] {query}")
        logger.info(f"{'='*60}")

        count = await _run_single_query(page, query, area, all_results)
        area_count += count

        # Random pause between different query templates
        await random_delay(*DELAY_BETWEEN_ACTIONS)

        # Occasional idle interaction
        if random.random() < 0.4:
            await random_page_interaction(page)

    logger.info(f"\n[DONE] Area '{area}' complete -- {area_count} listings scraped")
    return area_count


async def _run_single_query(page, query: str, area: str, all_results: list) -> int:
    """Execute a single search query and scrape all results."""

    # -- Step 1: Navigate to Google Maps (if not already there) --
    if "google.com/maps" not in page.url:
        logger.info("  Navigating to Google Maps...")
        await page.goto(MAPS_URL, wait_until="load", timeout=60000)
        await random_delay(*DELAY_PAGE_LOAD)
        await _handle_consent(page)

    # -- Step 2: Find the search box (try multiple selectors) --
    search_box = await _find_search_box(page)
    if not search_box:
        logger.warning("  Search box not found, reloading Maps...")
        await page.goto(MAPS_URL, wait_until="load", timeout=60000)
        await random_delay(3.0, 5.0)
        await _handle_consent(page)
        search_box = await _find_search_box(page)
        if not search_box:
            logger.error("  Search box still not found after reload, skipping query")
            return 0

    # Clear and type the query with human-like timing
    # Clear and type the query with human-like timing
    await random_typing(page, search_box, query)
    await random_delay(0.5, 1.0)

    # Press Enter with a small random delay
    await page.keyboard.press("Enter")
    logger.info("  [>] Search submitted")

    # -- Step 3: Wait for results to load --
    await random_delay(*DELAY_AFTER_SEARCH)

    # Check if results feed appeared
    feed_selector = await _find_feed_selector(page)
    if not feed_selector:
        logger.warning(f"  [!] No results feed found for: {query}")
        return 0

    # -- Step 4: Scroll to load all results --
    total_cards = await _scroll_results_feed(page, feed_selector)
    logger.info(f"  [i] Found {total_cards} listing cards after scrolling")

    # -- Step 5: Extract data from each listing --
    count = await _extract_all_listings(page, feed_selector, area, query, all_results)

    return count


async def _find_feed_selector(page) -> str | None:
    """Find the correct selector for the results feed panel."""
    for selector in [FEED_SELECTOR, FEED_FALLBACK]:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=3000):
                return selector
        except Exception:
            continue

    # Last resort: try any scrollable results container
    try:
        el = page.locator("div.m6QErb").first
        if await el.is_visible(timeout=3000):
            return "div.m6QErb"
    except Exception:
        pass

    return None


async def _scroll_results_feed(page, feed_selector: str) -> int:
    """
    Scroll the results feed to load all listings.
    Returns the total number of listing cards found.
    """
    previous_count = 0
    stable_count = 0

    for scroll_num in range(MAX_SCROLLS):
        # Scroll by random amount
        await random_scroll(page, feed_selector, SCROLL_STEP_MIN, SCROLL_STEP_MAX)
        await random_delay(*DELAY_BETWEEN_SCROLLS)

        # Count current listing cards
        current_count = await _count_listing_cards(page, feed_selector)

        if current_count == previous_count:
            stable_count += 1
            logger.debug(f"  Scroll #{scroll_num + 1}: {current_count} cards (stable: {stable_count}/{SCROLL_STABLE_CHECKS})")

            if stable_count >= SCROLL_STABLE_CHECKS:
                # Check for "end of results" indicator
                end_reached = await _check_end_of_results(page)
                if end_reached or stable_count >= SCROLL_STABLE_CHECKS + 2:
                    logger.info(f"  [OK] All results loaded after {scroll_num + 1} scrolls")
                    break
        else:
            stable_count = 0
            logger.debug(f"  Scroll #{scroll_num + 1}: {current_count} cards (+{current_count - previous_count})")

        previous_count = current_count

        # Occasional human-like interaction during scrolling
        if random.random() < 0.15:
            await random_mouse_move(page)

    return await _count_listing_cards(page, feed_selector)


async def _count_listing_cards(page, feed_selector: str) -> int:
    """Count the number of listing cards currently in the feed."""
    try:
        # Google Maps listing cards have a specific structure
        cards = page.locator(f"{feed_selector} > div > div[jsaction]")
        count = await cards.count()
        if count == 0:
            # Fallback selector
            cards = page.locator(f"{feed_selector} a[href*='/maps/place/']")
            count = await cards.count()
        return count
    except Exception:
        return 0


async def _check_end_of_results(page) -> bool:
    """Check if we've reached the end of the results list."""
    try:
        # Google shows "You've reached the end of the list" or similar
        end_el = page.locator(
            "span.HlvSq, p.fontBodyMedium:has-text('end of'), "
            "div:has-text('No more results')"
        ).first
        return await end_el.is_visible(timeout=1000)
    except Exception:
        return False


async def _extract_all_listings(
    page, feed_selector: str, area: str, query: str, all_results: list
) -> int:
    """
    Iterate through all listing cards, click each one,
    extract full details, and append to results.
    """
    count = 0

    # Get all listing links (more reliable than cards for clicking)
    listing_links = page.locator(f"{feed_selector} a[href*='/maps/place/']")
    total = await listing_links.count()

    if total == 0:
        # Fallback: try card-level elements
        listing_links = page.locator(f"{feed_selector} > div > div[jsaction]")
        total = await listing_links.count()

    logger.info(f"  [i] Processing {total} listings...")

    limit = cfg.MAX_LISTINGS_PER_QUERY if cfg.MAX_LISTINGS_PER_QUERY > 0 else total

    for i in range(min(total, limit)):
        logger.info(f"\n  -- Listing {i + 1}/{min(total, limit)} --")

        try:
            # Re-query the listings (DOM may have changed after back-navigation)
            current_links = page.locator(f"{feed_selector} a[href*='/maps/place/']")
            current_count = await current_links.count()

            if i >= current_count:
                # Try fallback selector
                current_links = page.locator(f"{feed_selector} > div > div[jsaction]")
                current_count = await current_links.count()
                if i >= current_count:
                    logger.warning(f"  [!] Listing {i + 1} not found, stopping")
                    break

            card = current_links.nth(i)

            # Scroll the card into view
            try:
                await card.scroll_into_view_if_needed(timeout=3000)
                await random_delay(0.5, 1.0)
            except Exception:
                pass

            # -- Extract card-level preview data --
            card_name = ""
            try:
                # Prioritize getting the aria-label which is the business name of the link card
                card_name = await card.get_attribute("aria-label", timeout=2000)
                if not card_name:
                    name_el = card.locator(".qBF1Pd, .fontHeadlineSmall").first
                    card_name = await name_el.inner_text(timeout=1000)
            except Exception:
                pass

            # -- Check for duplicates before clicking into detail --
            if card_name and _is_duplicate(card_name, area, all_results):
                logger.info(f"  [SKIP] Pre-emptive skip duplicate: {card_name}")
                continue

            # -- Extract full details --
            data = await extract_listing_detail(page, card, area, query)

            if data and data.get("name"):
                # Double-check duplicate with full name
                if not _is_duplicate(data["name"], area, all_results):
                    all_results.append(data)
                    count += 1
                    logger.info(f"  [+] [{count}] {data['name']}")
                    
                    # Immediate Supabase Sync (falls back to local mode automatically)
                    from supabase_manager import upsert_to_supabase
                    upserted = upsert_to_supabase(data)
                    if upserted:
                        logger.debug(f"    Pushed successfully to Supabase")
                    
                    # Immediate local json write for real-time local map dashboard updates
                    try:
                        from data_manager import export_json
                        export_json(all_results)
                    except Exception:
                        pass
                else:
                    logger.info(f"  [SKIP] Duplicate: {data['name']}")
            else:
                logger.warning(f"  [!] No data extracted for listing {i + 1}")

            # -- Navigate back to results --
            backed = await go_back_to_results(page)
            if not backed:
                logger.warning("  [!] Could not go back, re-searching...")
                # Re-run the search
                await page.goto(MAPS_URL, wait_until="load", timeout=60000)
                await random_delay(*DELAY_PAGE_LOAD)
                await _handle_consent(page)
                sb = await _find_search_box(page)
                if sb:
                    await random_typing(page, sb, query)
                    await page.keyboard.press("Enter")
                    await random_delay(*DELAY_AFTER_SEARCH)

                    # Re-scroll to approximate position
                    for _ in range(min(i // 3, 10)):
                        await random_scroll(page, feed_selector)
                        await random_delay(0.3, 0.6)

            # -- Human-like pause between listings --
            await random_pause_between_listings(
                *DELAY_BETWEEN_LISTINGS
            )

        except Exception as e:
            logger.error(f"  [ERR] Error processing listing {i + 1}: {e}")
            # Try to recover by going back
            try:
                await go_back_to_results(page)
            except Exception:
                pass
            continue

    return count


def _is_duplicate(name: str, area: str, results: list) -> bool:
    """Check if a listing name already exists in results for the current area (case-insensitive)."""
    if not name:
        return False
    normalized_name = name.strip().lower()
    normalized_area = area.strip().lower()
    for r in results:
        # Check both name and area to allow same-name businesses in different parts of Hyderabad
        if r.get("name", "").strip().lower() == normalized_name and r.get("area", "").strip().lower() == normalized_area:
            return True
    return False
