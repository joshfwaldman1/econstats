"""
Recession Probability and Detection Frameworks.

Provides comprehensive recession risk assessment using:
- Yield curve signals (10Y-2Y, 10Y-3M spreads)
- Leading economic indicators composite
- Probabilistic models combining multiple signals
- Expansion age and historical context

Key insight: No single indicator reliably predicts recessions.
The value is in combining multiple signals with different lead times
and historical accuracy to form a probabilistic assessment.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
import statistics

# Historical constants
LAST_RECESSION_END = date(2020, 6, 1)  # COVID recession ended June 2020
NBER_RECESSION_DATES = [
    # (start, end, name)
    (date(2020, 2, 1), date(2020, 4, 1), "COVID-19"),
    (date(2007, 12, 1), date(2009, 6, 1), "Great Recession"),
    (date(2001, 3, 1), date(2001, 11, 1), "Dot-Com"),
    (date(1990, 7, 1), date(1991, 3, 1), "1990-91"),
    (date(1981, 7, 1), date(1982, 11, 1), "1981-82"),
    (date(1980, 1, 1), date(1980, 7, 1), "1980"),
]

# Historical expansion lengths (months) since 1945
HISTORICAL_EXPANSIONS = [
    128,  # 2009-2020 (longest ever, cut short by COVID)
    73,   # 2001-2007
    120,  # 1991-2001
    92,   # 1982-1990
    12,   # 1980-1981
    58,   # 1975-1980
    36,   # 1970-1973
    106,  # 1961-1969
    24,   # 1958-1960
    39,   # 1954-1957
    45,   # 1949-1953
    37,   # 1945-1948
]

AVERAGE_EXPANSION_MONTHS = statistics.mean(HISTORICAL_EXPANSIONS)  # ~64 months
MEDIAN_EXPANSION_MONTHS = statistics.median(HISTORICAL_EXPANSIONS)  # ~51 months


@dataclass
class YieldCurveSignal:
    """Yield curve inversion analysis."""

    spread_10y_2y: Optional[float] = None  # T10Y2Y
    spread_10y_3m: Optional[float] = None  # T10Y3M
    status: str = "unknown"  # "inverted", "flat", "steep", "normal"
    days_inverted: Optional[int] = None  # Days since inversion started (if inverted)
    inversion_start_date: Optional[str] = None
    traffic_light: str = "gray"  # green, yellow, red, gray
    interpretation: str = ""

    # Historical context
    INVERSION_LEAD_TIME = "12-18 months"  # Typical lead before recession
    HISTORICAL_ACCURACY = 0.85  # ~85% of inversions preceded recessions since 1970


@dataclass
class LeadingIndicator:
    """Individual leading indicator with scoring."""

    name: str
    series_id: str
    current_value: Optional[float] = None
    trend: str = "unknown"  # "improving", "stable", "deteriorating"
    score: int = 0  # -2 (very bad) to +2 (very good)
    traffic_light: str = "gray"
    interpretation: str = ""
    weight: float = 1.0  # Weight in composite
    data_available: bool = True
    note: str = ""


@dataclass
class LeadingIndicatorsComposite:
    """Composite of multiple leading indicators."""

    indicators: list[LeadingIndicator] = None
    composite_score: float = 0.0  # Weighted average, -2 to +2
    traffic_light: str = "gray"
    interpretation: str = ""

    def __post_init__(self):
        if self.indicators is None:
            self.indicators = []


@dataclass
class RecessionProbability:
    """Combined recession probability estimate."""

    probability_6m: float = 0.0  # 6-month ahead probability
    probability_12m: float = 0.0  # 12-month ahead probability
    confidence: str = "low"  # "low", "medium", "high"
    traffic_light: str = "gray"
    interpretation: str = ""

    # Comparison points
    polymarket_prob: Optional[float] = None
    fed_model_prob: Optional[float] = None  # NY Fed model

    # Component weights
    yield_curve_weight: float = 0.35
    leading_indicators_weight: float = 0.35
    labor_market_weight: float = 0.30


@dataclass
class ExpansionAge:
    """Current expansion duration and historical context."""

    months_since_recession: int = 0
    years_since_recession: float = 0.0
    percentile_vs_history: float = 0.0  # Where this expansion ranks
    traffic_light: str = "gray"
    interpretation: str = ""

    historical_average: float = AVERAGE_EXPANSION_MONTHS
    historical_median: float = MEDIAN_EXPANSION_MONTHS


def _get_series_value(data: dict, series_id: str) -> Optional[float]:
    """Extract latest value for a series from data dict."""
    if series_id not in data:
        return None
    series_data = data[series_id]

    # Handle SeriesData objects
    if hasattr(series_data, 'latest_value'):
        return series_data.latest_value

    # Handle dict format
    if isinstance(series_data, dict):
        if 'values' in series_data and series_data['values']:
            return series_data['values'][-1]
        if 'value' in series_data:
            return series_data['value']

    return None


def _get_series_values(data: dict, series_id: str, n: int = 12) -> list[float]:
    """Get last N values for a series."""
    if series_id not in data:
        return []
    series_data = data[series_id]

    # Check for dict first (has 'values' attribute but it's a method, not data)
    if isinstance(series_data, dict):
        if 'values' in series_data and series_data['values']:
            return series_data['values'][-n:]
        return []

    # SeriesData object with values attribute
    if hasattr(series_data, 'values') and series_data.values:
        return series_data.values[-n:]

    return []


def _calculate_trend(values: list[float], periods: int = 3) -> str:
    """Calculate trend from recent values."""
    if len(values) < periods + 1:
        return "unknown"

    recent = values[-periods:]
    earlier = values[-(periods * 2):-periods] if len(values) >= periods * 2 else values[:periods]

    if not earlier:
        return "unknown"

    recent_avg = sum(recent) / len(recent)
    earlier_avg = sum(earlier) / len(earlier)

    pct_change = (recent_avg - earlier_avg) / abs(earlier_avg) * 100 if earlier_avg != 0 else 0

    if pct_change > 5:
        return "rising"
    elif pct_change < -5:
        return "falling"
    else:
        return "stable"


def analyze_yield_curve(data: dict) -> YieldCurveSignal:
    """
    Analyze yield curve for recession signals.

    Uses:
    - T10Y2Y: 10-Year Treasury minus 2-Year Treasury
    - T10Y3M: 10-Year Treasury minus 3-Month Treasury

    Historical context:
    - Yield curve inversions have preceded every US recession since 1970
    - Lead time typically 12-18 months from inversion to recession
    - False positive rate ~15% (inversions that didn't lead to recession)
    - The 10Y-3M spread has slightly better predictive power than 10Y-2Y
    """
    signal = YieldCurveSignal()

    # Get spread values
    signal.spread_10y_2y = _get_series_value(data, 'T10Y2Y')
    signal.spread_10y_3m = _get_series_value(data, 'T10Y3M')

    if signal.spread_10y_2y is None and signal.spread_10y_3m is None:
        signal.interpretation = "Yield curve data unavailable"
        return signal

    # Determine status based on both spreads
    primary_spread = signal.spread_10y_3m if signal.spread_10y_3m is not None else signal.spread_10y_2y

    if primary_spread < -0.25:
        signal.status = "inverted"
        signal.traffic_light = "red"
    elif primary_spread < 0:
        signal.status = "inverted"
        signal.traffic_light = "red"
    elif primary_spread < 0.25:
        signal.status = "flat"
        signal.traffic_light = "yellow"
    elif primary_spread < 1.0:
        signal.status = "normal"
        signal.traffic_light = "green"
    else:
        signal.status = "steep"
        signal.traffic_light = "green"

    # Calculate days inverted (if we have historical data)
    spread_values = _get_series_values(data, 'T10Y3M', n=252)  # ~1 year of daily data
    if not spread_values:
        spread_values = _get_series_values(data, 'T10Y2Y', n=252)

    if spread_values and signal.status == "inverted":
        # Count consecutive inverted days from end
        days_inverted = 0
        for val in reversed(spread_values):
            if val < 0:
                days_inverted += 1
            else:
                break
        signal.days_inverted = days_inverted if days_inverted > 0 else None

    # Build interpretation
    if signal.status == "inverted":
        signal.interpretation = (
            f"YIELD CURVE INVERTED. "
            f"10Y-3M spread: {signal.spread_10y_3m:.2f}% | 10Y-2Y spread: {signal.spread_10y_2y:.2f}%. "
            f"Historical pattern: inversions precede recessions by {YieldCurveSignal.INVERSION_LEAD_TIME}. "
        )
        if signal.days_inverted:
            signal.interpretation += f"Currently inverted for ~{signal.days_inverted} trading days. "
        signal.interpretation += (
            f"Accuracy: ~{YieldCurveSignal.HISTORICAL_ACCURACY:.0%} of inversions since 1970 preceded recessions."
        )
    elif signal.status == "flat":
        signal.interpretation = (
            f"Yield curve is flat (10Y-3M: {signal.spread_10y_3m:.2f}%). "
            f"This often precedes inversion. Warrants close monitoring. "
            f"Not yet signaling recession but risk is elevated."
        )
    else:
        signal.interpretation = (
            f"Yield curve is {signal.status} (10Y-3M: {signal.spread_10y_3m:.2f}%). "
            f"No recession signal from yield curve. "
            f"Normal/steep curves historically associated with economic expansion."
        )

    return signal


def analyze_leading_indicators(data: dict) -> LeadingIndicatorsComposite:
    """
    Analyze composite of leading economic indicators.

    Includes:
    - Initial jobless claims (ICSA) - Weekly, very timely
    - Building permits (PERMIT) - Forward-looking housing
    - Consumer expectations (UMCSENT) - Forward-looking sentiment
    - Manufacturing new orders (NEWORDER or DGORDER)
    - Aggregate hours worked (AWHAETP or similar)

    NOT included (note for users):
    - ISM Manufacturing PMI - Not available in FRED (subscription required)
      Consider: MANEMP (manufacturing employment) as proxy
    """
    composite = LeadingIndicatorsComposite()

    # 1. Initial Jobless Claims (ICSA)
    icsa = LeadingIndicator(
        name="Initial Jobless Claims",
        series_id="ICSA",
        weight=1.5,  # Higher weight - very timely weekly data
    )
    icsa_value = _get_series_value(data, 'ICSA')
    icsa_values = _get_series_values(data, 'ICSA', n=26)  # ~6 months weekly

    if icsa_value is not None:
        icsa.current_value = icsa_value
        icsa.data_available = True
        icsa.trend = _calculate_trend(icsa_values, periods=4)

        # Score based on level and trend
        # Historical context: <250K = strong, 250-350K = normal, >350K = weak, >500K = recession
        if icsa_value < 225000:
            icsa.score = 2
            icsa.traffic_light = "green"
            icsa.interpretation = f"Very low claims ({icsa_value/1000:.0f}K) - strong labor market"
        elif icsa_value < 300000:
            icsa.score = 1
            icsa.traffic_light = "green"
            icsa.interpretation = f"Low claims ({icsa_value/1000:.0f}K) - healthy labor market"
        elif icsa_value < 400000:
            icsa.score = 0
            icsa.traffic_light = "yellow"
            icsa.interpretation = f"Moderate claims ({icsa_value/1000:.0f}K) - neutral signal"
        else:
            icsa.score = -2 if icsa_value > 500000 else -1
            icsa.traffic_light = "red"
            icsa.interpretation = f"Elevated claims ({icsa_value/1000:.0f}K) - labor market weakening"

        # Adjust for trend
        if icsa.trend == "rising" and icsa.score > -2:
            icsa.score -= 1
            icsa.interpretation += " (trending higher)"
        elif icsa.trend == "falling" and icsa.score < 2:
            icsa.score += 1
            icsa.interpretation += " (trending lower)"
    else:
        icsa.data_available = False

    composite.indicators.append(icsa)

    # 2. Building Permits (PERMIT)
    permit = LeadingIndicator(
        name="Building Permits",
        series_id="PERMIT",
        weight=1.0,
    )
    permit_value = _get_series_value(data, 'PERMIT')
    permit_values = _get_series_values(data, 'PERMIT', n=12)

    if permit_value is not None:
        permit.current_value = permit_value
        permit.data_available = True
        permit.trend = _calculate_trend(permit_values)

        # Historical context: typically 1.2-1.6M annualized is healthy
        if permit_value > 1500:
            permit.score = 2
            permit.traffic_light = "green"
            permit.interpretation = f"Strong permits ({permit_value/1000:.1f}M) - housing demand robust"
        elif permit_value > 1200:
            permit.score = 1
            permit.traffic_light = "green"
            permit.interpretation = f"Healthy permits ({permit_value/1000:.1f}M) - stable housing"
        elif permit_value > 900:
            permit.score = 0
            permit.traffic_light = "yellow"
            permit.interpretation = f"Moderate permits ({permit_value/1000:.1f}M) - housing cooling"
        else:
            permit.score = -2 if permit_value < 700 else -1
            permit.traffic_light = "red"
            permit.interpretation = f"Weak permits ({permit_value/1000:.1f}M) - housing contraction"

        if permit.trend == "falling":
            permit.interpretation += " (declining trend)"
    else:
        permit.data_available = False

    composite.indicators.append(permit)

    # 3. Consumer Sentiment (UMCSENT)
    umcsent = LeadingIndicator(
        name="Consumer Sentiment",
        series_id="UMCSENT",
        weight=1.0,
    )
    umcsent_value = _get_series_value(data, 'UMCSENT')
    umcsent_values = _get_series_values(data, 'UMCSENT', n=12)

    if umcsent_value is not None:
        umcsent.current_value = umcsent_value
        umcsent.data_available = True
        umcsent.trend = _calculate_trend(umcsent_values)

        # Historical context: avg ~85, >90 = optimistic, <70 = pessimistic
        if umcsent_value > 95:
            umcsent.score = 2
            umcsent.traffic_light = "green"
            umcsent.interpretation = f"Very high sentiment ({umcsent_value:.1f}) - consumers optimistic"
        elif umcsent_value > 80:
            umcsent.score = 1
            umcsent.traffic_light = "green"
            umcsent.interpretation = f"Healthy sentiment ({umcsent_value:.1f}) - consumers confident"
        elif umcsent_value > 65:
            umcsent.score = 0
            umcsent.traffic_light = "yellow"
            umcsent.interpretation = f"Below-average sentiment ({umcsent_value:.1f}) - caution"
        else:
            umcsent.score = -2 if umcsent_value < 55 else -1
            umcsent.traffic_light = "red"
            umcsent.interpretation = f"Weak sentiment ({umcsent_value:.1f}) - consumers pessimistic"
    else:
        umcsent.data_available = False

    composite.indicators.append(umcsent)

    # 4. Manufacturing New Orders (DGORDER or NEWORDER)
    neworder = LeadingIndicator(
        name="Durable Goods Orders",
        series_id="DGORDER",
        weight=0.8,
    )
    neworder_value = _get_series_value(data, 'DGORDER')
    if neworder_value is None:
        neworder_value = _get_series_value(data, 'NEWORDER')
        neworder.series_id = "NEWORDER"
        neworder.name = "Manufacturing New Orders"

    neworder_values = _get_series_values(data, neworder.series_id, n=12)

    if neworder_value is not None:
        neworder.current_value = neworder_value
        neworder.data_available = True
        neworder.trend = _calculate_trend(neworder_values)

        # Score based on trend (level varies too much to use directly)
        if neworder.trend == "rising":
            neworder.score = 1
            neworder.traffic_light = "green"
            neworder.interpretation = f"Rising orders - manufacturing demand increasing"
        elif neworder.trend == "stable":
            neworder.score = 0
            neworder.traffic_light = "yellow"
            neworder.interpretation = f"Flat orders - manufacturing stable"
        else:
            neworder.score = -1
            neworder.traffic_light = "red"
            neworder.interpretation = f"Falling orders - manufacturing weakening"
    else:
        neworder.data_available = False

    composite.indicators.append(neworder)

    # 5. Average Weekly Hours (proxy for aggregate hours)
    hours = LeadingIndicator(
        name="Average Weekly Hours (Manufacturing)",
        series_id="AWHMAN",
        weight=0.8,
        note="Leading indicator: hours cut before layoffs",
    )
    hours_value = _get_series_value(data, 'AWHMAN')
    hours_values = _get_series_values(data, 'AWHMAN', n=12)

    if hours_value is not None:
        hours.current_value = hours_value
        hours.data_available = True
        hours.trend = _calculate_trend(hours_values)

        # Historical context: typically 40-42 hours, <40 = weak
        if hours_value > 41:
            hours.score = 2
            hours.traffic_light = "green"
            hours.interpretation = f"Strong hours ({hours_value:.1f}) - robust demand for labor"
        elif hours_value > 40:
            hours.score = 1
            hours.traffic_light = "green"
            hours.interpretation = f"Normal hours ({hours_value:.1f}) - stable labor demand"
        elif hours_value > 39:
            hours.score = 0
            hours.traffic_light = "yellow"
            hours.interpretation = f"Below-average hours ({hours_value:.1f}) - softening demand"
        else:
            hours.score = -1
            hours.traffic_light = "red"
            hours.interpretation = f"Weak hours ({hours_value:.1f}) - employers cutting hours"
    else:
        hours.data_available = False

    composite.indicators.append(hours)

    # 6. ISM Manufacturing placeholder
    ism = LeadingIndicator(
        name="ISM Manufacturing PMI",
        series_id="N/A",
        weight=0.0,  # Not included in scoring
        data_available=False,
        note="ISM data not available in FRED. Consider ISM subscription or use MANEMP as proxy.",
    )
    composite.indicators.append(ism)

    # Calculate composite score
    total_weight = sum(ind.weight for ind in composite.indicators if ind.data_available)
    if total_weight > 0:
        weighted_sum = sum(ind.score * ind.weight for ind in composite.indicators if ind.data_available)
        composite.composite_score = weighted_sum / total_weight

    # Determine traffic light
    if composite.composite_score > 0.5:
        composite.traffic_light = "green"
    elif composite.composite_score > -0.5:
        composite.traffic_light = "yellow"
    else:
        composite.traffic_light = "red"

    # Build interpretation
    available_count = sum(1 for ind in composite.indicators if ind.data_available)
    warning_count = sum(1 for ind in composite.indicators if ind.data_available and ind.score < 0)

    if composite.composite_score > 0.5:
        composite.interpretation = (
            f"Leading indicators broadly positive (score: {composite.composite_score:.2f}). "
            f"{available_count} indicators tracked, {warning_count} showing weakness. "
            f"No near-term recession signal from leading indicators."
        )
    elif composite.composite_score > -0.5:
        composite.interpretation = (
            f"Leading indicators mixed (score: {composite.composite_score:.2f}). "
            f"{warning_count} of {available_count} indicators showing weakness. "
            f"Economy slowing but not in imminent recession territory."
        )
    else:
        composite.interpretation = (
            f"Leading indicators concerning (score: {composite.composite_score:.2f}). "
            f"{warning_count} of {available_count} indicators deteriorating. "
            f"Elevated recession risk in coming quarters."
        )

    return composite


def calculate_recession_probability(
    yield_curve: YieldCurveSignal,
    leading_indicators: LeadingIndicatorsComposite,
    data: dict,
) -> RecessionProbability:
    """
    Calculate combined recession probability from multiple signals.

    Methodology:
    - Weight signals by historical accuracy
    - Yield curve: 35% weight (highest accuracy but long lead)
    - Leading indicators: 35% weight (timely, composite signal)
    - Labor market: 30% weight (lagging but high signal quality)

    Compare to:
    - NY Fed recession model (uses yield curve + more)
    - Polymarket prediction markets (crowd wisdom)
    """
    prob = RecessionProbability()

    # 1. Yield curve contribution (longer lead time)
    if yield_curve.status == "inverted":
        # Deep inversion = higher probability
        spread = yield_curve.spread_10y_3m or yield_curve.spread_10y_2y or 0
        if spread < -0.5:
            yc_prob = 0.60  # Deep inversion
        elif spread < -0.25:
            yc_prob = 0.45
        else:
            yc_prob = 0.35  # Mild inversion
    elif yield_curve.status == "flat":
        yc_prob = 0.25
    else:
        yc_prob = 0.10  # Normal/steep curve

    # 2. Leading indicators contribution
    li_score = leading_indicators.composite_score  # -2 to +2
    # Convert to probability: -2 -> 0.70, 0 -> 0.25, +2 -> 0.05
    li_prob = 0.25 - (li_score * 0.15)
    li_prob = max(0.05, min(0.70, li_prob))

    # 3. Labor market contribution
    # Use unemployment and jobless claims
    unrate = _get_series_value(data, 'UNRATE')
    unrate_values = _get_series_values(data, 'UNRATE', n=12)

    if unrate is not None and len(unrate_values) >= 6:
        unrate_change = unrate - min(unrate_values[-6:])  # Change from recent low

        # Sahm Rule: 0.5pp rise from low = recession signal
        if unrate_change >= 0.5:
            labor_prob = 0.65  # Sahm Rule triggered
        elif unrate_change >= 0.3:
            labor_prob = 0.40
        elif unrate_change >= 0.2:
            labor_prob = 0.25
        elif unrate < 4.5:
            labor_prob = 0.10  # Low unemployment
        else:
            labor_prob = 0.20
    else:
        labor_prob = 0.20  # Neutral if no data

    # Combine with weights
    prob.probability_12m = (
        yc_prob * prob.yield_curve_weight +
        li_prob * prob.leading_indicators_weight +
        labor_prob * prob.labor_market_weight
    )

    # 6-month probability is lower (inversions take time to manifest)
    prob.probability_6m = prob.probability_12m * 0.6

    # Confidence based on data availability
    available_indicators = sum(1 for ind in leading_indicators.indicators if ind.data_available)
    if available_indicators >= 4 and yield_curve.spread_10y_3m is not None:
        prob.confidence = "high"
    elif available_indicators >= 2:
        prob.confidence = "medium"
    else:
        prob.confidence = "low"

    # Traffic light
    if prob.probability_12m > 0.50:
        prob.traffic_light = "red"
    elif prob.probability_12m > 0.25:
        prob.traffic_light = "yellow"
    else:
        prob.traffic_light = "green"

    # Try to get comparison points from data
    polymarket = _get_series_value(data, 'polymarket_recession')
    if polymarket is not None:
        prob.polymarket_prob = polymarket / 100  # Convert from percentage

    # Build interpretation
    prob.interpretation = (
        f"12-month recession probability: {prob.probability_12m:.0%} "
        f"(6-month: {prob.probability_6m:.0%}). "
        f"Confidence: {prob.confidence}. "
    )

    if prob.probability_12m > 0.50:
        prob.interpretation += (
            "Multiple indicators suggest elevated recession risk. "
            "Historical accuracy of similar signal combinations: ~70-80%."
        )
    elif prob.probability_12m > 0.25:
        prob.interpretation += (
            "Mixed signals warrant monitoring. "
            "Recession possible but not the base case."
        )
    else:
        prob.interpretation += (
            "Indicators not signaling imminent recession. "
            "Economy appears on stable footing."
        )

    if prob.polymarket_prob is not None:
        prob.interpretation += f" Polymarket: {prob.polymarket_prob:.0%} recession odds."

    return prob


def calculate_expansion_age() -> ExpansionAge:
    """
    Calculate how long the current expansion has lasted.

    Historical context:
    - Average US expansion since 1945: ~64 months (~5.3 years)
    - Median expansion: ~51 months (~4.3 years)
    - Longest: 128 months (2009-2020)
    - Shortest post-war: 12 months (1980-1981)

    Note: Expansions don't die of old age. Length alone doesn't predict
    recession. But longer expansions often see accumulated imbalances.
    """
    expansion = ExpansionAge()

    today = date.today()
    months = (today.year - LAST_RECESSION_END.year) * 12 + (today.month - LAST_RECESSION_END.month)

    expansion.months_since_recession = months
    expansion.years_since_recession = months / 12

    # Calculate percentile
    longer_expansions = sum(1 for exp in HISTORICAL_EXPANSIONS if exp > months)
    expansion.percentile_vs_history = (len(HISTORICAL_EXPANSIONS) - longer_expansions) / len(HISTORICAL_EXPANSIONS) * 100

    # Traffic light based on relative age
    if expansion.percentile_vs_history > 90:
        expansion.traffic_light = "yellow"  # Very long by historical standards
    elif expansion.percentile_vs_history > 75:
        expansion.traffic_light = "yellow"
    else:
        expansion.traffic_light = "green"

    # Interpretation
    expansion.interpretation = (
        f"Current expansion: {expansion.months_since_recession} months "
        f"({expansion.years_since_recession:.1f} years) since June 2020. "
        f"This ranks in the {expansion.percentile_vs_history:.0f}th percentile of post-1945 expansions. "
        f"Historical average: {expansion.historical_average:.0f} months, "
        f"median: {expansion.historical_median:.0f} months. "
    )

    if expansion.percentile_vs_history > 75:
        expansion.interpretation += (
            "Expansion is mature by historical standards. "
            "However, expansions don't die of old age - they end due to shocks or imbalances."
        )
    elif expansion.percentile_vs_history > 50:
        expansion.interpretation += (
            "Expansion is middle-aged. Still room for continued growth if no major shocks."
        )
    else:
        expansion.interpretation += (
            "Expansion is relatively young. Historically, most recessions occur later in the cycle."
        )

    return expansion


def get_recession_dashboard(data: dict) -> dict:
    """
    Generate comprehensive recession risk dashboard.

    Args:
        data: Dict of series_id -> SeriesData or dict with 'values' key
              Expected series: T10Y2Y, T10Y3M, ICSA, PERMIT, UMCSENT,
                              DGORDER, AWHMAN, UNRATE

    Returns:
        Dict with all recession indicators and traffic light summary:
        {
            'yield_curve': YieldCurveSignal,
            'leading_indicators': LeadingIndicatorsComposite,
            'recession_probability': RecessionProbability,
            'expansion_age': ExpansionAge,
            'overall_status': str,  # "green", "yellow", "red"
            'summary': str,
        }
    """
    # Analyze each component
    yield_curve = analyze_yield_curve(data)
    leading_indicators = analyze_leading_indicators(data)
    recession_prob = calculate_recession_probability(yield_curve, leading_indicators, data)
    expansion_age = calculate_expansion_age()

    # Determine overall status
    red_count = sum(1 for status in [
        yield_curve.traffic_light,
        leading_indicators.traffic_light,
        recession_prob.traffic_light,
    ] if status == "red")

    yellow_count = sum(1 for status in [
        yield_curve.traffic_light,
        leading_indicators.traffic_light,
        recession_prob.traffic_light,
        expansion_age.traffic_light,
    ] if status == "yellow")

    if red_count >= 2:
        overall_status = "red"
        overall_message = "HIGH RECESSION RISK"
    elif red_count >= 1 or yellow_count >= 2:
        overall_status = "yellow"
        overall_message = "ELEVATED CAUTION"
    else:
        overall_status = "green"
        overall_message = "LOW RECESSION RISK"

    # Build summary
    summary = f"RECESSION DASHBOARD: {overall_message}\n\n"
    summary += f"Overall Assessment: {overall_status.upper()}\n"
    summary += f"12-Month Recession Probability: {recession_prob.probability_12m:.0%}\n"
    summary += f"Expansion Age: {expansion_age.months_since_recession} months\n\n"

    summary += "SIGNAL BREAKDOWN:\n"
    summary += f"  Yield Curve: {yield_curve.traffic_light.upper()} - {yield_curve.status}\n"
    summary += f"  Leading Indicators: {leading_indicators.traffic_light.upper()} (score: {leading_indicators.composite_score:.2f})\n"
    summary += f"  Recession Probability: {recession_prob.traffic_light.upper()}\n"
    summary += f"  Expansion Age: {expansion_age.traffic_light.upper()}\n\n"

    summary += "KEY OBSERVATIONS:\n"
    summary += f"  - {yield_curve.interpretation[:200]}...\n" if len(yield_curve.interpretation) > 200 else f"  - {yield_curve.interpretation}\n"
    summary += f"  - {leading_indicators.interpretation[:200]}...\n" if len(leading_indicators.interpretation) > 200 else f"  - {leading_indicators.interpretation}\n"

    return {
        'yield_curve': yield_curve,
        'leading_indicators': leading_indicators,
        'recession_probability': recession_prob,
        'expansion_age': expansion_age,
        'overall_status': overall_status,
        'summary': summary,
    }


# Test with mock data
if __name__ == "__main__":
    print("=" * 70)
    print("RECESSION FRAMEWORK TEST")
    print("=" * 70)

    # Mock data simulating current economic conditions
    mock_data = {
        # Yield curve (example: mildly inverted)
        'T10Y2Y': {'values': [-0.15, -0.10, -0.05, 0.05, 0.10]},
        'T10Y3M': {'values': [-0.30, -0.25, -0.20, -0.10, 0.05]},

        # Initial claims (weekly, in thousands - healthy at ~220K)
        'ICSA': {'values': [210000, 215000, 208000, 220000, 225000, 218000]},

        # Building permits (monthly, annualized - moderate at ~1.4M)
        'PERMIT': {'values': [1450, 1420, 1380, 1400, 1350]},

        # Consumer sentiment (index - below average at ~65)
        'UMCSENT': {'values': [68, 65, 63, 66, 64]},

        # Durable goods orders (billions)
        'DGORDER': {'values': [285000, 290000, 288000, 292000, 295000]},

        # Average weekly hours manufacturing
        'AWHMAN': {'values': [40.2, 40.1, 40.0, 39.9, 40.1]},

        # Unemployment rate
        'UNRATE': {'values': [3.7, 3.8, 3.9, 4.0, 4.1, 4.2]},
    }

    # Run dashboard
    dashboard = get_recession_dashboard(mock_data)

    print("\n" + dashboard['summary'])

    print("\nDETAILED COMPONENT ANALYSIS:")
    print("-" * 70)

    print("\n1. YIELD CURVE SIGNAL:")
    yc = dashboard['yield_curve']
    print(f"   Status: {yc.status} | Traffic Light: {yc.traffic_light}")
    print(f"   10Y-2Y Spread: {yc.spread_10y_2y}")
    print(f"   10Y-3M Spread: {yc.spread_10y_3m}")
    print(f"   Interpretation: {yc.interpretation}")

    print("\n2. LEADING INDICATORS COMPOSITE:")
    li = dashboard['leading_indicators']
    print(f"   Composite Score: {li.composite_score:.2f} | Traffic Light: {li.traffic_light}")
    for ind in li.indicators:
        status = "N/A" if not ind.data_available else f"Score: {ind.score}"
        print(f"   - {ind.name}: {status}")
        if ind.data_available:
            print(f"     {ind.interpretation}")
        elif ind.note:
            print(f"     Note: {ind.note}")

    print("\n3. RECESSION PROBABILITY:")
    rp = dashboard['recession_probability']
    print(f"   6-Month Probability: {rp.probability_6m:.0%}")
    print(f"   12-Month Probability: {rp.probability_12m:.0%}")
    print(f"   Confidence: {rp.confidence}")
    print(f"   Traffic Light: {rp.traffic_light}")
    print(f"   Interpretation: {rp.interpretation}")

    print("\n4. EXPANSION AGE:")
    ea = dashboard['expansion_age']
    print(f"   Months Since Recession End: {ea.months_since_recession}")
    print(f"   Years: {ea.years_since_recession:.1f}")
    print(f"   Percentile vs History: {ea.percentile_vs_history:.0f}th")
    print(f"   Traffic Light: {ea.traffic_light}")
    print(f"   Interpretation: {ea.interpretation}")

    print("\n" + "=" * 70)
    print(f"OVERALL STATUS: {dashboard['overall_status'].upper()}")
    print("=" * 70)

    # Test with more pessimistic data
    print("\n\nTESTING WITH PESSIMISTIC SCENARIO:")
    print("-" * 70)

    pessimistic_data = {
        'T10Y2Y': {'values': [-0.80, -0.75, -0.70, -0.65, -0.60]},
        'T10Y3M': {'values': [-1.0, -0.95, -0.90, -0.85, -0.80]},
        'ICSA': {'values': [280000, 310000, 350000, 380000, 420000]},
        'PERMIT': {'values': [1100, 1000, 950, 900, 850]},
        'UMCSENT': {'values': [62, 58, 55, 52, 50]},
        'DGORDER': {'values': [290000, 285000, 275000, 270000, 260000]},
        'AWHMAN': {'values': [40.0, 39.8, 39.5, 39.2, 39.0]},
        'UNRATE': {'values': [3.7, 3.9, 4.2, 4.5, 4.8]},
    }

    pessimistic_dashboard = get_recession_dashboard(pessimistic_data)
    print(pessimistic_dashboard['summary'])
    print(f"\nOVERALL STATUS: {pessimistic_dashboard['overall_status'].upper()}")
    print(f"12-Month Probability: {pessimistic_dashboard['recession_probability'].probability_12m:.0%}")
