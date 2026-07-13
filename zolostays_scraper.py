import logging
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from supabase_manager import generate_unique_id
from anti_detect import random_delay

logger = logging.getLogger(__name__)

# Map broad Hyderabad areas to Zolostays subpages
ZOLO_AREA_MAPPING = {
    "madhapur": "pgs-in-madhapur-hyderabad",
    "gachibowli": "pgs-in-gachibowli-hyderabad",
    "kondapur": "pgs-in-kondapur-hyderabad",
    "kukatpally": "pgs-in-kukatpally-hyderabad",
    "hitech": "pgs-in-hitech-city-hyderabad",
}

async def scrape_zolostays_area(page, area: str, all_results: list) -> int:
    """
    Scrape branded co-living properties from Zolostays.
    Uses card DOM parsers on zolostays.com.
    """
    # 1. Resolve Zolo URL based on Hyderabad area
    area_lower = area.lower()
    zolo_slug = "pgs-in-madhapur-hyderabad" # default fallback
    for keyword, slug in ZOLO_AREA_MAPPING.items():
        if keyword in area_lower:
            zolo_slug = slug
            break
            
    url = f"https://zolostays.com/{zolo_slug}"
    logger.info(f"[Zolostays] Navigating to: {url}")
    
    try:
        await page.goto(url, wait_until="commit", timeout=40000)
        await random_delay(4.0, 7.0)
        
        # Scroll page to trigger lazy loading cards
        for _ in range(3):
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1.5)
            
    except Exception as e:
        logger.warning(f"  [Zolostays] Page load/scroll timeout: {e}")

    count = 0
    try:
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select("a.property-card-link")
        
        logger.info(f"  [Zolostays] Found {len(cards)} property cards on page.")
        
        for card in cards:
            title_el = card.select_one(".local-name")
            if not title_el:
                continue
            name = title_el.text.strip()
            
            # Format URLs
            href = card.get("href")
            link = f"https://zolostays.com{href}" if href else url
            
            # Gender parsing
            gender = "colive"
            gender_el = next((span for span in card.select("span") 
                             if any(g in span.text.upper() for g in ["UNISEX", "LADIES", "GENTS", "MENS", "WOMENS"])), None)
            if gender_el:
                g_text = gender_el.text.upper()
                if "LADIES" in g_text or "WOMENS" in g_text:
                    gender = "women"
                elif "GENTS" in g_text or "MENS" in g_text:
                    gender = "men"
            
            # Rent pricing
            price_el = card.select_one(".price")
            rent_text = f"₹{price_el.text.strip()}/month" if price_el else ""
            
            # Address location descriptor
            loc_el = next((span for span in card.select("span") if "PG in" in span.text), None)
            address = loc_el.text.strip() if loc_el else f"Zolostays {area}"
            
            record_id = generate_unique_id(name, address)
            
            payload = {
                "id": record_id,
                "name": name,
                "classification": gender,
                "rating": None,
                "review_count": 0,
                "category": "Zolostays Portal",
                "address_short": address,
                "address_full": address,
                "phone": "",
                "website": link,
                "hours": "",
                "price_level": rent_text,
                "plus_code": "",
                "latitude": None,
                "longitude": None,
                "google_maps_url": link,
                "photos_count": 0,
                "search_query": f"Zolo PG in {area}",
                "area": area,
                "scraped_at": datetime.now().isoformat(),
                "image_url": "",
                "review_tags": ""
            }
            
            if not any(item["id"] == record_id for item in all_results):
                all_results.append(payload)
                count += 1
                
        logger.info(f"  [Zolostays] Extracted {count} listings successfully.")
    except Exception as e:
        logger.warning(f"  [Zolostays] DOM parsing failed: {e}")
        
    return count
