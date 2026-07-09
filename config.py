import os

# Load .env file manually into os.environ if it exists in the current directory
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    # Strip quotes if present in env values
                    val = val.strip().strip('"').strip("'")
                    os.environ[key.strip()] = val
    except Exception:
        pass

# ─────────────────────────────────────────────
# Supabase Configuration (loaded safely via environment variables)
# ─────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ─────────────────────────────────────────────
# Target Areas — Hyderabad localities & micro-localities
# ─────────────────────────────────────────────
HYDERABAD_AREAS = [
    # Madhapur micro-areas - TARGET ZONE
    "Madhapur Ayyappa Society",
    "Madhapur Kavuri Hills",
    "Madhapur Siddhi Vinayak Nagar",
    "Madhapur Image Gardens",
    "Madhapur Hitech City Metro",
    "Madhapur Mastan Nagar",
    "Madhapur Patrika Nagar",
    "Madhapur Vittal Rao Nagar",
    "Madhapur Silicon Valley",
    "Madhapur Sector 1",
    "Madhapur Sector 2",
    "Madhapur Sector 3",
    "Madhapur HUDA Techno Enclave",
    "Madhapur VIP Hills",
    "Madhapur Metro Station",

    # Other areas (Disabled for now to focus entirely on Madhapur)
    # "Gachibowli DLF Phase 1",
    # "Gachibowli Indira Nagar",
    # "Gachibowli Telecom Nagar",
    # "Gachibowli Financial District",
    # "Kondapur Botanical Garden",
    # "Kondapur Raghavendra Colony",
    # "Kondapur Masjid Banda",
    # "Kukatpally Housing Board Colony",
    # "Kukatpally JNTU",
    # "Kukatpally Pragathi Nagar",
    # "Ameerpet Maitrivanam",
    # "Ameerpet Satyam Theatre Road",
    # "SR Nagar Community Hall",
    # "SR Nagar BK Guda Colony",
    # "Begumpet Prakash Nagar",
    # "Begumpet SP Road",
    # "Miyapur Allwyn Colony",
    # "Miyapur JP Nagar",
    # "Manikonda Lanco Hills",
    # "Manikonda Puppalguda",
    # "Nanakramguda IT Corridor",
    # "Nanakramguda Financial District",
    # "Jubilee Hills Road No 36",
    # "Banjara Hills Road No 12",
    # "Secunderabad SP Road",
    # "Dilsukhnagar Metro Station",
    # "LB Nagar Kamineni Hospital",
    # "Tarnaka Osmania University",
    # "Uppal Ring Road",
]

# ─────────────────────────────────────────────
# Search Query Templates
# ─────────────────────────────────────────────
SEARCH_TEMPLATES = [
    "PG in {area} Hyderabad",
    "Hostel in {area} Hyderabad",
    "Paying guest in {area} Hyderabad",
]

# ─────────────────────────────────────────────
# Delay Ranges (seconds) — used by anti_detect
# ─────────────────────────────────────────────
DELAY_BETWEEN_ACTIONS = (1.5, 3.5)       # General action gap
DELAY_BETWEEN_KEYSTROKES = (0.04, 0.18)  # Typing speed per character
DELAY_AFTER_SEARCH = (3.0, 6.0)          # Wait for results to load
DELAY_BETWEEN_LISTINGS = (2.0, 5.0)      # Pause between clicking listings
DELAY_BETWEEN_SCROLLS = (0.8, 2.0)       # Scroll pause
DELAY_BETWEEN_AREAS = (8.0, 15.0)        # Longer pause between area switches
DELAY_PAGE_LOAD = (2.0, 4.0)             # Wait after navigation

# ─────────────────────────────────────────────
# Scroll Configuration
# ─────────────────────────────────────────────
SCROLL_STEP_MIN = 300    # Minimum pixels per scroll
SCROLL_STEP_MAX = 700    # Maximum pixels per scroll
MAX_SCROLLS = 35         # Give up after this many scrolls per query
SCROLL_STABLE_CHECKS = 3 # How many no-new-results scrolls before stopping

# ─────────────────────────────────────────────
# Browser / Stealth Settings
# ─────────────────────────────────────────────
HEADLESS = True  # Set False for debugging

# Pool of realistic viewport sizes
VIEWPORT_POOL = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 800},
    {"width": 1600, "height": 900},
]

# Pool of realistic Chrome user-agent strings (Windows / Mac)
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Chrome launch flags for anti-fingerprinting
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-infobars",
    "--disable-background-networking",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
    "--lang=en-IN",
]

# ─────────────────────────────────────────────
# Proxy (optional) — fill in to use
# Format: "http://user:pass@host:port"
# ─────────────────────────────────────────────
PROXY = None  # e.g. "http://user:pass@proxy.example.com:8080"

# ─────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────
OUTPUT_DIR = "./output"
OUTPUT_CSV = "pg_hostel_data.csv"
OUTPUT_JSON = "pg_hostel_data.json"
OUTPUT_XLSX = "pg_hostel_data.xlsx"

# ─────────────────────────────────────────────
# Limits
# ─────────────────────────────────────────────
MAX_LISTINGS_PER_QUERY = 0  # 0 = no limit (scrape all found)

# Google Maps base URL
MAPS_URL = "https://www.google.com/maps"
