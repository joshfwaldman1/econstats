"""
Labor Market Analysis Frameworks

This module provides economic frameworks for analyzing labor market conditions
using FRED data series. Each framework includes calculation and interpretation
functions with plain English explanations.

Frameworks included:
1. BEVERIDGE_CURVE - Vacancy-unemployment relationship and matching efficiency
2. SAHM_RULE - Real-time recession probability indicator
3. LABOR_MARKET_HEAT - Composite labor market tightness measure
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics


# =============================================================================
# BEVERIDGE CURVE FRAMEWORK
# =============================================================================

class BeveridgePosition(Enum):
    """Classification of labor market tightness based on Beveridge curve position."""
    VERY_TIGHT = "very_tight"      # High vacancies, low unemployment
    TIGHT = "tight"                 # Above-trend vacancies relative to unemployment
    BALANCED = "balanced"           # Near historical norm
    SLACK = "slack"                 # Below-trend vacancies relative to unemployment
    VERY_SLACK = "very_slack"       # Low vacancies, high unemployment


# Required FRED series for Beveridge Curve analysis
BEVERIDGE_CURVE_SERIES = [
    "JTSJOL",   # Job Openings: Total Nonfarm (thousands)
    "UNRATE",   # Unemployment Rate (percent)
]

# Thresholds for Beveridge curve interpretation
# Based on historical ranges (2001-2024)
BEVERIDGE_THRESHOLDS = {
    "vacancy_rate_high": 7.0,       # Job openings as % of labor force
    "vacancy_rate_low": 3.0,
    "unemployment_low": 4.0,        # Percent
    "unemployment_high": 6.0,
    "matching_efficiency_shift": 0.5,  # Standard deviations from trend
}


def calculate_beveridge_curve(data: Dict) -> Dict:
    """
    Calculate Beveridge curve position and matching efficiency.

    The Beveridge curve describes the inverse relationship between job vacancies
    and unemployment. A tight labor market shows high vacancies with low
    unemployment (upper-left), while a slack market shows the opposite (lower-right).

    Outward shifts in the curve (same unemployment but higher vacancies) indicate
    reduced matching efficiency - workers and jobs are having trouble connecting.
    This can signal structural changes like skills mismatches or geographic
    immobility.

    Args:
        data: Dictionary containing:
            - 'JTSJOL': Job openings level (thousands) or list of recent values
            - 'UNRATE': Unemployment rate (percent) or list of recent values
            - 'labor_force': Labor force level (thousands), optional
            - 'historical_vacancy_rates': List of historical vacancy rates, optional
            - 'historical_unemployment': List of historical unemployment rates, optional

    Returns:
        Dictionary with:
            - vacancy_rate: Current job openings as % of labor force
            - unemployment_rate: Current unemployment rate
            - position: BeveridgePosition enum value
            - vacancies_per_unemployed: Ratio of openings to unemployed persons
            - matching_efficiency_deviation: How far from historical trend
            - curve_shift_detected: Boolean if significant outward shift
    """
    # Extract current values (handle both single values and lists)
    jtsjol = data.get("JTSJOL")
    unrate = data.get("UNRATE")

    if isinstance(jtsjol, list):
        jtsjol = jtsjol[-1] if jtsjol else None
    if isinstance(unrate, list):
        unrate = unrate[-1] if unrate else None

    if jtsjol is None or unrate is None:
        return {"error": "Missing required data: JTSJOL and UNRATE"}

    # Calculate vacancy rate (job openings as % of labor force)
    # Default labor force ~165 million if not provided
    labor_force = data.get("labor_force", 165000)
    vacancy_rate = (jtsjol / labor_force) * 100

    # Calculate vacancies per unemployed person
    unemployed_level = data.get("UNEMPLOY")
    if unemployed_level is None:
        # Estimate from unemployment rate and labor force
        unemployed_level = (unrate / 100) * labor_force
    vacancies_per_unemployed = jtsjol / unemployed_level if unemployed_level > 0 else 0

    # Determine Beveridge curve position
    position = _classify_beveridge_position(vacancy_rate, unrate)

    # Calculate matching efficiency deviation
    # Compare current vacancy rate to what historical trend would predict
    historical_vr = data.get("historical_vacancy_rates", [])
    historical_ur = data.get("historical_unemployment", [])

    matching_efficiency_deviation = 0.0
    curve_shift_detected = False

    if len(historical_vr) >= 12 and len(historical_ur) >= 12:
        # Simple regression-based approach: predict vacancy rate from unemployment
        # and compare to actual
        predicted_vr = _predict_vacancy_rate_from_history(
            unrate, historical_ur, historical_vr
        )
        if predicted_vr is not None:
            deviation = vacancy_rate - predicted_vr
            std_dev = statistics.stdev(historical_vr) if len(historical_vr) > 1 else 1.0
            matching_efficiency_deviation = deviation / std_dev if std_dev > 0 else 0
            curve_shift_detected = abs(matching_efficiency_deviation) > BEVERIDGE_THRESHOLDS["matching_efficiency_shift"]

    return {
        "vacancy_rate": round(vacancy_rate, 2),
        "unemployment_rate": round(unrate, 2),
        "position": position,
        "vacancies_per_unemployed": round(vacancies_per_unemployed, 2),
        "matching_efficiency_deviation": round(matching_efficiency_deviation, 2),
        "curve_shift_detected": curve_shift_detected,
    }


def _classify_beveridge_position(vacancy_rate: float, unemployment_rate: float) -> BeveridgePosition:
    """Classify position on the Beveridge curve based on vacancy and unemployment rates."""
    vr_high = BEVERIDGE_THRESHOLDS["vacancy_rate_high"]
    vr_low = BEVERIDGE_THRESHOLDS["vacancy_rate_low"]
    ur_high = BEVERIDGE_THRESHOLDS["unemployment_high"]
    ur_low = BEVERIDGE_THRESHOLDS["unemployment_low"]

    if vacancy_rate >= vr_high and unemployment_rate <= ur_low:
        return BeveridgePosition.VERY_TIGHT
    elif vacancy_rate >= vr_low and unemployment_rate <= ur_high:
        if vacancy_rate > (vr_high + vr_low) / 2 or unemployment_rate < (ur_high + ur_low) / 2:
            return BeveridgePosition.TIGHT
        return BeveridgePosition.BALANCED
    elif vacancy_rate <= vr_low and unemployment_rate >= ur_high:
        return BeveridgePosition.VERY_SLACK
    elif vacancy_rate < (vr_high + vr_low) / 2 and unemployment_rate > (ur_high + ur_low) / 2:
        return BeveridgePosition.SLACK
    else:
        return BeveridgePosition.BALANCED


def _predict_vacancy_rate_from_history(
    current_ur: float,
    historical_ur: List[float],
    historical_vr: List[float]
) -> Optional[float]:
    """Simple linear prediction of vacancy rate from unemployment rate using historical data."""
    n = len(historical_ur)
    if n < 2 or len(historical_vr) < 2:
        return None

    # Use min of both lists
    n = min(n, len(historical_vr))
    ur = historical_ur[:n]
    vr = historical_vr[:n]

    # Simple linear regression
    ur_mean = statistics.mean(ur)
    vr_mean = statistics.mean(vr)

    numerator = sum((ur[i] - ur_mean) * (vr[i] - vr_mean) for i in range(n))
    denominator = sum((ur[i] - ur_mean) ** 2 for i in range(n))

    if denominator == 0:
        return vr_mean

    slope = numerator / denominator
    intercept = vr_mean - slope * ur_mean

    return slope * current_ur + intercept


def interpret_beveridge_curve(result: Dict) -> str:
    """
    Generate plain English interpretation of Beveridge curve analysis.

    Args:
        result: Output from calculate_beveridge_curve()

    Returns:
        Human-readable interpretation of labor market conditions.
    """
    if "error" in result:
        return f"Unable to analyze Beveridge curve: {result['error']}"

    position = result["position"]
    vr = result["vacancy_rate"]
    ur = result["unemployment_rate"]
    vpu = result["vacancies_per_unemployed"]
    shift = result["curve_shift_detected"]

    # Position interpretation
    position_text = {
        BeveridgePosition.VERY_TIGHT: (
            f"The labor market is very tight. With a vacancy rate of {vr}% and "
            f"unemployment at {ur}%, employers are competing intensely for workers. "
            f"There are {vpu} job openings for every unemployed person."
        ),
        BeveridgePosition.TIGHT: (
            f"The labor market is tight. Vacancies ({vr}%) are elevated relative to "
            f"unemployment ({ur}%), with {vpu} openings per unemployed worker. "
            "Employers may face hiring difficulties."
        ),
        BeveridgePosition.BALANCED: (
            f"The labor market appears balanced. The vacancy rate ({vr}%) and "
            f"unemployment rate ({ur}%) are near historical norms, with {vpu} "
            "openings per unemployed worker."
        ),
        BeveridgePosition.SLACK: (
            f"The labor market shows slack. With vacancies at {vr}% and unemployment "
            f"at {ur}%, workers face reduced job-finding prospects. There are only "
            f"{vpu} openings per unemployed person."
        ),
        BeveridgePosition.VERY_SLACK: (
            f"The labor market is very slack. Low vacancies ({vr}%) combined with "
            f"high unemployment ({ur}%) indicate weak labor demand. Only {vpu} "
            "openings exist per unemployed worker."
        ),
    }

    interpretation = position_text.get(position, "Unable to classify labor market position.")

    # Add matching efficiency commentary
    if shift:
        deviation = result["matching_efficiency_deviation"]
        if deviation > 0:
            interpretation += (
                "\n\nNotably, the Beveridge curve appears to have shifted outward - "
                "vacancy rates are higher than historical patterns would predict for "
                "this unemployment level. This suggests reduced matching efficiency, "
                "possibly due to skills mismatches, geographic barriers, or changes "
                "in worker preferences."
            )
        else:
            interpretation += (
                "\n\nThe Beveridge curve appears to have shifted inward - vacancies "
                "are lower than expected, suggesting improved matching efficiency "
                "or structural changes in labor market dynamics."
            )

    return interpretation


# =============================================================================
# SAHM RULE FRAMEWORK
# =============================================================================

# Required FRED series for Sahm Rule
SAHM_RULE_SERIES = [
    "UNRATE",   # Unemployment Rate (percent)
]

# Sahm Rule threshold
SAHM_THRESHOLD = 0.50  # 0.5 percentage point rise triggers recession signal


def calculate_sahm_rule(data: Dict) -> Dict:
    """
    Calculate the Sahm Rule recession indicator.

    The Sahm Rule identifies the start of a recession when the 3-month moving
    average of the national unemployment rate rises by 0.50 percentage points
    or more relative to its low during the previous 12 months.

    This indicator was developed by economist Claudia Sahm and has accurately
    identified every U.S. recession since 1970 in real-time. It triggers near
    the start of recessions, making it valuable for timely policy response.

    Economic logic: When unemployment begins rising meaningfully from its
    recent low, it typically signals the start of a self-reinforcing downturn
    where job losses lead to reduced spending, causing further job losses.

    Args:
        data: Dictionary containing:
            - 'UNRATE': List of at least 15 monthly unemployment rates
                       (most recent last), or single current value with
                       'unrate_3mo_avg' and 'unrate_12mo_low' provided

    Returns:
        Dictionary with:
            - current_3mo_avg: 3-month average unemployment rate
            - twelve_month_low: Lowest 3-month avg in prior 12 months
            - sahm_value: Current Sahm indicator value
            - threshold: Trigger threshold (0.50)
            - triggered: Boolean if recession signal is on
            - distance_to_trigger: How far from triggering (negative = already triggered)
            - risk_level: 'low', 'elevated', 'high', or 'triggered'
    """
    unrate_data = data.get("UNRATE")

    # Handle pre-calculated values
    if isinstance(unrate_data, (int, float)):
        current_3mo_avg = data.get("unrate_3mo_avg", unrate_data)
        twelve_month_low = data.get("unrate_12mo_low")
        if twelve_month_low is None:
            return {"error": "Need either 15 months of UNRATE data or unrate_12mo_low"}
    elif isinstance(unrate_data, list):
        if len(unrate_data) < 15:
            return {"error": f"Need at least 15 months of unemployment data, got {len(unrate_data)}"}

        # Calculate 3-month averages
        three_month_avgs = []
        for i in range(len(unrate_data) - 2):
            avg = statistics.mean(unrate_data[i:i+3])
            three_month_avgs.append(avg)

        current_3mo_avg = three_month_avgs[-1]
        # Look at 12 months of 3-month averages before the current one
        prior_12_month_avgs = three_month_avgs[-13:-1] if len(three_month_avgs) >= 13 else three_month_avgs[:-1]
        twelve_month_low = min(prior_12_month_avgs) if prior_12_month_avgs else current_3mo_avg
    else:
        return {"error": "UNRATE must be a number or list of monthly values"}

    # Calculate Sahm indicator
    sahm_value = current_3mo_avg - twelve_month_low
    triggered = sahm_value >= SAHM_THRESHOLD
    distance_to_trigger = SAHM_THRESHOLD - sahm_value

    # Classify risk level
    if triggered:
        risk_level = "triggered"
    elif sahm_value >= 0.3:
        risk_level = "high"
    elif sahm_value >= 0.2:
        risk_level = "elevated"
    else:
        risk_level = "low"

    return {
        "current_3mo_avg": round(current_3mo_avg, 2),
        "twelve_month_low": round(twelve_month_low, 2),
        "sahm_value": round(sahm_value, 2),
        "threshold": SAHM_THRESHOLD,
        "triggered": triggered,
        "distance_to_trigger": round(distance_to_trigger, 2),
        "risk_level": risk_level,
    }


def interpret_sahm_rule(result: Dict) -> str:
    """
    Generate plain English interpretation of Sahm Rule analysis.

    Args:
        result: Output from calculate_sahm_rule()

    Returns:
        Human-readable interpretation of recession risk.
    """
    if "error" in result:
        return f"Unable to calculate Sahm Rule: {result['error']}"

    sahm = result["sahm_value"]
    threshold = result["threshold"]
    current_avg = result["current_3mo_avg"]
    low = result["twelve_month_low"]
    distance = result["distance_to_trigger"]
    triggered = result["triggered"]
    risk = result["risk_level"]

    if triggered:
        interpretation = (
            f"RECESSION SIGNAL TRIGGERED. The Sahm Rule indicator stands at {sahm:.2f}, "
            f"exceeding the {threshold} threshold. The 3-month average unemployment rate "
            f"({current_avg}%) has risen {sahm:.2f} percentage points from its 12-month "
            f"low of {low}%. Historically, this pattern has marked the beginning of every "
            "U.S. recession since 1970."
        )
    elif risk == "high":
        interpretation = (
            f"Recession risk is elevated. The Sahm indicator at {sahm:.2f} is approaching "
            f"the {threshold} trigger threshold (only {distance:.2f}pp away). Unemployment "
            f"has risen from a 12-month low of {low}% to a 3-month average of {current_avg}%. "
            "Close monitoring is warranted."
        )
    elif risk == "elevated":
        interpretation = (
            f"The Sahm indicator shows some deterioration at {sahm:.2f}, still {distance:.2f} "
            f"percentage points below the {threshold} recession trigger. The 3-month average "
            f"unemployment ({current_avg}%) has edged up from its recent low of {low}%. "
            "This bears watching but is not yet alarming."
        )
    else:
        interpretation = (
            f"The Sahm Rule indicator is at {sahm:.2f}, well below the {threshold} recession "
            f"threshold ({distance:.2f}pp of cushion). The 3-month average unemployment rate "
            f"of {current_avg}% remains close to its 12-month low of {low}%. No recession "
            "signal is present."
        )

    return interpretation


# =============================================================================
# LABOR MARKET HEAT FRAMEWORK
# =============================================================================

# Required FRED series for Labor Market Heat
LABOR_MARKET_HEAT_SERIES = [
    "JTSQUR",      # Quits Rate: Total Nonfarm (percent)
    "JTSJOL",      # Job Openings: Total Nonfarm (thousands)
    "UNEMPLOY",    # Unemployment Level (thousands)
    "LNS12300060", # Employment-Population Ratio - 25-54 Yrs (percent)
]

# Historical benchmarks for heat indicators (approximate 2015-2019 averages as "normal")
HEAT_BENCHMARKS = {
    "quits_rate_hot": 2.4,        # Above this = very confident workers
    "quits_rate_normal": 2.2,     # Pre-pandemic average
    "quits_rate_cold": 1.8,       # Below this = workers scared to leave

    "openings_per_unemployed_hot": 1.2,    # Above this = very tight
    "openings_per_unemployed_normal": 0.8, # Balanced
    "openings_per_unemployed_cold": 0.5,   # Below this = slack

    "prime_epop_hot": 80.5,       # Near historical highs
    "prime_epop_normal": 79.0,    # 2019 level
    "prime_epop_cold": 76.0,      # Significant slack

    "wage_productivity_gap_hot": 1.0,    # Wages outpacing productivity
    "wage_productivity_gap_cold": -1.0,  # Wages lagging badly
}


def calculate_labor_market_heat(data: Dict) -> Dict:
    """
    Calculate a composite measure of labor market tightness.

    This framework combines multiple indicators to assess overall labor market
    conditions, as no single metric tells the full story:

    1. Quits Rate: When workers voluntarily leave jobs at high rates, it signals
       confidence in finding new/better positions. Low quits suggest fear.

    2. Job Openings per Unemployed: A direct measure of labor market tightness.
       Values above 1.0 mean more open jobs than job seekers.

    3. Prime-Age Employment-Population Ratio (25-54): Measures labor market
       utilization without demographic distortions from aging population or
       changing school enrollment.

    4. Wage Growth vs Productivity: When wage growth exceeds productivity gains,
       it suggests excess labor demand (and potential inflation pressure).

    Args:
        data: Dictionary containing:
            - 'JTSQUR': Quits rate (percent)
            - 'JTSJOL': Job openings (thousands)
            - 'UNEMPLOY': Unemployment level (thousands)
            - 'LNS12300060': Prime-age employment-population ratio (percent)
            - 'wage_growth': Optional - year-over-year wage growth (percent)
            - 'productivity_growth': Optional - productivity growth (percent)

    Returns:
        Dictionary with component scores, composite heat index, and classification.
    """
    # Extract values
    quits_rate = data.get("JTSQUR")
    job_openings = data.get("JTSJOL")
    unemployed = data.get("UNEMPLOY")
    prime_epop = data.get("LNS12300060")
    wage_growth = data.get("wage_growth")
    productivity_growth = data.get("productivity_growth")

    # Handle list inputs (take most recent)
    if isinstance(quits_rate, list):
        quits_rate = quits_rate[-1] if quits_rate else None
    if isinstance(job_openings, list):
        job_openings = job_openings[-1] if job_openings else None
    if isinstance(unemployed, list):
        unemployed = unemployed[-1] if unemployed else None
    if isinstance(prime_epop, list):
        prime_epop = prime_epop[-1] if prime_epop else None

    result = {
        "components": {},
        "component_scores": {},
        "missing_components": [],
    }

    # Score each component on a -2 to +2 scale
    # Negative = cold/slack, Positive = hot/tight
    scores = []

    # 1. Quits Rate
    if quits_rate is not None:
        result["components"]["quits_rate"] = round(quits_rate, 2)
        quits_score = _score_indicator(
            quits_rate,
            cold=HEAT_BENCHMARKS["quits_rate_cold"],
            normal=HEAT_BENCHMARKS["quits_rate_normal"],
            hot=HEAT_BENCHMARKS["quits_rate_hot"]
        )
        result["component_scores"]["quits_rate"] = round(quits_score, 2)
        scores.append(quits_score)
    else:
        result["missing_components"].append("JTSQUR")

    # 2. Job Openings per Unemployed
    if job_openings is not None and unemployed is not None and unemployed > 0:
        openings_per_unemployed = job_openings / unemployed
        result["components"]["openings_per_unemployed"] = round(openings_per_unemployed, 2)
        opu_score = _score_indicator(
            openings_per_unemployed,
            cold=HEAT_BENCHMARKS["openings_per_unemployed_cold"],
            normal=HEAT_BENCHMARKS["openings_per_unemployed_normal"],
            hot=HEAT_BENCHMARKS["openings_per_unemployed_hot"]
        )
        result["component_scores"]["openings_per_unemployed"] = round(opu_score, 2)
        scores.append(opu_score)
    else:
        if job_openings is None:
            result["missing_components"].append("JTSJOL")
        if unemployed is None:
            result["missing_components"].append("UNEMPLOY")

    # 3. Prime-Age EPOP
    if prime_epop is not None:
        result["components"]["prime_epop"] = round(prime_epop, 2)
        epop_score = _score_indicator(
            prime_epop,
            cold=HEAT_BENCHMARKS["prime_epop_cold"],
            normal=HEAT_BENCHMARKS["prime_epop_normal"],
            hot=HEAT_BENCHMARKS["prime_epop_hot"]
        )
        result["component_scores"]["prime_epop"] = round(epop_score, 2)
        scores.append(epop_score)
    else:
        result["missing_components"].append("LNS12300060")

    # 4. Wage-Productivity Gap (optional but informative)
    if wage_growth is not None and productivity_growth is not None:
        wage_prod_gap = wage_growth - productivity_growth
        result["components"]["wage_productivity_gap"] = round(wage_prod_gap, 2)
        wpg_score = _score_indicator(
            wage_prod_gap,
            cold=HEAT_BENCHMARKS["wage_productivity_gap_cold"],
            normal=0.0,
            hot=HEAT_BENCHMARKS["wage_productivity_gap_hot"]
        )
        result["component_scores"]["wage_productivity_gap"] = round(wpg_score, 2)
        scores.append(wpg_score)

    # Calculate composite heat index
    if scores:
        heat_index = statistics.mean(scores)
        result["heat_index"] = round(heat_index, 2)
        result["classification"] = _classify_heat(heat_index)
    else:
        result["heat_index"] = None
        result["classification"] = "insufficient_data"

    return result


def _score_indicator(value: float, cold: float, normal: float, hot: float) -> float:
    """
    Score an indicator on a -2 to +2 scale.

    -2 = very cold (well below normal)
    -1 = cold (below normal)
     0 = normal
    +1 = hot (above normal)
    +2 = very hot (well above normal)
    """
    if value >= hot:
        # How far above hot threshold
        excess = value - hot
        range_size = hot - normal
        additional = min(excess / range_size, 1.0) if range_size > 0 else 0
        return 1.0 + additional
    elif value >= normal:
        # Between normal and hot
        return (value - normal) / (hot - normal) if hot != normal else 0
    elif value >= cold:
        # Between cold and normal
        return -((normal - value) / (normal - cold)) if normal != cold else 0
    else:
        # Below cold
        deficit = cold - value
        range_size = normal - cold
        additional = min(deficit / range_size, 1.0) if range_size > 0 else 0
        return -1.0 - additional


def _classify_heat(heat_index: float) -> str:
    """Classify overall labor market heat based on composite index."""
    if heat_index >= 1.5:
        return "overheating"
    elif heat_index >= 0.5:
        return "hot"
    elif heat_index >= -0.5:
        return "balanced"
    elif heat_index >= -1.5:
        return "cooling"
    else:
        return "cold"


def interpret_labor_market_heat(result: Dict) -> str:
    """
    Generate plain English interpretation of labor market heat analysis.

    Args:
        result: Output from calculate_labor_market_heat()

    Returns:
        Human-readable interpretation of labor market tightness.
    """
    if result.get("classification") == "insufficient_data":
        missing = result.get("missing_components", [])
        return f"Insufficient data for heat analysis. Missing: {', '.join(missing)}"

    heat_index = result["heat_index"]
    classification = result["classification"]
    components = result["components"]
    scores = result["component_scores"]

    # Overall assessment
    heat_descriptions = {
        "overheating": (
            f"The labor market is OVERHEATING (heat index: {heat_index:+.2f}). "
            "Multiple indicators show extreme tightness that typically generates "
            "significant wage pressure and may require policy response."
        ),
        "hot": (
            f"The labor market is HOT (heat index: {heat_index:+.2f}). "
            "Conditions favor workers, with strong hiring demand and limited "
            "labor supply. Some wage pressure is likely."
        ),
        "balanced": (
            f"The labor market is BALANCED (heat index: {heat_index:+.2f}). "
            "Supply and demand appear roughly in equilibrium, consistent with "
            "sustainable growth."
        ),
        "cooling": (
            f"The labor market is COOLING (heat index: {heat_index:+.2f}). "
            "Conditions have softened from peak tightness. Workers have less "
            "bargaining power than before."
        ),
        "cold": (
            f"The labor market is COLD (heat index: {heat_index:+.2f}). "
            "Slack conditions prevail, with limited opportunities for workers "
            "and minimal wage pressure."
        ),
    }

    interpretation = heat_descriptions.get(classification, "Unable to classify labor market heat.")

    # Add component details
    details = []

    if "quits_rate" in components:
        qr = components["quits_rate"]
        qs = scores["quits_rate"]
        if qs > 0.5:
            details.append(f"Workers are confident: the quits rate of {qr}% shows people are willing to leave jobs for better opportunities")
        elif qs < -0.5:
            details.append(f"Workers are cautious: the low quits rate of {qr}% suggests people are staying put")

    if "openings_per_unemployed" in components:
        opu = components["openings_per_unemployed"]
        if opu > 1.0:
            details.append(f"There are {opu} job openings per unemployed person - more jobs than job seekers")
        else:
            details.append(f"There are {opu} job openings per unemployed person - job seekers outnumber openings")

    if "prime_epop" in components:
        epop = components["prime_epop"]
        es = scores["prime_epop"]
        if es > 0.5:
            details.append(f"Prime-age employment at {epop}% is historically strong")
        elif es < -0.5:
            details.append(f"Prime-age employment at {epop}% indicates underutilization")

    if "wage_productivity_gap" in components:
        gap = components["wage_productivity_gap"]
        if gap > 0.5:
            details.append(f"Wages are growing {gap:.1f}pp faster than productivity, adding to inflation pressure")
        elif gap < -0.5:
            details.append(f"Wage growth trails productivity by {abs(gap):.1f}pp, easing inflation concerns")

    if details:
        interpretation += "\n\nKey observations:\n- " + "\n- ".join(details)

    if result["missing_components"]:
        interpretation += f"\n\n(Note: Analysis excludes {', '.join(result['missing_components'])} due to missing data)"

    return interpretation


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_all_required_series() -> List[str]:
    """Return deduplicated list of all FRED series required for labor market analysis."""
    all_series = set()
    all_series.update(BEVERIDGE_CURVE_SERIES)
    all_series.update(SAHM_RULE_SERIES)
    all_series.update(LABOR_MARKET_HEAT_SERIES)
    return sorted(list(all_series))


def analyze_labor_market(data: Dict) -> Dict:
    """
    Run all labor market frameworks and return consolidated results.

    Args:
        data: Dictionary containing all required FRED series data

    Returns:
        Dictionary with results from all frameworks
    """
    return {
        "beveridge_curve": {
            "result": calculate_beveridge_curve(data),
            "interpretation": interpret_beveridge_curve(calculate_beveridge_curve(data)),
        },
        "sahm_rule": {
            "result": calculate_sahm_rule(data),
            "interpretation": interpret_sahm_rule(calculate_sahm_rule(data)),
        },
        "labor_market_heat": {
            "result": calculate_labor_market_heat(data),
            "interpretation": interpret_labor_market_heat(calculate_labor_market_heat(data)),
        },
        "required_series": get_all_required_series(),
    }


# =============================================================================
# TESTS WITH SAMPLE DATA
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("LABOR MARKET ANALYSIS FRAMEWORKS - TEST SUITE")
    print("=" * 70)

    # Sample data representing a tight labor market (similar to 2022-2023)
    tight_market_data = {
        "JTSJOL": 10500,  # 10.5 million job openings
        "UNRATE": [3.4, 3.5, 3.4, 3.6, 3.7, 3.6, 3.5, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 4.0, 4.1],
        "UNEMPLOY": 6500,  # 6.5 million unemployed
        "labor_force": 165000,  # 165 million
        "JTSQUR": 2.6,  # High quits rate
        "LNS12300060": 80.8,  # Strong prime-age employment
        "wage_growth": 5.0,
        "productivity_growth": 1.5,
        "historical_vacancy_rates": [4.5, 4.8, 5.0, 5.2, 5.5, 5.8, 6.0, 6.2, 6.5, 6.8, 7.0, 6.8],
        "historical_unemployment": [6.0, 5.5, 5.2, 4.8, 4.5, 4.2, 4.0, 3.8, 3.6, 3.5, 3.4, 3.5],
    }

    print("\n" + "-" * 70)
    print("TEST 1: BEVERIDGE CURVE - Tight Labor Market")
    print("-" * 70)
    bev_result = calculate_beveridge_curve(tight_market_data)
    print(f"Result: {bev_result}")
    print(f"\nInterpretation:\n{interpret_beveridge_curve(bev_result)}")

    print("\n" + "-" * 70)
    print("TEST 2: SAHM RULE - No Recession Signal")
    print("-" * 70)
    sahm_result = calculate_sahm_rule(tight_market_data)
    print(f"Result: {sahm_result}")
    print(f"\nInterpretation:\n{interpret_sahm_rule(sahm_result)}")

    print("\n" + "-" * 70)
    print("TEST 3: LABOR MARKET HEAT - Hot Market")
    print("-" * 70)
    heat_result = calculate_labor_market_heat(tight_market_data)
    print(f"Result: {heat_result}")
    print(f"\nInterpretation:\n{interpret_labor_market_heat(heat_result)}")

    # Sample data representing recession conditions
    recession_data = {
        "JTSJOL": 4000,  # Low job openings
        "UNRATE": [3.5, 3.6, 3.8, 4.0, 4.3, 4.6, 5.0, 5.4, 5.8, 6.2, 6.5, 6.8, 7.0, 7.2, 7.5],
        "UNEMPLOY": 12000,  # 12 million unemployed
        "labor_force": 160000,
        "JTSQUR": 1.6,  # Low quits
        "LNS12300060": 75.0,  # Weak prime-age employment
        "wage_growth": 2.0,
        "productivity_growth": 1.0,
    }

    print("\n" + "-" * 70)
    print("TEST 4: BEVERIDGE CURVE - Slack Market")
    print("-" * 70)
    bev_result2 = calculate_beveridge_curve(recession_data)
    print(f"Result: {bev_result2}")
    print(f"\nInterpretation:\n{interpret_beveridge_curve(bev_result2)}")

    print("\n" + "-" * 70)
    print("TEST 5: SAHM RULE - Recession Triggered")
    print("-" * 70)
    sahm_result2 = calculate_sahm_rule(recession_data)
    print(f"Result: {sahm_result2}")
    print(f"\nInterpretation:\n{interpret_sahm_rule(sahm_result2)}")

    print("\n" + "-" * 70)
    print("TEST 6: LABOR MARKET HEAT - Cold Market")
    print("-" * 70)
    heat_result2 = calculate_labor_market_heat(recession_data)
    print(f"Result: {heat_result2}")
    print(f"\nInterpretation:\n{interpret_labor_market_heat(heat_result2)}")

    print("\n" + "-" * 70)
    print("TEST 7: ALL REQUIRED FRED SERIES")
    print("-" * 70)
    print(f"Required series: {get_all_required_series()}")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
