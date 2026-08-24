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

        success = False
        try:
            from supabase_manager import replicate_staging_to_production
            success = replicate_staging_to_production()
        except Exception as e:
            print(f"[!] Vercel API: Replication error: {e}")

        self.wfile.write(json.dumps({"success": success}).encode('utf-8'))
