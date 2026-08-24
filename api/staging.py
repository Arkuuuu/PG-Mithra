from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import urllib.parse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if self.path.startswith('/api/staging/delete'):
            record_id = qs.get('id', [''])[0]
            success = False
            try:
                from supabase_manager import delete_staging_listing
                success = delete_staging_listing(record_id)
            except Exception as e:
                print(f"[!] Vercel API: Delete staging listing error: {e}")
            self.wfile.write(json.dumps({"success": success, "id": record_id}).encode('utf-8'))

        elif self.path.startswith('/api/staging/approve'):
            record_id = qs.get('id', [''])[0]
            success = False
            try:
                from supabase_manager import approve_single_staging_listing
                success = approve_single_staging_listing(record_id)
            except Exception as e:
                print(f"[!] Vercel API: Single approve listing error: {e}")
            self.wfile.write(json.dumps({"success": success, "id": record_id}).encode('utf-8'))

        else:
            staging_listings = []
            try:
                from supabase_manager import fetch_supabase_listings
                staging_listings = fetch_supabase_listings()
            except Exception as e:
                print(f"[!] Vercel API: Failed to fetch staging listings: {e}")
            self.wfile.write(json.dumps({"listings": staging_listings}).encode('utf-8'))
