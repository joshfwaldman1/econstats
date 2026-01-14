#!/usr/bin/env python3
"""
EconStats - Natural Language Economic Data Tool

Ask questions in plain English and get charts of economic data from FRED.

Usage:
    python econstats.py "What is the current unemployment rate?"
    python econstats.py "Show me inflation over the last 10 years"
    python econstats.py "Compare GDP and unemployment"
    python econstats.py --interactive

Environment:
    Set FRED_API_KEY environment variable with your FRED API key
    Get a key at: https://fred.stlouisfed.org/docs/api/api_key.html

Requirements:
    pip install matplotlib
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


BASE_URL = "https://api.stlouisfed.org/fred"

# Common economic indicators mapped to FRED series IDs
SERIES_MAPPINGS = {
    # Unemployment
    "unemployment": "UNRATE",
    "unemployment rate": "UNRATE",
    "jobless": "UNRATE",
    "jobless rate": "UNRATE",
    "jobs": "PAYEMS",
    "employment": "PAYEMS",
    "nonfarm payrolls": "PAYEMS",
    "payrolls": "PAYEMS",
    "labor force": "CLF16OV",
    "initial claims": "ICSA",
    "jobless claims": "ICSA",

    # Inflation & Prices
    "inflation": "CPIAUCSL",
    "cpi": "CPIAUCSL",
    "consumer price": "CPIAUCSL",
    "consumer prices": "CPIAUCSL",
    "core inflation": "CPILFESL",
    "core cpi": "CPILFESL",
    "pce": "PCEPI",
    "pce inflation": "PCEPI",
    "core pce": "PCEPILFE",
    "producer prices": "PPIACO",
    "ppi": "PPIACO",

    # GDP & Growth
    "gdp": "GDP",
    "gross domestic product": "GDP",
    "real gdp": "GDPC1",
    "gdp growth": "A191RL1Q225SBEA",
    "economic growth": "A191RL1Q225SBEA",

    # Interest Rates
    "interest rate": "FEDFUNDS",
    "interest rates": "FEDFUNDS",
    "fed funds": "FEDFUNDS",
    "fed funds rate": "FEDFUNDS",
    "federal funds": "FEDFUNDS",
    "federal funds rate": "FEDFUNDS",
    "prime rate": "DPRIME",
    "10 year": "DGS10",
    "10 year treasury": "DGS10",
    "10 year yield": "DGS10",
    "2 year": "DGS2",
    "2 year treasury": "DGS2",
    "30 year mortgage": "MORTGAGE30US",
    "mortgage rate": "MORTGAGE30US",
    "mortgage rates": "MORTGAGE30US",

    # Housing
    "housing": "HOUST",
    "housing starts": "HOUST",
    "home prices": "CSUSHPINSA",
    "house prices": "CSUSHPINSA",
    "case shiller": "CSUSHPINSA",
    "existing home sales": "EXHOSLUSM495S",
    "new home sales": "HSN1F",

    # Stock Market
    "stock market": "SP500",
    "stocks": "SP500",
    "s&p": "SP500",
    "s&p 500": "SP500",
    "sp500": "SP500",
    "dow": "DJIA",
    "dow jones": "DJIA",
    "nasdaq": "NASDAQCOM",
    "vix": "VIXCLS",
    "volatility": "VIXCLS",

    # Money & Banking
    "money supply": "M2SL",
    "m2": "M2SL",
    "m1": "M1SL",
    "bank lending": "TOTLL",
    "commercial lending": "TOTLL",

    # Trade & International
    "trade balance": "BOPGSTB",
    "trade deficit": "BOPGSTB",
    "exports": "BOPGEXP",
    "imports": "BOPGIMP",
    "dollar": "DTWEXBGS",
    "dollar index": "DTWEXBGS",
    "exchange rate": "DTWEXBGS",

    # Consumer & Retail
    "retail sales": "RSXFS",
    "consumer confidence": "UMCSENT",
    "consumer sentiment": "UMCSENT",
    "personal income": "PI",
    "personal spending": "PCE",
    "savings rate": "PSAVERT",

    # Industrial
    "industrial production": "INDPRO",
    "capacity utilization": "TCU",
    "manufacturing": "IPMAN",
    "durable goods": "DGORDER",

    # Debt
    "national debt": "GFDEBTN",
    "federal debt": "GFDEBTN",
    "government debt": "GFDEBTN",
    "debt to gdp": "GFDEGDQ188S",

    # Canada specific (from user's example)
    "canada": "NGDPSAXDCCAQ",
    "canada gdp": "NGDPSAXDCCAQ",
    "canadian": "NGDPSAXDCCAQ",
}

# Dashboard queries - general questions that show multiple indicators
DASHBOARD_QUERIES = {
    "economy": ["A191RL1Q225SBEA", "UNRATE", "CPIAUCSL"],  # GDP growth, unemployment, inflation
    "economic overview": ["A191RL1Q225SBEA", "UNRATE", "CPIAUCSL"],
    "how is the economy": ["A191RL1Q225SBEA", "UNRATE", "CPIAUCSL"],
    "economy doing": ["A191RL1Q225SBEA", "UNRATE", "CPIAUCSL"],
    "economic health": ["A191RL1Q225SBEA", "UNRATE", "CPIAUCSL"],
    "recession": ["A191RL1Q225SBEA", "UNRATE", "ICSA"],  # GDP growth, unemployment, jobless claims
    "labor market": ["UNRATE", "PAYEMS", "ICSA"],  # unemployment, payrolls, claims
    "job market": ["UNRATE", "PAYEMS", "ICSA"],
    "market overview": ["SP500", "DGS10", "VIXCLS"],  # S&P, 10yr treasury, VIX
    "financial markets": ["SP500", "DGS10", "VIXCLS"],
    "monetary policy": ["FEDFUNDS", "M2SL", "DGS10"],  # fed funds, money supply, 10yr
    "fed policy": ["FEDFUNDS", "M2SL", "DGS10"],
    "price stability": ["CPIAUCSL", "PCEPI", "PPIACO"],  # CPI, PCE, PPI
    "cost of living": ["CPIAUCSL", "CSUSHPINSA", "MORTGAGE30US"],  # CPI, home prices, mortgage
}

# Time period parsing
TIME_PATTERNS = [
    (r"last (\d+) years?", lambda m: int(m.group(1)) * 365),
    (r"past (\d+) years?", lambda m: int(m.group(1)) * 365),
    (r"(\d+) years?", lambda m: int(m.group(1)) * 365),
    (r"last (\d+) months?", lambda m: int(m.group(1)) * 30),
    (r"past (\d+) months?", lambda m: int(m.group(1)) * 30),
    (r"(\d+) months?", lambda m: int(m.group(1)) * 30),
    (r"last (\d+) days?", lambda m: int(m.group(1))),
    (r"ytd|year to date", lambda m: (datetime.now() - datetime(datetime.now().year, 1, 1)).days),
    (r"since (\d{4})", lambda m: (datetime.now() - datetime(int(m.group(1)), 1, 1)).days),
    (r"from (\d{4})", lambda m: (datetime.now() - datetime(int(m.group(1)), 1, 1)).days),
]


def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("Error: FRED_API_KEY environment variable not set.")
        print("Get your free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        sys.exit(1)
    return api_key


def make_request(endpoint: str, params: dict) -> dict:
    """Make a request to the FRED API and return JSON response."""
    params["api_key"] = get_api_key()
    params["file_type"] = "json"

    url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"

    try:
        req = Request(url, headers={"User-Agent": "EconStats/1.0"})
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 400:
            try:
                error_data = json.loads(e.read().decode("utf-8"))
                return {"error": error_data.get("error_message", "Bad request")}
            except:
                return {"error": "Bad request"}
        elif e.code == 429:
            return {"error": "Rate limit exceeded. Please wait and try again."}
        return {"error": f"HTTP Error {e.code}"}
    except URLError as e:
        return {"error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def parse_time_period(query: str) -> Optional[int]:
    """Extract time period from query, returns days."""
    query_lower = query.lower()
    for pattern, days_func in TIME_PATTERNS:
        match = re.search(pattern, query_lower)
        if match:
            return days_func(match)
    return None


def identify_series(query: str) -> List[str]:
    """Identify FRED series IDs from a natural language query."""
    query_lower = query.lower()
    found_series = []

    # First check for dashboard queries (general economy questions)
    sorted_dashboard = sorted(DASHBOARD_QUERIES.items(), key=lambda x: len(x[0]), reverse=True)
    for phrase, series_list in sorted_dashboard:
        if phrase in query_lower:
            return series_list  # Return the full dashboard

    # Check for comparison keywords
    is_comparison = any(word in query_lower for word in ["compare", "versus", "vs", "and", "against"])

    # Try exact phrase matches (longer phrases first)
    sorted_mappings = sorted(SERIES_MAPPINGS.items(), key=lambda x: len(x[0]), reverse=True)

    for phrase, series_id in sorted_mappings:
        if phrase in query_lower and series_id not in found_series:
            found_series.append(series_id)
            if not is_comparison and len(found_series) >= 1:
                break
            if is_comparison and len(found_series) >= 3:
                break

    return found_series


def search_series(query: str, limit: int = 5) -> List[dict]:
    """Search FRED for series matching the query."""
    data = make_request("series/search", {
        "search_text": query,
        "limit": limit,
        "order_by": "popularity",
        "sort_order": "desc"
    })
    return data.get("seriess", [])


def get_series_info(series_id: str) -> Optional[dict]:
    """Get metadata for a series."""
    data = make_request("series", {"series_id": series_id})
    series_list = data.get("seriess", [])
    return series_list[0] if series_list else None


def get_observations(series_id: str, days_back: Optional[int] = None, limit: int = 1000) -> Tuple[List[str], List[float], dict]:
    """Get observations for a series. Returns (dates, values, metadata)."""
    params = {
        "series_id": series_id,
        "limit": limit,
        "sort_order": "asc"
    }

    if days_back:
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        params["observation_start"] = start_date

    # Get series info
    info = get_series_info(series_id)
    if not info:
        return [], [], {"error": f"Series {series_id} not found"}

    # Get observations
    data = make_request("series/observations", params)

    if "error" in data:
        return [], [], {"error": data["error"]}

    observations = data.get("observations", [])

    dates = []
    values = []
    for obs in observations:
        try:
            val = float(obs["value"])
            dates.append(obs["date"])
            values.append(val)
        except (ValueError, KeyError):
            continue

    return dates, values, info


def create_chart(series_data: List[Tuple[str, List[str], List[float], dict]],
                 title: str = "",
                 save_path: Optional[str] = None,
                 dark_mode: bool = False) -> None:
    """Create a chart from series data."""
    if not HAS_MATPLOTLIB:
        print("\nMatplotlib not installed. Install with: pip install matplotlib")
        print("Showing data in text format instead:\n")
        for series_id, dates, values, info in series_data:
            print(f"\n{info.get('title', series_id)}:")
            print(f"  Latest: {values[-1]:,.2f} ({dates[-1]})")
            if len(values) > 1:
                change = values[-1] - values[0]
                pct_change = (change / values[0]) * 100 if values[0] != 0 else 0
                print(f"  Change: {change:+,.2f} ({pct_change:+.1f}%)")
        return

    # Apply dark mode theme
    if dark_mode:
        plt.style.use('dark_background')
        bg_color = '#1a1a2e'
        face_color = '#16213e'
        text_color = '#e8e8e8'
        grid_color = '#404040'
        source_color = '#888888'
        colors = ['#00d4ff', '#ff6b6b', '#4ade80', '#fbbf24', '#a78bfa']
    else:
        plt.style.use('default')
        bg_color = 'white'
        face_color = '#FAFAFA'
        text_color = 'black'
        grid_color = 'gray'
        source_color = 'gray'
        colors = ['#2E86AB', '#E94F37', '#28A745', '#FFC107', '#6C757D']

    # Use subplots for 3+ series (dashboard view), otherwise single plot
    use_subplots = len(series_data) >= 3

    if use_subplots:
        fig, axes = plt.subplots(len(series_data), 1, figsize=(12, 3 * len(series_data)), sharex=True)
        fig.patch.set_facecolor(bg_color)
        if len(series_data) == 1:
            axes = [axes]
    else:
        fig, ax1 = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor(bg_color)
        axes = [ax1]

        # If comparing 2 series with different units, use dual axis
        use_dual_axis = False
        if len(series_data) == 2:
            units1 = series_data[0][3].get('units', '')
            units2 = series_data[1][3].get('units', '')
            if units1 != units2:
                use_dual_axis = True
                ax2 = ax1.twinx()
                axes.append(ax2)

    for i, (series_id, dates, values, info) in enumerate(series_data):
        if not dates or not values:
            continue

        # Parse dates
        try:
            date_objects = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        except ValueError:
            continue

        if use_subplots:
            ax = axes[i]
        else:
            ax = axes[min(i, len(axes) - 1)]
        color = colors[i % len(colors)]

        label = info.get('title', series_id)
        if len(label) > 50:
            label = label[:47] + "..."

        ax.plot(date_objects, values, color=color, linewidth=2, label=label)

        if use_subplots:
            ax.set_ylabel(info.get('units_short', info.get('units', '')[:15]), color=text_color, fontsize=9)
            ax.set_title(label, fontsize=11, fontweight='bold', color=text_color, loc='left')
            ax.set_facecolor(face_color)
            ax.grid(True, alpha=0.3, color=grid_color)
            ax.tick_params(axis='both', labelcolor=text_color)
            for spine in ax.spines.values():
                spine.set_color(grid_color)
        else:
            ax.set_ylabel(info.get('units', ''), color=color if (not use_subplots and len(series_data) == 2 and series_data[0][3].get('units', '') != series_data[1][3].get('units', '')) else text_color)
            if not use_subplots and len(series_data) == 2 and series_data[0][3].get('units', '') != series_data[1][3].get('units', ''):
                ax.tick_params(axis='y', labelcolor=color)
            else:
                ax.tick_params(axis='y', labelcolor=text_color)
            ax.tick_params(axis='x', labelcolor=text_color)

    # Formatting
    if use_subplots:
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)
        if title:
            fig.suptitle(title, fontsize=14, fontweight='bold', color=text_color)
        else:
            fig.suptitle("Economic Dashboard", fontsize=14, fontweight='bold', color=text_color)
    else:
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        axes[0].xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)

        # Title
        if title:
            plt.title(title, fontsize=14, fontweight='bold', color=text_color)
        elif len(series_data) == 1:
            plt.title(series_data[0][3].get('title', ''), fontsize=14, fontweight='bold', color=text_color)

    # Legend and styling (only for non-subplot mode)
    if not use_subplots:
        legend_kwargs = {'loc': 'upper left', 'facecolor': face_color, 'edgecolor': grid_color}
        if dark_mode:
            legend_kwargs['labelcolor'] = text_color
        if len(series_data) > 1:
            lines1, labels1 = axes[0].get_legend_handles_labels()
            if len(axes) > 1:
                lines2, labels2 = axes[1].get_legend_handles_labels()
                axes[0].legend(lines1 + lines2, labels1 + labels2, **legend_kwargs)
            else:
                axes[0].legend(**legend_kwargs)

        axes[0].grid(True, alpha=0.3, color=grid_color)
        axes[0].set_facecolor(face_color)
        for spine in axes[0].spines.values():
            spine.set_color(grid_color)

    plt.tight_layout()

    # Add source annotation
    plt.figtext(0.99, 0.01, 'Source: Federal Reserve Economic Data (FRED)',
                ha='right', va='bottom', fontsize=8, color=source_color)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"\nChart saved to: {save_path}")
    else:
        plt.show()


def print_summary(series_data: List[Tuple[str, List[str], List[float], dict]]) -> None:
    """Print a text summary of the data."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for series_id, dates, values, info in series_data:
        if not values:
            print(f"\n{series_id}: No data available")
            continue

        title = info.get('title', series_id)
        units = info.get('units', '')

        print(f"\n{title}")
        print("-" * min(len(title), 60))
        print(f"  Latest Value:  {values[-1]:,.2f} {units} ({dates[-1]})")

        if len(values) >= 2:
            # Period change
            change = values[-1] - values[0]
            pct_change = (change / values[0]) * 100 if values[0] != 0 else 0
            print(f"  Period Start:  {values[0]:,.2f} {units} ({dates[0]})")
            print(f"  Change:        {change:+,.2f} ({pct_change:+.1f}%)")

        if len(values) >= 12:
            # Statistics
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            print(f"  Average:       {avg:,.2f}")
            print(f"  Range:         {min_val:,.2f} to {max_val:,.2f}")


def answer_question(query: str, save_chart: Optional[str] = None, no_chart: bool = False, dark_mode: bool = False) -> None:
    """Process a natural language question and display answer with chart."""
    print(f"\nAnalyzing: \"{query}\"\n")

    # Try to identify series from keywords
    series_ids = identify_series(query)

    # If no matches, search FRED
    if not series_ids:
        print("Searching FRED database...")
        # Extract key terms for search
        search_terms = re.sub(r'\b(what|is|the|show|me|how|has|been|over|last|past|years?|months?|current|recent|trend)\b',
                             '', query.lower())
        search_terms = ' '.join(search_terms.split())

        results = search_series(search_terms)
        if results:
            series_ids = [results[0]['id']]
            print(f"Found: {results[0]['title']}")
        else:
            print("Could not find relevant economic data series.")
            print("\nTry asking about: unemployment, inflation, GDP, interest rates, housing, stocks, etc.")
            return

    # Parse time period
    days_back = parse_time_period(query)
    if not days_back:
        days_back = 5 * 365  # Default to 5 years

    # Fetch data for each series
    series_data = []
    for series_id in series_ids:
        print(f"Fetching {series_id}...")
        dates, values, info = get_observations(series_id, days_back)
        if dates and values:
            series_data.append((series_id, dates, values, info))
        elif "error" in info:
            print(f"  Error: {info['error']}")

    if not series_data:
        print("No data retrieved. Please check series availability.")
        return

    # Print summary
    print_summary(series_data)

    # Create chart
    if not no_chart:
        create_chart(series_data, save_path=save_chart, dark_mode=dark_mode)


def interactive_mode(dark_mode: bool = False) -> None:
    """Run in interactive mode."""
    print("\n" + "=" * 60)
    print("  EconStats - Natural Language Economic Data Tool")
    print("=" * 60)
    print("\nAsk questions about economic data in plain English.")
    print("Examples:")
    print("  - What is the current unemployment rate?")
    print("  - Show me inflation over the last 10 years")
    print("  - Compare GDP and unemployment since 2020")
    print("  - How has the stock market performed this year?")
    print("\nType 'quit' or 'exit' to leave.\n")

    while True:
        try:
            query = input("Question: ").strip()
            if not query:
                continue
            if query.lower() in ('quit', 'exit', 'q'):
                print("Goodbye!")
                break
            answer_question(query, dark_mode=dark_mode)
            print()
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="EconStats - Ask economic questions, get data charts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "What is the unemployment rate?"
  %(prog)s "Show me inflation over the last 10 years"
  %(prog)s "Compare GDP and unemployment"
  %(prog)s "How has S&P 500 performed since 2020?" --dark
  %(prog)s --interactive --dark
  %(prog)s "housing starts" --save housing.png

Common topics: unemployment, inflation, GDP, interest rates,
housing, stocks, consumer confidence, retail sales, etc.

Get your free FRED API key at:
https://fred.stlouisfed.org/docs/api/api_key.html
        """
    )

    parser.add_argument("question", nargs="?", help="Your question about economic data")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--save", "-s", metavar="FILE", help="Save chart to file (PNG, PDF, etc.)")
    parser.add_argument("--no-chart", action="store_true", help="Show only text summary, no chart")
    parser.add_argument("--dark", "-d", action="store_true", help="Use dark mode theme for charts")
    parser.add_argument("--list-topics", action="store_true", help="List available topic keywords")

    args = parser.parse_args()

    if args.list_topics:
        print("\nAvailable Topics (keywords you can use in questions):\n")
        topics = sorted(set(SERIES_MAPPINGS.keys()))
        for i, topic in enumerate(topics):
            print(f"  {topic}", end="")
            if (i + 1) % 4 == 0:
                print()
        print("\n")
        return

    if args.interactive:
        interactive_mode(dark_mode=args.dark)
    elif args.question:
        answer_question(args.question, save_chart=args.save, no_chart=args.no_chart, dark_mode=args.dark)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
