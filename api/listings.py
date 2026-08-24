from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        data = None
        try:
            from supabase_manager import fetch_production_listings
            cloud_data = fetch_production_listings()
            if cloud_data:
                data = {"listings": cloud_data}
        except Exception as e:
            print(f"[!] Vercel API: Supabase listings fetch error: {e}")

        if not data:
            data = {"listings": []}

        self.wfile.write(json.dumps(data).encode('utf-8'))
