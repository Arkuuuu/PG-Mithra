"""
Supabase Database Manager -- Handles cloud persistence in PostgreSQL.

If credentials are not provided or the connection fails, it falls back
gracefully to local file persistence.
"""

import logging
import hashlib
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Initialize client lazily to avoid exceptions at import-time
_supabase_client = None

def get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.debug("  Supabase credentials not configured in environment. Operating in Local-Only mode.")
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("[DB] Supabase client initialized successfully")
        return _supabase_client
    except Exception as e:
        logger.warning(f"[DB] Failed to initialize Supabase client: {e}. Falling back to Local-Only mode.")
        return None


def generate_unique_id(name: str, address: str) -> str:
    """Generate a stable MD5 hash ID based on name and address."""
    key = f"{name.strip().lower()}||{address.strip().lower()}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def upsert_to_supabase(item: dict) -> bool:
    """
    Upsert a single listing record into Supabase PostgreSQL.
    Returns True on success, False on failure/local mode.
    """
    client = get_supabase_client()
    if not client:
        return False

    name = item.get("name", "")
    addr = item.get("address_full") or item.get("address_short") or ""
    if not name:
        return False

    # Generate a stable uuid/hash key
    record_id = generate_unique_id(name, addr)

    # Cast fields to database formats safely
    payload = {
        "id": record_id,
        "name": name,
        "classification": item.get("classification") or "remaining",
        "rating": float(item["rating"]) if item.get("rating") else None,
        "review_count": int(item["review_count"]) if item.get("review_count") else 0,
        "category": item.get("category") or "",
        "address_short": item.get("address_short") or "",
        "address_full": item.get("address_full") or "",
        "phone": item.get("phone") or "",
        "website": item.get("website") or "",
        "hours": item.get("hours") or "",
        "price_level": item.get("price_level") or "",
        "plus_code": item.get("plus_code") or "",
        "latitude": float(item["latitude"]) if item.get("latitude") else None,
        "longitude": float(item["longitude"]) if item.get("longitude") else None,
        "google_maps_url": item.get("google_maps_url") or "",
        "photos_count": int(item["photos_count"]) if item.get("photos_count") else 0,
        "search_query": item.get("search_query") or "",
        "area": item.get("area") or "",
        "scraped_at": item.get("scraped_at") or datetime.now().isoformat(),
        "image_url": item.get("image_url") or "",
        "review_tags": item.get("review_tags") or "",
    }

    try:
        # Pushes with upsert behavior (conflict on 'id') to staging database first
        client.table("listings_staging").upsert(payload).execute()
        return True
    except Exception as e:
        logger.warning(f"[DB] Supabase staging push failed: {e}. Record will be synced locally.")
        return False


def fetch_supabase_listings() -> list:
    """
    Fetch all active listings from Supabase Staging to pre-populate local cache for deduplication.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        res = client.table("listings_staging").select("*").execute()
        listings = res.data if hasattr(res, "data") else []
        logger.info(f"[DB] Fetched {len(listings)} staging listings from Supabase")
        return listings
    except Exception as e:
        logger.warning(f"[DB] Failed to fetch staging listings: {e}")
        return []


def fetch_production_listings() -> list:
    """
    Fetch all approved master production listings from Supabase to serve the public dashboard.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        res = client.table("listings").select("*").execute()
        listings = res.data if hasattr(res, "data") else []
        logger.info(f"[DB] Fetched {len(listings)} master production listings from Supabase")
        return listings
    except Exception as e:
        logger.warning(f"[DB] Failed to fetch production listings: {e}")
        return []


# ─────────────────────────────────────────────
# Scraper Farm (Bot Farm) Telemetry & Orchestration Logic
# ─────────────────────────────────────────────

def register_worker(worker_id: str) -> bool:
    """Register a new scraping worker node."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        payload = {
            "worker_id": worker_id,
            "status": "idle",
            "current_area": "",
            "total_scraped": 0,
            "last_heartbeat": datetime.now().isoformat()
        }
        client.table("workers").upsert(payload).execute()
        return True
    except Exception as e:
        logger.warning(f"[DB] Failed to register worker: {e}")
        return False


def update_worker_heartbeat(worker_id: str, status: str, current_area: str, total_scraped: int) -> bool:
    """Update active telemetry heartbeat for a worker node."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        payload = {
            "worker_id": worker_id,
            "status": status,
            "current_area": current_area,
            "total_scraped": total_scraped,
            "last_heartbeat": datetime.now().isoformat()
        }
        client.table("workers").upsert(payload).execute()
        return True
    except Exception as e:
        logger.debug(f"[DB] Failed to update heartbeat: {e}")
        return False


def pull_next_task(worker_id: str) -> dict:
    """
    Atomically pull the next pending scraping task from the task queue.
    Invokes the RPC function to prevent race conditions.
    If no pending tasks exist, recycles completed tasks automatically.
    """
    client = get_supabase_client()
    if not client:
        return {}
    try:
        # 1. Attempt to pull next pending task
        res = client.rpc("pull_next_task", {"worker_name": worker_id}).execute()
        tasks = res.data if hasattr(res, "data") else []
        task = {}
        if isinstance(tasks, list) and len(tasks) > 0:
            task = tasks[0]
        elif isinstance(tasks, dict):
            task = tasks
            
        # 2. If no task returned, try recycling completed tasks
        if not task or not task.get("area"):
            logger.info("[DB] Task queue empty. Automatically recycling completed tasks for next loop sweep...")
            recycle_res = client.rpc("recycle_completed_tasks").execute()
            recycled_count = recycle_res.data if hasattr(recycle_res, "data") else 0
            logger.info(f"[DB] Recycled {recycled_count} completed tasks back to pending.")
            
            # Try pulling again after recycling
            res = client.rpc("pull_next_task", {"worker_name": worker_id}).execute()
            tasks = res.data if hasattr(res, "data") else []
            if isinstance(tasks, list) and len(tasks) > 0:
                task = tasks[0]
            elif isinstance(tasks, dict):
                task = tasks
                
        return task if task and task.get("area") else {}
    except Exception as e:
        logger.warning(f"[DB] Failed to pull task from cloud: {e}")
        return {}


def complete_task(area: str) -> bool:
    """Mark a task as completed in the Supabase queue."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.rpc("complete_task", {"area_name": area}).execute()
        return True
    except Exception as e:
        logger.warning(f"[DB] Failed to mark task complete: {e}")
        return False


def fetch_workers() -> list:
    """Fetch all worker statuses for the Admin panel."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = client.table("workers").select("*").order("last_heartbeat", desc=True).execute()
        return res.data if hasattr(res, "data") else []
    except Exception as e:
        logger.warning(f"[DB] Failed to fetch workers: {e}")
        return []


def fetch_tasks() -> list:
    """Fetch all scraping queue tasks for the Admin panel."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = client.table("tasks").select("*").order("id").execute()
        return res.data if hasattr(res, "data") else []
    except Exception as e:
        logger.warning(f"[DB] Failed to fetch tasks: {e}")
        return []


def replicate_staging_to_production() -> bool:
    """Execute SQL transaction to replicate and approve staging data into production table."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.rpc("approve_and_replicate_staging_data").execute()
        return True
    except Exception as e:
        logger.warning(f"[DB] Failed to run replication RPC: {e}")
        return False


# ─────────────────────────────────────────────
# SQL SCHEMA REFERENCE FOR THE USER
# ─────────────────────────────────────────────
SQL_CREATE_TABLE_SCHEMA = """
-- Run this SQL command in your Supabase SQL Editor:

-- 1. Main approved listings table
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    classification TEXT DEFAULT 'remaining',
    rating DOUBLE PRECISION,
    review_count INTEGER DEFAULT 0,
    category TEXT,
    address_short TEXT,
    address_full TEXT,
    phone TEXT,
    website TEXT,
    hours TEXT,
    price_level TEXT,
    plus_code TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    google_maps_url TEXT,
    photos_count INTEGER DEFAULT 0,
    search_query TEXT,
    area TEXT,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    image_url TEXT,
    review_tags TEXT
);
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public access" ON listings FOR ALL USING (true);

-- 2. Scraper worker staging table
CREATE TABLE IF NOT EXISTS listings_staging (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    classification TEXT DEFAULT 'remaining',
    rating DOUBLE PRECISION,
    review_count INTEGER DEFAULT 0,
    category TEXT,
    address_short TEXT,
    address_full TEXT,
    phone TEXT,
    website TEXT,
    hours TEXT,
    price_level TEXT,
    plus_code TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    google_maps_url TEXT,
    photos_count INTEGER DEFAULT 0,
    search_query TEXT,
    area TEXT,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    image_url TEXT,
    review_tags TEXT
);
ALTER TABLE listings_staging ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public access to staging" ON listings_staging FOR ALL USING (true);

-- 3. Workers Telemetry Table
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'idle',
    current_area TEXT,
    total_scraped INTEGER DEFAULT 0,
    last_heartbeat TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE workers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public access to workers" ON workers FOR ALL USING (true);

-- 4. Tasks Orchestration Queue Table
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    area TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, in_progress, completed
    assigned_worker TEXT REFERENCES workers(worker_id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public access to tasks" ON tasks FOR ALL USING (true);

-- 5. RPC Function: Pull Next Task (locks row to prevent worker race conditions)
CREATE OR REPLACE FUNCTION pull_next_task(worker_name TEXT)
RETURNS TABLE (
    id INT,
    area TEXT,
    status TEXT,
    assigned_worker TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    UPDATE tasks
    SET status = 'in_progress',
        assigned_worker = worker_name,
        started_at = NOW()
    WHERE tasks.id = (
        SELECT t.id
        FROM tasks t
        WHERE t.status = 'pending'
        ORDER BY t.id ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *;
END;
$$ LANGUAGE plpgsql;

-- 6. RPC Function: Complete Task
CREATE OR REPLACE FUNCTION complete_task(area_name TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE tasks
    SET status = 'completed',
        completed_at = NOW()
    WHERE area = area_name;
END;
$$ LANGUAGE plpgsql;

-- 7. RPC Function: Approve and Replicate Staging Data
CREATE OR REPLACE FUNCTION approve_and_replicate_staging_data()
RETURNS VOID AS $$
BEGIN
    INSERT INTO listings
    SELECT * FROM listings_staging
    ON CONFLICT (id) DO UPDATE SET
        classification = EXCLUDED.classification,
        rating = EXCLUDED.rating,
        review_count = EXCLUDED.review_count,
        phone = EXCLUDED.phone,
        website = EXCLUDED.website,
        hours = EXCLUDED.hours,
        image_url = EXCLUDED.image_url,
        review_tags = EXCLUDED.review_tags;
END;
$$ LANGUAGE plpgsql;

-- 8. Initialize Task Queue with Madhapur Areas
INSERT INTO tasks (area) VALUES
    ('Madhapur Ayyappa Society'),
    ('Madhapur Kavuri Hills'),
    ('Madhapur Siddhi Vinayak Nagar'),
    ('Madhapur Image Gardens'),
    ('Madhapur Hitech City Metro'),
    ('Madhapur Mastan Nagar'),
    ('Madhapur Patrika Nagar'),
    ('Madhapur Vittal Rao Nagar'),
    ('Madhapur Silicon Valley'),
    ('Madhapur Sector 1'),
    ('Madhapur Sector 2'),
    ('Madhapur Sector 3'),
    ('Madhapur HUDA Techno Enclave'),
    ('Madhapur VIP Hills'),
    ('Madhapur Metro Station')
ON CONFLICT (area) DO NOTHING;
"""
