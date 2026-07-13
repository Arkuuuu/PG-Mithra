import os
import logging
from supabase_manager import get_supabase_client
from panning_scraper import AREA_COORDINATES

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("GridGenerator")

def generate_coordinate_tasks(step_size=0.0018, grid_radius=2):
    """
    Calculate and upload a grid of coordinate task cells for each target area.
    grid_radius=2 generates a 5x5 grid (25 cells) around each center.
    At zoom 18, each cell is approx 200m wide, ensuring 100% coverage without gaps.
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not configured. Set URL and KEY in .env.")
        return

    logger.info("Initializing coordinate grid calculation...")
    tasks_to_insert = []

    for area, (center_lat, center_lon) in AREA_COORDINATES.items():
        logger.info(f"Generating cell grid for: {area}...")
        
        # Grid range: -grid_radius to +grid_radius
        for dx in range(-grid_radius, grid_radius + 1):
            for dy in range(-grid_radius, grid_radius + 1):
                # Calculate cell coordinates
                cell_lat = center_lat + (dy * step_size)
                cell_lon = center_lon + (dx * step_size)
                
                # Name the task distinctively
                cell_name = f"{area} - Cell [Lat: {cell_lat:.5f}, Lon: {cell_lon:.5f}]"
                
                tasks_to_insert.append({
                    "area": cell_name,
                    "status": "pending",
                    "latitude": cell_lat,
                    "longitude": cell_lon
                })

    logger.info(f"Generated {len(tasks_to_insert)} total cell coordinate tasks.")
    
    # Upload to Supabase tasks table in chunks to avoid payload size constraints
    chunk_size = 50
    inserted_count = 0
    
    for i in range(0, len(tasks_to_insert), chunk_size):
        chunk = tasks_to_insert[i:i+chunk_size]
        try:
            # Insert with upsert/ignore on conflicts
            res = client.table("tasks").upsert(
                chunk, 
                on_conflict="area"
            ).execute()
            inserted_count += len(chunk)
            logger.info(f"  Uploaded tasks chunk {i//chunk_size + 1}: {inserted_count}/{len(tasks_to_insert)}")
        except Exception as e:
            logger.warning(f"  Error inserting chunk: {e}")

    logger.info(f"Successfully populated task queue database with {inserted_count} coordinate cells!")

if __name__ == "__main__":
    generate_coordinate_tasks()
