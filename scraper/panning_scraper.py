import logging
import asyncio
import random
from datetime import datetime
from supabase_manager import generate_unique_id
from anti_detect import random_delay, random_typing
from scraper import _find_search_box, _find_feed_selector, _scroll_results_feed, _extract_all_listings, _handle_consent
import config as cfg

logger = logging.getLogger(__name__)

# Center geolocations for Madhapur sectors/societies
AREA_COORDINATES = {
    "Madhapur Ayyappa Society": (17.4483, 78.3908),
    "Madhapur Kavuri Hills": (17.4422, 78.3965),
    "Madhapur Siddhi Vinayak Nagar": (17.4465, 78.3842),
    "Madhapur Image Gardens": (17.4435, 78.3888),
    "Madhapur Hitech City Metro": (17.4430, 78.3815),
    "Madhapur Mastan Nagar": (17.4498, 78.3952),
    "Madhapur Patrika Nagar": (17.4480, 78.3802),
    "Madhapur Vittal Rao Nagar": (17.4452, 78.3855),
    "Madhapur Silicon Valley": (17.4495, 78.3780),
    "Madhapur Sector 1": (17.4510, 78.3820),
    "Madhapur Sector 2": (17.4530, 78.3850),
    "Madhapur Sector 3": (17.4550, 78.3880),
    "Madhapur HUDA Techno Enclave": (17.4455, 78.3755),
    "Madhapur VIP Hills": (17.4482, 78.3920),
    "Madhapur Metro Station": (17.4432, 78.3822),
}

async def execute_single_cell_extraction(page, area: str, all_results: list) -> int:
    """Executes search-this-area and listing extraction across multi-synonym queries for a single cell."""
    search_this_area_selectors = [
        "button:has-text('Search this area')",
        "span:has-text('Search this area')",
        "button[jsaction*='searchthisarea']",
        "button.uE3aBe"
    ]
    
    queries = ["PG", "Hostel", "Gents PG", "Ladies PG"]
    total_cell_count = 0

    for query in queries:
        logger.info(f"    [Cell Search] Sweeping query '{query}' for cell {area}...")
        
        search_box = await _find_search_box(page)
        if search_box:
            try:
                await search_box.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await random_typing(page, search_box, query)
                await random_delay(0.5, 1.0)
                await page.keyboard.press("Enter")
                await random_delay(3.0, 5.0)
            except Exception as e:
                logger.debug(f"    [Cell Search] Search box query failed: {e}")

        # Relentless search-this-area clicker loop per query
        for attempt in range(1, 3):
            btn_clicked = False
            for selector in search_this_area_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        logger.info(f"    [Cell Search] Clicked 'Search this area' ({query})")
                        btn_clicked = True
                        break
                except Exception:
                    continue
            
            await random_delay(3.0, 4.5)
            
            feed_selector = await _find_feed_selector(page)
            if feed_selector:
                cards = await _scroll_results_feed(page, feed_selector)
                if cards > 0:
                    count = await _extract_all_listings(page, feed_selector, area, f"{query} Cell ({area})", all_results)
                    total_cell_count += count
                    logger.info(f"    [Cell Search] Extracted {count} listings for '{query}'.")
                    break
            else:
                await asyncio.sleep(1.5)

    logger.info(f"    [Cell Search] Total extracted in cell: {total_cell_count} listings across all queries.")
    return total_cell_count


async def scrape_maps_panning(page, area: str, all_results: list, cell_coords: tuple = None) -> int:
    """
    Perform a geographic grid-panning search on Google Maps.
    Centers viewport, runs generic 'PG' query, and pans maps to trigger local pin updates.
    """
    # 1. Retrieve center coordinates
    if cell_coords:
        lat, lon = cell_coords
        logger.info(f"[Panning] Loading exact Coordinate Cell: {lat}, {lon} for {area}")
        grid_mode = False
    else:
        coords = AREA_COORDINATES.get(area)
        if not coords:
            coords = (17.4483, 78.3908)
        lat, lon = coords
        grid_mode = True
        
    zoom = 18 # High zoom for residential level detail
    
    url = f"https://www.google.com/maps/@{lat},{lon},{zoom}z"
    logger.info(f"[Panning] Loading Maps: {url}")
    
    await page.goto(url, wait_until="load", timeout=60000)
    await random_delay(4.0, 6.0)
    await _handle_consent(page)
    
    search_box = await _find_search_box(page)
    if not search_box:
        logger.error("[Panning] Search box not found, skipping panning search")
        return 0
        
    # Search generic keyword 'PG'
    await random_typing(page, search_box, "PG")
    await random_delay(0.5, 1.0)
    await page.keyboard.press("Enter")
    await random_delay(4.0, 6.0)
    
    if not grid_mode:
        return await execute_single_cell_extraction(page, area, all_results)
        
    total_scraped = 0
    
    # 2. Grid loop: Pan maps in 3x3 pattern using Arrow inputs
    # Panning coordinates grid: [Center, East, South, West, North, North-East, South-East...]
    directions = [
        [], # Start at center
        ["ArrowRight"], # East
        ["ArrowDown"],  # South
        ["ArrowLeft", "ArrowLeft"], # West
        ["ArrowUp", "ArrowUp"], # North
        ["ArrowRight"], # North-East
        ["ArrowDown", "ArrowDown"], # South-East
    ]
    
    for idx, pan_keys in enumerate(directions, 1):
        logger.info(f"  [Panning] Processing grid step {idx}/7...")
        
        # Simulate map panning
        for key in pan_keys:
            await page.keyboard.press(key)
            await asyncio.sleep(0.5)
            
        await random_delay(1.5, 3.0)
        
        # Click "Search this area" button if visible
        search_this_area_selectors = [
            "button:has-text('Search this area')",
            "span:has-text('Search this area')",
            "button[jsaction*='searchthisarea']",
            "button.uE3aBe"
        ]
        
        btn_clicked = False
        for selector in search_this_area_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    logger.info("    [Panning] Clicked 'Search this area'")
                    btn_clicked = True
                    break
            except Exception:
                continue
                
        # Wait for map update results to compile
        await random_delay(3.0, 5.0)
        
        # Retrieve results
        feed_selector = await _find_feed_selector(page)
        if not feed_selector:
            logger.debug("    [Panning] No scrollable results feed found for this grid coordinate")
            continue
            
        # Extract listings found in this grid sector
        cards = await _scroll_results_feed(page, feed_selector)
        if cards > 0:
            count = await _extract_all_listings(page, feed_selector, area, f"PG Grid-panning ({area})", all_results)
            total_scraped += count
            logger.info(f"    [Panning] Extracted {count} listings in this step.")
            
    logger.info(f"[Panning] Finished: Scraped {total_scraped} total listings for area {area}")
    return total_scraped
