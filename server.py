#!/usr/bin/env python3
"""
EconStats Web Server - serves the app and proxies FRED API requests
Uses Claude to interpret natural language economic queries like an economist
"""

import http.server
import json
import os
import socketserver
from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs
from urllib.error import HTTPError, URLError

PORT = 8000
FRED_API_KEY = 'c43c82548c611ec46800c51f898026d6'
FRED_BASE = 'https://api.stlouisfed.org/fred'

# Get Anthropic API key from environment or use configured key
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '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')

ECONOMIST_PROMPT = """You are an expert economist helping interpret a user's question about economic data. Your job is to determine what FRED (Federal Reserve Economic Data) series would best answer their question.

Think like Jason Furman or a top policy economist. Consider:
- What data would actually answer this question?
- What's the right measure? (e.g., for jobs: payrolls vs household survey, for inflation: CPI vs PCE, headline vs core)
- Should we show levels, growth rates, or year-over-year changes?
- Are there demographic or sector breakdowns that would be relevant?
- What time period makes sense?

IMPORTANT FRED SERIES TO KNOW:
- Jobs: PAYEMS (nonfarm payrolls), UNRATE (unemployment), LNS12300060 (prime-age employment ratio)
- Women: LNS14000002 (women unemployment), LNS12300062 (women prime-age EPOP), LNS11300002 (women LFPR)
- Men: LNS14000001 (men unemployment), LNS12300061 (men prime-age EPOP)
- Inflation: CPIAUCSL (CPI), CPILFESL (core CPI), PCEPI (PCE), PCEPILFE (core PCE)
- GDP: GDPC1 (real GDP), A191RL1Q225SBEA (GDP growth rate)
- Rates: FEDFUNDS (fed funds), DGS10 (10yr Treasury), DGS2 (2yr), MORTGAGE30US (mortgage)
- Housing: CSUSHPINSA (Case-Shiller home prices), HOUST (housing starts)
- Sectors: MANEMP (manufacturing), USCONS (construction), USEHS (education/health), USLAH (leisure/hospitality)
- Consumer: RSXFS (retail sales), UMCSENT (consumer sentiment), PSAVERT (saving rate)
- Other: JTSJOL (job openings), M2SL (money supply), SP500 (stocks), BOPGSTB (trade balance)

For any topic not in the list above, provide good FRED search terms.

Respond with JSON only, in this exact format:
{
  "series": ["SERIES_ID1", "SERIES_ID2"],
  "search_terms": ["term1", "term2"],
  "explanation": "Brief explanation of why these series answer the question",
  "show_yoy": false,
  "combine_chart": false
}

- "series": Known FRED series IDs that answer the question (up to 4)
- "search_terms": If you're not sure of exact IDs, provide search terms for FRED API (up to 3)
- "explanation": 1-2 sentences on what the data shows and why it's relevant
- "show_yoy": true if year-over-year change is more meaningful than levels (e.g., for price indices)
- "combine_chart": true if series should be shown on same chart (same units, directly comparable)

USER QUESTION: """

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        # Proxy FRED API requests
        if parsed.path.startswith('/api/'):
            self.proxy_fred_request(parsed)
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/interpret':
            self.interpret_query()
        else:
            self.send_response(404)
            self.end_headers()

    def interpret_query(self):
        """Use Claude to interpret the economic question like an expert economist"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            query = data.get('query', '')

            if not query:
                self.send_json_response({'error': 'No query provided'}, 400)
                return

            if not ANTHROPIC_API_KEY:
                # Fall back to simple response if no API key
                self.send_json_response({
                    'series': [],
                    'search_terms': [query],
                    'explanation': 'Search FRED for: ' + query,
                    'show_yoy': False,
                    'combine_chart': False
                })
                return

            # Call Claude API
            result = self.call_claude(query)
            self.send_json_response(result)

        except Exception as e:
            print(f"Interpret error: {e}")
            self.send_json_response({'error': str(e)}, 500)

    def call_claude(self, query):
        """Call Claude API to interpret the economic question"""
        url = 'https://api.anthropic.com/v1/messages'

        payload = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 1024,
            'messages': [
                {'role': 'user', 'content': ECONOMIST_PROMPT + query}
            ]
        }

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        }

        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')

        try:
            with urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['content'][0]['text']

                # Parse JSON from response
                # Handle case where Claude might wrap in markdown
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0]
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0]

                return json.loads(content.strip())

        except HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            print(f"Claude API error: {e.code} - {error_body}")
            return {
                'series': [],
                'search_terms': [query],
                'explanation': f'AI interpretation unavailable, searching for: {query}',
                'show_yoy': False,
                'combine_chart': False
            }
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return {
                'series': [],
                'search_terms': [query],
                'explanation': 'Search FRED for: ' + query,
                'show_yoy': False,
                'combine_chart': False
            }

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def proxy_fred_request(self, parsed):
        # Convert /api/series/observations to FRED endpoint
        endpoint = parsed.path.replace('/api/', '')
        query = parsed.query

        # Add API key
        if query:
            url = f"{FRED_BASE}/{endpoint}?{query}&api_key={FRED_API_KEY}&file_type=json"
        else:
            url = f"{FRED_BASE}/{endpoint}?api_key={FRED_API_KEY}&file_type=json"

        try:
            req = Request(url, headers={'User-Agent': 'EconStats/1.0'})
            with urlopen(req, timeout=30) as response:
                data = response.read()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)

        except HTTPError as e:
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n  EconStats running at http://localhost:{PORT}")
        if ANTHROPIC_API_KEY:
            print(f"  AI economist interpretation: ENABLED")
        else:
            print(f"  AI economist interpretation: DISABLED")
            print(f"  Set ANTHROPIC_API_KEY environment variable to enable")
        print(f"  Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
