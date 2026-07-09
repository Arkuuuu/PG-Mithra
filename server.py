"""
Local HTTP Server for Interactive PG & Hostel Map Dashboard.

Serves the dashboard UI at http://localhost:8000 and loads the
scraped data locally, preventing CORS issues.
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

import json

class DashboardHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # Serve global cloud data from Supabase, fall back to local file
        if self.path == '/api/listings':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            data = None
            try:
                # Import lazily to avoid startup crashes if libraries are missing
                from supabase_manager import fetch_production_listings
                cloud_data = fetch_production_listings()
                if cloud_data:
                    data = {"listings": cloud_data}
            except Exception as e:
                print(f"[!] Server API: Supabase load failed, falling back to local file: {e}")

            # Local fallback if Supabase is not configured or failed
            if not data:
                local_path = os.path.join(DIRECTORY, "output", "pg_hostel_data.json")
                if os.path.exists(local_path):
                    try:
                        with open(local_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception as e:
                        print(f"[!] Server API: Failed to read local JSON file: {e}")

            if not data:
                data = {"listings": []}

            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif self.path == '/api/workers':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            workers = []
            try:
                from supabase_manager import fetch_workers
                workers = fetch_workers()
            except Exception as e:
                print(f"[!] Server API: Failed to fetch workers: {e}")

            self.wfile.write(json.dumps({"workers": workers}).encode('utf-8'))

        elif self.path == '/api/tasks':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            tasks = []
            try:
                from supabase_manager import fetch_tasks
                tasks = fetch_tasks()
            except Exception as e:
                print(f"[!] Server API: Failed to fetch tasks: {e}")

            self.wfile.write(json.dumps({"tasks": tasks}).encode('utf-8'))

        elif self.path == '/api/staging':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            staging_listings = []
            try:
                from supabase_manager import fetch_supabase_listings
                staging_listings = fetch_supabase_listings()
            except Exception as e:
                print(f"[!] Server API: Failed to fetch staging listings: {e}")

            self.wfile.write(json.dumps({"listings": staging_listings}).encode('utf-8'))

        elif self.path == '/api/replicate':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            success = False
            try:
                from supabase_manager import replicate_staging_to_production
                success = replicate_staging_to_production()
            except Exception as e:
                print(f"[!] Server API: Replication error: {e}")

            self.wfile.write(json.dumps({"success": success}).encode('utf-8'))
        else:
            super().do_GET()

    def end_headers(self):
        # Allow CORS just in case
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def run_server():
    # Ensure stdout is UTF-8 to prevent console encode crashes
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    handler = DashboardHTTPRequestHandler
    
    # Enable socket re-use to avoid port bind conflicts
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"============================================================")
        print(f"🚀 PG & Hostel Map Dashboard Local Server Active")
        print(f"============================================================")
        print(f"  URL: http://localhost:{PORT}")
        print(f"  Directory: {DIRECTORY}")
        print(f"  Press Ctrl+C to stop the server")
        print(f"============================================================")
        
        # Open in default browser
        webbrowser.open(f"http://localhost:{PORT}")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user.")
            sys.exit(0)

if __name__ == "__main__":
    run_server()
