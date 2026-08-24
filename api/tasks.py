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

        tasks = []
        try:
            from supabase_manager import fetch_tasks
            tasks = fetch_tasks()
        except Exception as e:
            print(f"[!] Vercel API: Failed to fetch tasks: {e}")

        self.wfile.write(json.dumps({"tasks": tasks}).encode('utf-8'))
