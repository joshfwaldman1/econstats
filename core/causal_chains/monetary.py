"""
Monetary Policy Transmission Chains.

Structured representations of how Federal Reserve policy affects the economy
through various transmission mechanisms. Each chain models the sequence of
effects with typical lag times and relevant FRED series.

Chains:
1. RATE_TO_HOUSING - Fed policy → housing market → shelter inflation
2. RATE_TO_CONSUMPTION - Fed policy → credit conditions → consumer spending
3. RATE_TO_LABOR - Fed policy → business conditions → labor market

Usage:
    from core.causal_chains.monetary import (
        RATE_TO_HOUSING,
        RATE_TO_CONSUMPTION,
        RATE_TO_LABOR,
        detect_chain_position,
        explain_chain_position
    )

    position = detect_chain_position(RATE_TO_HOUSING, data)
    explanation = explain_chain_position('RATE_TO_HOUSING', position)
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta


# =============================================================================
# CHAIN DEFINITIONS
# Each stage has:
#   - stage: Human-readable description
#   - lag: Expected time range from Fed action to this stage responding
#   - series: Primary FRED series to monitor this stage
#   - direction: Expected direction of change when Fed HIKES (+ = increase, - = decrease)
#   - threshold: Minimum % change to consider "activated" (for rates/indices)
# =============================================================================

RATE_TO_HOUSING = [
    {
        'stage': 'Fed hikes rates',
        'lag': 'immediate',
        'lag_months': (0, 0),
        'series': 'FEDFUNDS',
        'direction': '+',
        'threshold': 0.25,
        'description': 'Federal Reserve raises the federal funds rate target'
    },
    {
        'stage': 'Treasury yields rise',
        'lag': '0-1 months',
        'lag_months': (0, 1),
        'series': 'DGS10',
        'direction': '+',
        'threshold': 0.10,
        'description': 'Long-term Treasury yields adjust to new rate expectations'
    },
    {
        'stage': 'Mortgage rates rise',
        'lag': '0-2 months',
        'lag_months': (0, 2),
        'series': 'MORTGAGE30US',
        'direction': '+',
        'threshold': 0.25,
        'description': '30-year fixed mortgage rates follow Treasury yields'
    },
    {
        'stage': 'Housing demand falls',
        'lag': '2-6 months',
        'lag_months': (2, 6),
        'series': 'EXHOSLUSM495S',  # Existing home sales
        'direction': '-',
        'threshold': -5.0,
        'description': 'Higher borrowing costs reduce homebuyer demand'
    },
    {
        'stage': 'Home prices cool',
        'lag': '6-12 months',
        'lag_months': (6, 12),
        'series': 'CSUSHPINSA',  # Case-Shiller
        'direction': '-',
        'threshold': -2.0,
        'description': 'Reduced demand slows home price appreciation'
    },
    {
        'stage': 'Shelter CPI responds',
        'lag': '12-24 months',
        'lag_months': (12, 24),
        'series': 'CUSR0000SAH1',  # Shelter CPI
        'direction': '-',
        'threshold': -1.0,
        'description': 'CPI shelter inflation (rent + OER) begins to decelerate'
    },
    {
        'stage': 'Core CPI eases',
        'lag': '18-30 months',
        'lag_months': (18, 30),
        'series': 'CPILFESL',  # Core CPI
        'direction': '-',
        'threshold': -0.5,
        'description': 'Shelter (~40% of core) pulls down overall core inflation'
    }
]


RATE_TO_CONSUMPTION = [
    {
        'stage': 'Fed hikes rates',
        'lag': 'immediate',
        'lag_months': (0, 0),
        'series': 'FEDFUNDS',
        'direction': '+',
        'threshold': 0.25,
        'description': 'Federal Reserve raises the federal funds rate target'
    },
    {
        'stage': 'Credit card rates rise',
        'lag': 'immediate',
        'lag_months': (0, 0),
        'series': 'TERMCBCCALLNS',  # Credit card interest rate
        'direction': '+',
        'threshold': 0.25,
        'description': 'Variable-rate credit cards adjust immediately to prime rate'
    },
    {
        'stage': 'Auto loan rates rise',
        'lag': '0-1 months',
        'lag_months': (0, 1),
        'series': 'TERMCBPER24NS',  # 24-month auto loan rate
        'direction': '+',
        'threshold': 0.25,
        'description': 'Auto financing costs increase for new loans'
    },
    {
        'stage': 'Durable goods demand slows',
        'lag': '3-6 months',
        'lag_months': (3, 6),
        'series': 'DGORDER',  # Durable goods orders
        'direction': '-',
        'threshold': -3.0,
        'description': 'Big-ticket purchases decline as financing costs rise'
    },
    {
        'stage': 'Consumer spending cools',
        'lag': '6-12 months',
        'lag_months': (6, 12),
        'series': 'PCE',  # Personal consumption expenditures
        'direction': '-',
        'threshold': -1.0,
        'description': 'Overall consumer spending growth moderates'
    }
]


RATE_TO_LABOR = [
    {
        'stage': 'Fed hikes rates',
        'lag': 'immediate',
        'lag_months': (0, 0),
        'series': 'FEDFUNDS',
        'direction': '+',
        'threshold': 0.25,
        'description': 'Federal Reserve raises the federal funds rate target'
    },
    {
        'stage': 'Financial conditions tighten',
        'lag': '0-3 months',
        'lag_months': (0, 3),
        'series': 'NFCI',  # Chicago Fed Financial Conditions Index
        'direction': '+',
        'threshold': 0.1,
        'description': 'Credit spreads widen, lending standards tighten'
    },
    {
        'stage': 'Business investment slows',
        'lag': '6-12 months',
        'lag_months': (6, 12),
        'series': 'PNFI',  # Private nonresidential fixed investment
        'direction': '-',
        'threshold': -2.0,
        'description': 'Companies pull back on capital expenditures'
    },
    {
        'stage': 'Hiring slows',
        'lag': '9-15 months',
        'lag_months': (9, 15),
        'series': 'PAYEMS',  # Nonfarm payrolls (look at MoM change)
        'direction': '-',
        'threshold': -50,  # Thousands
        'description': 'Job creation decelerates as businesses become cautious'
    },
    {
        'stage': 'Job openings fall',
        'lag': '9-15 months',
        'lag_months': (9, 15),
        'series': 'JTSJOL',  # JOLTS job openings (leading indicator)
        'direction': '-',
        'threshold': -500,  # Thousands
        'description': 'Companies reduce job postings before cutting existing workers'
    },
    {
        'stage': 'Unemployment rises',
        'lag': '12-24 months',
        'lag_months': (12, 24),
        'series': 'UNRATE',  # Unemployment rate (lagging indicator)
        'direction': '+',
        'threshold': 0.3,
        'description': 'Layoffs and slower hiring push unemployment higher'
    }
]


# Chain lookup for convenience
CHAINS = {
    'RATE_TO_HOUSING': RATE_TO_HOUSING,
    'RATE_TO_CONSUMPTION': RATE_TO_CONSUMPTION,
    'RATE_TO_LABOR': RATE_TO_LABOR
}


# =============================================================================
# CHAIN POSITION DETECTION
# =============================================================================

def detect_chain_position(chain: list, data: dict,
                          rate_hike_date: Optional[str] = None) -> dict:
    """
    Detect where we are in a monetary policy transmission chain.

    Args:
        chain: One of the chain definitions (e.g., RATE_TO_HOUSING)
        data: Dictionary of series data, keyed by series ID.
              Each value should have 'values' (list of floats) and
              'dates' (list of date strings) keys.
        rate_hike_date: Optional start date of rate hiking cycle (YYYY-MM-DD).
                        If not provided, attempts to detect from FEDFUNDS data.

    Returns:
        dict with:
            - 'current_stage': Index of current stage (0-based)
            - 'stage_name': Name of current stage
            - 'months_since_hike': Estimated months since hiking began
            - 'stages_activated': List of stages that show expected response
            - 'stages_pending': List of stages not yet responding
            - 'next_stage': Expected next stage
            - 'next_stage_timing': When to expect next stage
            - 'stage_details': Per-stage analysis
    """
    result = {
        'current_stage': 0,
        'stage_name': chain[0]['stage'],
        'months_since_hike': 0,
        'stages_activated': [],
        'stages_pending': [],
        'next_stage': None,
        'next_stage_timing': None,
        'stage_details': []
    }

    # Try to detect hiking start from FEDFUNDS data if not provided
    if rate_hike_date is None:
        rate_hike_date = _detect_hike_start(data.get('FEDFUNDS', {}))

    # Calculate months since hike
    if rate_hike_date:
        try:
            hike_dt = datetime.strptime(rate_hike_date, '%Y-%m-%d')
            months_since = (datetime.now() - hike_dt).days / 30.44
            result['months_since_hike'] = int(months_since)
        except (ValueError, TypeError):
            pass

    # Analyze each stage
    for i, stage in enumerate(chain):
        series_id = stage['series']
        series_data = data.get(series_id, {})

        stage_analysis = {
            'stage': stage['stage'],
            'series': series_id,
            'lag_range': stage['lag'],
            'expected_direction': stage['direction'],
            'status': 'unknown',
            'recent_change': None,
            'activated': False
        }

        # Check if we have data for this series
        if series_data and 'values' in series_data:
            change = _calculate_recent_change(series_data, stage)
            stage_analysis['recent_change'] = change

            # Check if the change matches expected direction and exceeds threshold
            if change is not None:
                threshold = stage['threshold']
                if stage['direction'] == '+':
                    activated = change >= threshold
                else:  # direction == '-'
                    activated = change <= threshold

                stage_analysis['activated'] = activated
                if activated:
                    stage_analysis['status'] = 'responding'
                    result['stages_activated'].append(stage['stage'])
                else:
                    stage_analysis['status'] = 'not yet'
                    result['stages_pending'].append(stage['stage'])
        else:
            stage_analysis['status'] = 'no data'
            result['stages_pending'].append(stage['stage'])

        result['stage_details'].append(stage_analysis)

    # Determine current stage (last activated stage)
    for i, detail in enumerate(result['stage_details']):
        if detail['activated']:
            result['current_stage'] = i
            result['stage_name'] = chain[i]['stage']

    # Determine next expected stage
    if result['current_stage'] < len(chain) - 1:
        next_idx = result['current_stage'] + 1
        result['next_stage'] = chain[next_idx]['stage']

        # Calculate when to expect it
        lag_low, lag_high = chain[next_idx]['lag_months']
        months_since = result['months_since_hike']

        if months_since < lag_low:
            result['next_stage_timing'] = f"in {lag_low - months_since} to {lag_high - months_since} months"
        elif months_since <= lag_high:
            result['next_stage_timing'] = "expected now through " + f"{lag_high - months_since} more months"
        else:
            result['next_stage_timing'] = "overdue (expected by now)"

    return result


def _detect_hike_start(fedfunds_data: dict) -> Optional[str]:
    """
    Detect the start of a rate hiking cycle from FEDFUNDS data.

    Looks for the first significant rate increase after a period of stability.
    Returns the date of that increase.
    """
    if not fedfunds_data or 'values' not in fedfunds_data or 'dates' not in fedfunds_data:
        return None

    values = fedfunds_data['values']
    dates = fedfunds_data['dates']

    if len(values) < 3:
        return None

    # Look for rate increases of at least 0.25% from a low base
    for i in range(1, len(values)):
        if values[i] - values[i-1] >= 0.20:  # At least ~25bp increase
            # Check if previous rate was near zero (or low)
            if values[i-1] < 1.0:
                return dates[i]

    # Fallback: find the minimum rate and return the date of first increase after
    min_rate = min(values)
    min_idx = values.index(min_rate)

    for i in range(min_idx + 1, len(values)):
        if values[i] > min_rate + 0.20:
            return dates[i]

    return None


def _calculate_recent_change(series_data: dict, stage: dict) -> Optional[float]:
    """
    Calculate the recent change in a series to assess if it's responding.

    For rates (FEDFUNDS, mortgage, etc.): absolute change in level
    For indices (CPI, home prices): YoY % change in the rate of change
    For levels (job openings, payrolls): absolute change
    """
    values = series_data.get('values', [])

    if len(values) < 2:
        return None

    series_id = stage['series']

    # For rates - look at level change over past 12 months
    if series_id in ('FEDFUNDS', 'DGS10', 'MORTGAGE30US', 'TERMCBCCALLNS',
                     'TERMCBPER24NS', 'UNRATE', 'NFCI'):
        # Compare current to 12 months ago (or as far back as we have)
        lookback = min(12, len(values) - 1)
        current = values[-1]
        past = values[-(lookback + 1)]
        return current - past

    # For indices - calculate YoY change
    if series_id in ('CPILFESL', 'CUSR0000SAH1', 'CSUSHPINSA'):
        if len(values) >= 13:
            current = values[-1]
            year_ago = values[-13]
            if year_ago > 0:
                return ((current - year_ago) / year_ago) * 100
        return None

    # For levels (activity data) - YoY change
    if series_id in ('EXHOSLUSM495S', 'DGORDER', 'PCE', 'PNFI', 'JTSJOL'):
        if len(values) >= 13:
            current = values[-1]
            year_ago = values[-13]
            if year_ago > 0:
                return ((current - year_ago) / year_ago) * 100
        elif len(values) >= 2:
            # Short data - use available change
            return ((values[-1] - values[0]) / values[0]) * 100 if values[0] > 0 else None
        return None

    # For payrolls - MoM change (in thousands)
    if series_id == 'PAYEMS':
        if len(values) >= 2:
            return values[-1] - values[-2]
        return None

    # Default: simple difference
    return values[-1] - values[0] if len(values) >= 2 else None


# =============================================================================
# CHAIN POSITION EXPLANATION
# =============================================================================

def explain_chain_position(chain_name: str, position: dict) -> str:
    """
    Generate a plain English explanation of the current position in a chain.

    Args:
        chain_name: One of 'RATE_TO_HOUSING', 'RATE_TO_CONSUMPTION', 'RATE_TO_LABOR'
        position: Result from detect_chain_position()

    Returns:
        Human-readable explanation suitable for a briefing.
    """
    chain = CHAINS.get(chain_name)
    if not chain:
        return f"Unknown chain: {chain_name}"

    months = position.get('months_since_hike', 0)
    current_stage = position.get('current_stage', 0)
    stage_name = position.get('stage_name', 'Unknown')
    activated = position.get('stages_activated', [])
    pending = position.get('stages_pending', [])
    next_stage = position.get('next_stage')
    next_timing = position.get('next_stage_timing')

    # Build the explanation based on chain type
    if chain_name == 'RATE_TO_HOUSING':
        return _explain_housing_chain(months, current_stage, stage_name,
                                       activated, pending, next_stage, next_timing,
                                       position.get('stage_details', []))

    elif chain_name == 'RATE_TO_CONSUMPTION':
        return _explain_consumption_chain(months, current_stage, stage_name,
                                           activated, pending, next_stage, next_timing,
                                           position.get('stage_details', []))

    elif chain_name == 'RATE_TO_LABOR':
        return _explain_labor_chain(months, current_stage, stage_name,
                                     activated, pending, next_stage, next_timing,
                                     position.get('stage_details', []))

    return f"Chain analysis not available for {chain_name}"


def _explain_housing_chain(months: int, current_stage: int, stage_name: str,
                           activated: list, pending: list, next_stage: str,
                           next_timing: str, details: list) -> str:
    """Generate explanation for the housing transmission chain."""

    parts = []

    # Opening context
    if months > 0:
        parts.append(f"We're about {months} months into the rate-to-housing transmission.")
    else:
        parts.append("Analyzing the rate-to-housing transmission chain.")

    # What has responded
    if len(activated) > 1:
        responded = [s for s in activated if s != 'Fed hikes rates']
        if responded:
            parts.append(f"So far, {_list_to_prose(responded)} have responded to tighter policy.")

    # Current status based on stage
    if current_stage == 0:
        parts.append("We're at the very beginning - rate hikes have occurred but effects haven't materialized yet.")

    elif current_stage <= 2:
        # Early stages - rates adjusting
        parts.append("Mortgage rates have risen, making home buying more expensive.")
        if 'Housing demand falls' in pending:
            parts.append("Housing demand hasn't fully cooled yet - expect that in the coming months.")

    elif current_stage == 3:
        # Demand falling
        parts.append("Housing demand has clearly weakened - fewer buyers can afford homes at current rates.")
        if 'Home prices cool' in pending:
            parts.append("Home prices are still elevated but should start cooling soon.")

    elif current_stage == 4:
        # Prices cooling
        parts.append("Home prices are now cooling as reduced demand works through the market.")
        if 'Shelter CPI responds' in pending:
            time_hint = "6-12 months" if months < 12 else "within the next 6-12 months"
            parts.append(f"Shelter CPI hasn't peaked yet - expect relief in {time_hint}.")

    elif current_stage == 5:
        # Shelter CPI responding
        parts.append("Shelter CPI is finally starting to decelerate.")
        parts.append("This is a key inflection point - shelter is ~40% of core CPI.")
        if 'Core CPI eases' in pending:
            parts.append("Core inflation should follow within 6-12 months as shelter continues easing.")

    elif current_stage == 6:
        # Full transmission
        parts.append("The full transmission is complete - lower shelter costs are now pulling down core CPI.")
        parts.append("This typically marks the end of the tightening-to-inflation cycle.")

    # Forward look
    if next_stage and next_timing and 'overdue' not in next_timing:
        parts.append(f"Next expected: {next_stage.lower()} {next_timing}.")
    elif next_stage and 'overdue' in str(next_timing):
        parts.append(f"Note: {next_stage} appears delayed - may indicate unusual market conditions.")

    return " ".join(parts)


def _explain_consumption_chain(months: int, current_stage: int, stage_name: str,
                                activated: list, pending: list, next_stage: str,
                                next_timing: str, details: list) -> str:
    """Generate explanation for the consumption transmission chain."""

    parts = []

    if months > 0:
        parts.append(f"We're about {months} months into the rate-to-consumption transmission.")
    else:
        parts.append("Analyzing the rate-to-consumption transmission chain.")

    if current_stage <= 2:
        # Early - credit costs rising
        parts.append("Borrowing costs have increased - credit card and auto loan rates are higher.")
        if 'Durable goods demand slows' in pending:
            parts.append("Consumer demand for big-ticket items should start slowing in the next few months.")

    elif current_stage == 3:
        # Durable goods slowing
        parts.append("Durable goods demand has weakened - consumers are pulling back on big purchases.")
        parts.append("Auto sales and appliance purchases typically lead this slowdown.")
        if 'Consumer spending cools' in pending:
            parts.append("Broader consumer spending should follow within 3-6 months.")

    elif current_stage == 4:
        # Spending cooling
        parts.append("Consumer spending growth has moderated as the cumulative effect of higher rates takes hold.")
        parts.append("This is the intended effect - slowing demand to reduce inflation pressure.")

    if next_stage and next_timing and 'overdue' not in next_timing:
        parts.append(f"Next expected: {next_stage.lower()} {next_timing}.")

    return " ".join(parts)


def _explain_labor_chain(months: int, current_stage: int, stage_name: str,
                         activated: list, pending: list, next_stage: str,
                         next_timing: str, details: list) -> str:
    """Generate explanation for the labor market transmission chain."""

    parts = []

    if months > 0:
        parts.append(f"We're about {months} months into the rate-to-labor transmission.")
    else:
        parts.append("Analyzing the rate-to-labor transmission chain.")

    if current_stage <= 1:
        # Financial conditions tightening
        parts.append("Financial conditions have tightened - credit is harder to get and more expensive.")
        if 'Business investment slows' in pending:
            parts.append("Business investment should start slowing in the next 3-9 months.")

    elif current_stage == 2:
        # Investment slowing
        parts.append("Business investment has slowed as companies respond to tighter financial conditions.")
        if 'Hiring slows' in pending:
            parts.append("Hiring is typically the next domino - expect payroll growth to moderate soon.")

    elif current_stage <= 4:
        # Hiring/openings stage
        if 'Hiring slows' in activated or 'Job openings fall' in activated:
            parts.append("The labor market is cooling - job openings are declining and hiring has slowed.")
            parts.append("Job openings typically fall before unemployment rises (leading indicator).")
        if 'Unemployment rises' in pending:
            parts.append("Unemployment hasn't risen significantly yet - that's usually the last shoe to drop.")

    elif current_stage == 5:
        # Unemployment rising
        parts.append("Unemployment has started rising - the labor market has clearly softened.")
        parts.append("This is typically the final stage of monetary transmission and often signals the Fed will pause or cut.")

    if next_stage and next_timing:
        if 'overdue' not in next_timing:
            parts.append(f"Next expected: {next_stage.lower()} {next_timing}.")
        else:
            parts.append(f"Note: {next_stage} may be delayed - labor market resilience has been unusual this cycle.")

    return " ".join(parts)


def _list_to_prose(items: list) -> str:
    """Convert a list to prose (e.g., ['a', 'b', 'c'] -> 'a, b, and c')."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0].lower()
    if len(items) == 2:
        return f"{items[0].lower()} and {items[1].lower()}"
    return ", ".join(item.lower() for item in items[:-1]) + f", and {items[-1].lower()}"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_chain_series(chain_name: str) -> list:
    """Get all FRED series IDs needed to analyze a chain."""
    chain = CHAINS.get(chain_name)
    if not chain:
        return []
    return [stage['series'] for stage in chain]


def get_all_chain_series() -> list:
    """Get all unique FRED series IDs across all chains."""
    all_series = set()
    for chain in CHAINS.values():
        for stage in chain:
            all_series.add(stage['series'])
    return list(all_series)


def summarize_all_chains(data: dict, rate_hike_date: Optional[str] = None) -> dict:
    """
    Analyze all chains and return a summary.

    Args:
        data: Dictionary of series data, keyed by series ID
        rate_hike_date: Optional start of hiking cycle

    Returns:
        Dictionary with summary for each chain
    """
    summary = {}
    for chain_name, chain in CHAINS.items():
        position = detect_chain_position(chain, data, rate_hike_date)
        explanation = explain_chain_position(chain_name, position)
        summary[chain_name] = {
            'position': position,
            'explanation': explanation
        }
    return summary


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("MONETARY POLICY TRANSMISSION CHAINS - TEST")
    print("=" * 70)

    # Test 1: Chain definitions
    print("\n1. CHAIN DEFINITIONS")
    print("-" * 40)

    for chain_name, chain in CHAINS.items():
        print(f"\n{chain_name}:")
        for i, stage in enumerate(chain):
            print(f"  {i+1}. {stage['stage']} ({stage['lag']}) - {stage['series']}")

    # Test 2: Get all series needed
    print("\n\n2. SERIES REQUIRED FOR ALL CHAINS")
    print("-" * 40)
    all_series = get_all_chain_series()
    print(f"Total unique series: {len(all_series)}")
    print(f"Series: {sorted(all_series)}")

    # Test 3: Simulate chain detection with mock data
    print("\n\n3. CHAIN POSITION DETECTION (SIMULATED DATA)")
    print("-" * 40)

    # Mock data simulating ~12 months after hike start (March 2022 cycle)
    mock_data = {
        'FEDFUNDS': {
            'values': [0.08, 0.08, 0.33, 0.77, 1.21, 1.68, 2.33, 3.08, 3.83, 4.33, 4.57, 4.83, 5.08, 5.33],
            'dates': ['2022-01-01', '2022-02-01', '2022-03-01', '2022-04-01', '2022-05-01',
                      '2022-06-01', '2022-07-01', '2022-08-01', '2022-09-01', '2022-10-01',
                      '2022-11-01', '2022-12-01', '2023-01-01', '2023-02-01']
        },
        'DGS10': {
            'values': [1.78, 1.93, 2.14, 2.78, 2.84, 2.98, 2.90, 2.90, 3.52, 4.07, 3.87, 3.62, 3.52, 3.92],
            'dates': ['2022-01-01', '2022-02-01', '2022-03-01', '2022-04-01', '2022-05-01',
                      '2022-06-01', '2022-07-01', '2022-08-01', '2022-09-01', '2022-10-01',
                      '2022-11-01', '2022-12-01', '2023-01-01', '2023-02-01']
        },
        'MORTGAGE30US': {
            'values': [3.45, 3.76, 4.16, 5.10, 5.30, 5.52, 5.54, 5.66, 6.11, 7.08, 6.95, 6.42, 6.27, 6.50],
            'dates': ['2022-01-01', '2022-02-01', '2022-03-01', '2022-04-01', '2022-05-01',
                      '2022-06-01', '2022-07-01', '2022-08-01', '2022-09-01', '2022-10-01',
                      '2022-11-01', '2022-12-01', '2023-01-01', '2023-02-01']
        },
        'EXHOSLUSM495S': {
            'values': [6.49, 6.02, 5.77, 5.61, 5.41, 5.12, 4.81, 4.71, 4.43, 4.43, 4.09, 4.02, 4.0, 4.08],
            'dates': ['2022-01-01', '2022-02-01', '2022-03-01', '2022-04-01', '2022-05-01',
                      '2022-06-01', '2022-07-01', '2022-08-01', '2022-09-01', '2022-10-01',
                      '2022-11-01', '2022-12-01', '2023-01-01', '2023-02-01']
        },
        'CSUSHPINSA': {
            'values': [280, 285, 290, 295, 300, 305, 305, 303, 300, 298, 297, 296, 295, 294],
            'dates': ['2022-01-01', '2022-02-01', '2022-03-01', '2022-04-01', '2022-05-01',
                      '2022-06-01', '2022-07-01', '2022-08-01', '2022-09-01', '2022-10-01',
                      '2022-11-01', '2022-12-01', '2023-01-01', '2023-02-01']
        },
        # Shelter CPI - still rising in this simulation (lagged response)
        'CUSR0000SAH1': {
            'values': [100, 100.5, 101.0, 101.6, 102.2, 102.9, 103.6, 104.3, 105.0, 105.8, 106.5, 107.2, 107.9, 108.5],
            'dates': ['2022-01-01', '2022-02-01', '2022-03-01', '2022-04-01', '2022-05-01',
                      '2022-06-01', '2022-07-01', '2022-08-01', '2022-09-01', '2022-10-01',
                      '2022-11-01', '2022-12-01', '2023-01-01', '2023-02-01']
        }
    }

    # Detect position in housing chain
    print("\nRATE_TO_HOUSING Chain:")
    position = detect_chain_position(RATE_TO_HOUSING, mock_data, rate_hike_date='2022-03-01')

    print(f"  Months since hike: {position['months_since_hike']}")
    print(f"  Current stage: {position['current_stage']} - {position['stage_name']}")
    print(f"  Stages activated: {position['stages_activated']}")
    print(f"  Stages pending: {position['stages_pending']}")
    print(f"  Next stage: {position['next_stage']}")
    print(f"  Next timing: {position['next_stage_timing']}")

    # Test 4: Plain English explanation
    print("\n\n4. PLAIN ENGLISH EXPLANATION")
    print("-" * 40)

    explanation = explain_chain_position('RATE_TO_HOUSING', position)
    print(f"\n{explanation}")

    # Test 5: Test other chains with minimal data
    print("\n\n5. OTHER CHAIN EXPLANATIONS (MINIMAL DATA)")
    print("-" * 40)

    for chain_name in ['RATE_TO_CONSUMPTION', 'RATE_TO_LABOR']:
        position = detect_chain_position(CHAINS[chain_name], mock_data, rate_hike_date='2022-03-01')
        explanation = explain_chain_position(chain_name, position)
        print(f"\n{chain_name}:")
        print(f"  {explanation}")

    # Test 6: Hike detection
    print("\n\n6. RATE HIKE DETECTION")
    print("-" * 40)
    detected_hike = _detect_hike_start(mock_data['FEDFUNDS'])
    print(f"Detected hike start: {detected_hike}")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
