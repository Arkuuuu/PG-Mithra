"""
Google Maps PG & Hostel Scraper -- Main Entry Point

Orchestrates the full scraping pipeline:
  1. Launch stealth browser
  2. For each area → run all search queries
  3. Deduplicate and export results
  4. Print summary

Usage:
    python main.py                              # Full Hyderabad run (headless)
    python main.py --headed                     # Visible browser for debugging
    python main.py --areas "Madhapur,Gachibowli" # Specific areas only
    python main.py --max-listings 5             # Limit per query (for testing)
    python main.py --output-dir ./my_output     # Custom output directory
"""

import asyncio
import argparse
import logging
import sys
import random
from datetime import datetime

from config import (
    HYDERABAD_AREAS,
    DELAY_BETWEEN_AREAS,
    MAX_LISTINGS_PER_QUERY,
    OUTPUT_DIR,
)
from browser_stealth import launch_stealth_browser, close_browser
from scraper import scrape_area
from panning_scraper import scrape_maps_panning
from nobroker_scraper import scrape_nobroker_area
from zolostays_scraper import scrape_zolostays_area
from anti_detect import random_delay, random_page_interaction
from data_manager import (
    deduplicate,
    merge_results,
    export_csv,
    export_json,
    export_excel,
    sync_local_files_with_supabase,
    load_existing_results,
    print_summary,
)
import threading
import time
import socket

# -- Shared Worker State for Heartbeat Telemetry --
worker_state = {
    "worker_id": "",
    "status": "idle",
    "current_area": "",
    "total_scraped": 0,
    "active": False
}

def heartbeat_daemon(state):
    """Background thread sending periodic check-in telemetry updates to Supabase."""
    from supabase_manager import update_worker_heartbeat
    while state["active"]:
        try:
            update_worker_heartbeat(
                state["worker_id"],
                state["status"],
                state["current_area"],
                state["total_scraped"]
            )
        except Exception:
            pass
        # Sleep 30s with safety interrupts
        for _ in range(30):
            if not state["active"]:
                break
            time.sleep(1)


# -- Logging setup --
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO

    # Force UTF-8 on the console stream to avoid cp1252 encoding errors on Windows
    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(utf8_stdout),
            logging.FileHandler("scraper.log", encoding="utf-8"),
        ],
    )


async def main(args):
    """Main async entry point."""

    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    # -- Determine areas to scrape --
    if args.areas:
        areas = [a.strip() for a in args.areas.split(",")]
    else:
        areas = list(HYDERABAD_AREAS)

    # Shuffle areas to avoid predictable access patterns
    random.shuffle(areas)

    # -- Override max listings if set --
    if args.max_listings:
        import config
        config.MAX_LISTINGS_PER_QUERY = args.max_listings

    output_dir = args.output_dir or OUTPUT_DIR
    headless = not args.headed

    logger.info(f"{'='*60}")
    logger.info(f"[>>] Google Maps PG & Hostel Scraper")
    logger.info(f"{'='*60}")
    logger.info(f"  Areas:       {len(areas)} ({', '.join(areas[:5])}{'...' if len(areas) > 5 else ''})")
    logger.info(f"  Headless:    {headless}")
    logger.info(f"  Output:      {output_dir}")
    logger.info(f"  Max/query:   {args.max_listings or 'unlimited'}")
    logger.info(f"  Started at:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}\n")
    # -- Load existing results for incremental scraping --
    all_results = load_existing_results(output_dir)

    # -- Initialize Worker Node Telemetry --
    hostname = socket.gethostname()
    random_id = "".join(random.choices("0123456789ABCDEF", k=4))
    worker_id = f"{hostname}-{random_id}"

    from supabase_manager import register_worker, pull_next_task, complete_task
    
    register_worker(worker_id)
    worker_state["worker_id"] = worker_id
    worker_state["status"] = "idle"
    worker_state["total_scraped"] = len(all_results)
    worker_state["active"] = True

    # Start background heartbeat reporting thread
    heartbeat_thread = threading.Thread(target=heartbeat_daemon, args=(worker_state,), daemon=True)
    heartbeat_thread.start()
    logger.info(f"[TELEMETRY] Registered worker node: {worker_id}")

    loop_count = 1
    try:
        while True:
            # Check if using dynamic queue (default when --areas is not specified)
            use_dynamic_queue = (args.areas is None)
            
            if use_dynamic_queue:
                logger.info("\n[QUEUE] Querying Supabase central tasks table for work...")
                worker_state["status"] = "idle"
                worker_state["current_area"] = ""
                
                area = pull_next_task(worker_id)
                if not area:
                    logger.info("[QUEUE] No pending tasks available. Waiting 45s before checking again...")
                    worker_state["status"] = "cooldown"
                    await asyncio.sleep(45)
                    continue
                
                areas_to_scrape = [area]
                logger.info(f"[QUEUE] Claimed task area from queue: {area}")
            else:
                areas_to_scrape = list(areas)
                # Shuffle local areas for random execution order
                random.shuffle(areas_to_scrape)
                logger.info(f"\n[LOCAL] Local area queue sequence #{loop_count} starting")

            # -- Launch browser for this scraping iteration --
            pw = browser = context = page = None
            try:
                pw, browser, context, page = await launch_stealth_browser(headless=headless)

                # -- Scrape each area --
                for idx, area in enumerate(areas_to_scrape, 1):
                    logger.info(f"\n{'#'*60}")
                    logger.info(f"# AREA: {area}")
                    logger.info(f"{'#'*60}")

                    worker_state["status"] = "scraping"
                    worker_state["current_area"] = area

                    try:
                         # Run matching scrapers dynamically based on CLI selection
                         source = getattr(args, "source", "all").lower()
                         area_count = 0
                         
                         if source in ["all", "maps"]:
                             count = await scrape_area(page, area, all_results)
                             area_count += count
                             
                         if source in ["all", "panning"]:
                             count = await scrape_maps_panning(page, area, all_results)
                             area_count += count
                             
                         if source in ["all", "nobroker"]:
                             count = await scrape_nobroker_area(page, area, all_results)
                             area_count += count
                             
                         if source in ["all", "zolo"]:
                             count = await scrape_zolostays_area(page, area, all_results)
                             area_count += count

                         logger.info(f"  [STAT] Area '{area}': {area_count} total listings extracted across sources")
                         
                         # Update telemetry counts
                         worker_state["total_scraped"] = len(all_results)
                         
                         # Mark complete in Supabase task queue
                         if use_dynamic_queue:
                             complete_task(area)
                    except Exception as e:
                        logger.error(f"  [ERR] Error scraping area '{area}': {e}")
                        # Try to recover by creating a new page
                        try:
                            await page.close()
                            page = await context.new_page()
                            from playwright_stealth import Stealth
                            await Stealth().apply_stealth_async(page)
                        except Exception:
                            logger.error("  [ERR] Could not recover, stopping loop area iteration")
                            break

                    # -- Incremental save and cloud synchronization after each area --
                    all_results = sync_local_files_with_supabase(all_results, output_dir)
                    worker_state["total_scraped"] = len(all_results)

                    # -- Pause between areas --
                    if idx < len(areas_to_scrape):
                        pause = await random_delay(*DELAY_BETWEEN_AREAS)
                        logger.info(f"  [WAIT] Area pause: {pause:.1f}s before next area")

                        # Occasional random interaction during area pause
                        if random.random() < 0.5:
                            await random_page_interaction(page)

            except Exception as e:
                logger.error(f"[ERR] Error in browser execution sequence: {e}")
            finally:
                # -- Close browser to release resources and avoid detection during cooldown --
                if pw and browser:
                    await close_browser(pw, browser)

            if not args.loop:
                break

            loop_count += 1
            # Add some jitter to loop interval
            jitter_interval = args.loop_interval + random.randint(-120, 120)
            logger.info(f"\n⏳ Loop cycle complete. Cooldown for {jitter_interval} seconds before next run...")
            worker_state["status"] = "cooldown"
            worker_state["current_area"] = ""
            await asyncio.sleep(max(10, jitter_interval))

    except KeyboardInterrupt:
        logger.info("\n\n[!] Interrupted by user -- preparing final export...")

    except Exception as e:
        logger.error(f"\n[ERR] Fatal error in execution: {e}")

    finally:
        # Stop telemetry reporting
        worker_state["active"] = False
        
        # -- Final export and cloud synchronization --
        if all_results:
            all_results = sync_local_files_with_supabase(all_results, output_dir)
            print_summary(all_results)
        else:
            logger.warning("[!] No results were collected.")

    logger.info(f"\n[OK] Scraping complete at {datetime.now().strftime('%H:%M:%S')}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Google Maps PG & Hostel Scraper -- Hyderabad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                  Full run (all areas, headless)
  python main.py --headed                         Show browser window
  python main.py --areas "Madhapur,Gachibowli"    Specific areas only
  python main.py --max-listings 5                 Quick test (5 per query)
  python main.py --verbose                        Debug-level logging
        """,
    )
    parser.add_argument(
        "--areas",
        type=str,
        default=None,
        help="Comma-separated list of areas to scrape (default: all Hyderabad areas)",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["all", "maps", "panning", "nobroker", "zolo"],
        default="all",
        help="Target data source/method to execute (default: all)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser in headed (visible) mode for debugging",
    )
    parser.add_argument(
        "--max-listings",
        type=int,
        default=None,
        help="Max listings per search query (default: unlimited)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable debug-level logging",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        default=False,
        help="Run continuously in 24/7 loop mode",
    )
    parser.add_argument(
        "--loop-interval",
        type=int,
        default=1800,
        help="Cooldown interval in seconds between loops (default: 1800 / 30 mins)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
