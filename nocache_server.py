"""Simple HTTP file server with no-cache headers on every response."""
import http.server
import os

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

if __name__ == '__main__':
    os.chdir('/Users/ssr/Projects/WorkingBot')
    server = http.server.HTTPServer(('', 8080), NoCacheHandler)
    print('Serving /Users/ssr/Projects/WorkingBot on port 8080 (no-cache)')
    server.serve_forever()
