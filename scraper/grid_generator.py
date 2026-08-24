import os
import logging
from supabase_manager import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("GridGenerator")

# Center centroid of Hyderabad (Hussain Sagar / Khairatabad region)
HYDERABAD_CENTER = (17.4126, 78.4727)

def generate_coordinate_tasks(step_size=0.0018, max_rings=35):
    """
    Generate coordinate cells in concentric square rings expanding outwards from the Hyderabad center.
    This guarantees workers systematic progression starting from the center outward.
    - step_size=0.0018 (approx 200m per cell at zoom level 18)
    - max_rings=35 covers a 7km radius, generating 5,041 cells.
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not configured. Set URL and KEY in .env.")
        return

    logger.info(f"Generating concentric grid cells from Hyderabad Center {HYDERABAD_CENTER}...")
    tasks_to_insert = []
    center_lat, center_lon = HYDERABAD_CENTER

    # 1. Generate grid cells ring-by-ring
    for r in range(max_rings + 1):
        if r == 0:
            # Center cell
            cell_name = f"Hyderabad Center - Cell [Lat: {center_lat:.5f}, Lon: {center_lon:.5f}]"
            tasks_to_insert.append({
                "area": cell_name,
                "status": "pending",
                "latitude": center_lat,
                "longitude": center_lon
            })
            continue

        # For ring r, cells lie on the boundary of the square of offset radius r
        # dy ranges from -r to r, dx has boundary values, and vice versa.
        ring_cells = []
        for offset in range(-r, r + 1):
            # Top boundary (dy = r, dx = offset)
            ring_cells.append((offset, r))
            # Bottom boundary (dy = -r, dx = offset)
            ring_cells.append((offset, -r))
            # Left boundary (dx = -r, dy = offset, excluding corners already captured)
            if offset not in (-r, r):
                ring_cells.append((-r, offset))
            # Right boundary (dx = r, dy = offset, excluding corners already captured)
            if offset not in (-r, r):
                ring_cells.append((r, offset))

        for dx, dy in ring_cells:
            cell_lat = center_lat + (dy * step_size)
            cell_lon = center_lon + (dx * step_size)
            cell_name = f"Hyd Ring {r} - Cell [Lat: {cell_lat:.5f}, Lon: {cell_lon:.5f}]"
            
            tasks_to_insert.append({
                "area": cell_name,
                "status": "pending",
                "latitude": cell_lat,
                "longitude": cell_lon
            })

    logger.info(f"Calculated {len(tasks_to_insert)} concentric coordinate cells.")
    
    # 2. Upload to Supabase tasks table in bulk chunks
    chunk_size = 200
    inserted_count = 0
    
    for i in range(0, len(tasks_to_insert), chunk_size):
        chunk = tasks_to_insert[i:i+chunk_size]
        try:
            res = client.table("tasks").upsert(
                chunk, 
                on_conflict="area"
            ).execute()
            inserted_count += len(chunk)
            logger.info(f"  Uploaded tasks chunk {i//chunk_size + 1}: {inserted_count}/{len(tasks_to_insert)}")
        except Exception as e:
            logger.warning(f"  Error inserting chunk: {e}")

    logger.info(f"Successfully populated task queue database with {inserted_count} concentric cells!")

if __name__ == "__main__":
    generate_coordinate_tasks()
