import logging
import asyncio
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime
from supabase_manager import generate_unique_id
from anti_detect import random_delay, random_typing

logger = logging.getLogger(__name__)

async def scrape_nobroker_area(page, area: str, all_results: list) -> int:
    """
    Scrape PG listings from NoBroker for a specific area in Hyderabad.
    Uses direct URL navigation and DOM parsing as fallback.
    """
    # 1. Format area slug for NoBroker URL
    # e.g., "Madhapur Sector 1" -> "madhapur-sector-1"
    area_slug = area.lower().replace(" ", "-").replace(",", "")
    url = f"https://www.nobroker.in/pg-for-rent-in-{area_slug}_hyderabad"
    
    logger.info(f"[NoBroker] Navigating to: {url}")
    
    # Intercept API calls to capture JSON payload directly if possible
    captured_listings = []
    
    async def handle_response(response):
        if "api/v1/property/filter" in response.url or "/filter/pg" in response.url:
            try:
                text = await response.text()
                data = json.loads(text)
                properties = data.get("data", []) or data.get("properties", [])
                if properties:
                    logger.info(f"  [NoBroker API] Intercepted {len(properties)} properties from API response!")
                    captured_listings.extend(properties)
            except Exception as e:
                logger.debug(f"  [NoBroker API] Intercept parsing error: {e}")

    page.on("response", handle_response)
    
    try:
        await page.goto(url, wait_until="commit", timeout=40000)
        await random_delay(4.0, 7.0)
    except Exception as e:
        logger.warning(f"  [NoBroker] Page load timeout/error: {e}")

    # Remove handler to avoid leaks
    page.remove_listener("response", handle_response)

    count = 0

    # 2. Process API Intercepts if captured
    if captured_listings:
        for prop in captured_listings:
            name = prop.get("propertyTitle") or prop.get("title")
            if not name:
                continue
            
            # Format address
            address = prop.get("secondaryTitle") or prop.get("street") or area
            record_id = generate_unique_id(name, address)
            
            # Parse gender/type
            gender = "colive"
            sub_type = str(prop.get("type", "")).lower()
            if "girls" in sub_type or "female" in sub_type:
                gender = "women"
            elif "boys" in sub_type or "male" in sub_type:
                gender = "men"
                
            lat = prop.get("latitude")
            lon = prop.get("longitude")
            
            # Rent amount
            rent = prop.get("rent") or prop.get("price") or 0
            
            payload = {
                "id": record_id,
                "name": name,
                "classification": gender,
                "rating": None,
                "review_count": 0,
                "category": "NoBroker Portal",
                "address_short": address,
                "address_full": address,
                "phone": "",
                "website": f"https://www.nobroker.in/property/rent/{prop.get('id')}",
                "hours": "",
                "price_level": f"₹{rent}/month" if rent else "",
                "plus_code": "",
                "latitude": float(lat) if lat else None,
                "longitude": float(lon) if lon else None,
                "google_maps_url": f"https://www.nobroker.in/property/rent/{prop.get('id')}",
                "photos_count": 0,
                "search_query": f"PG in {area}",
                "area": area,
                "scraped_at": datetime.now().isoformat(),
                "image_url": "",
                "review_tags": ""
            }
            
            # Deduplicate locally
            if not any(item["id"] == record_id for item in all_results):
                all_results.append(payload)
                count += 1
                
        if count > 0:
            logger.info(f"  [NoBroker] Extracted {count} listings via API intercept.")
            return count

    # 3. Fallback: Parse DOM directly
    logger.info("  [NoBroker] No API data intercepted. Parsing webpage DOM...")
    try:
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select("article.item, div[itemtype='http://schema.org/Place'], div.property-card")
        
        for card in cards:
            title_el = card.select_one("h2.heading-6, .heading-8, [itemprop='name']")
            if not title_el:
                continue
            name = title_el.text.strip()
            
            addr_el = card.select_one(".nb-address, [itemprop='address']")
            address = addr_el.text.strip() if addr_el else area
            
            record_id = generate_unique_id(name, address)
            
            link_el = card.select_one("a[href*='/property/']")
            href = f"https://www.nobroker.in{link_el.get('href')}" if link_el else url
            
            price_el = card.select_one(".rent, #minimumRent, div:contains('₹')")
            rent_text = price_el.text.strip() if price_el else ""
            
            gender = "colive"
            card_text = card.text.lower()
            if "girls" in card_text or "female" in card_text or "ladies" in card_text:
                gender = "women"
            elif "boys" in card_text or "male" in card_text or "gents" in card_text:
                gender = "men"
                
            payload = {
                "id": record_id,
                "name": name,
                "classification": gender,
                "rating": None,
                "review_count": 0,
                "category": "NoBroker Portal",
                "address_short": address,
                "address_full": address,
                "phone": "",
                "website": href,
                "hours": "",
                "price_level": rent_text,
                "plus_code": "",
                "latitude": None,
                "longitude": None,
                "google_maps_url": href,
                "photos_count": 0,
                "search_query": f"PG in {area}",
                "area": area,
                "scraped_at": datetime.now().isoformat(),
                "image_url": "",
                "review_tags": ""
            }
            
            if not any(item["id"] == record_id for item in all_results):
                all_results.append(payload)
                count += 1
                
        logger.info(f"  [NoBroker] Extracted {count} listings via DOM parsing.")
    except Exception as e:
        logger.warning(f"  [NoBroker] DOM parsing failed: {e}")
        
    return count
