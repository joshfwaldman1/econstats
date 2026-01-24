"""
Historical analogues module for EconStats.

Finds similar historical periods based on economic "fingerprints" and explains
what happened next. Useful for contextualizing current conditions.

Flow:
1. Define economic fingerprint dimensions (inflation, labor, Fed stance, growth, yield curve)
2. Match current conditions against historical periods
3. Return analogues with similarity scores and lessons learned
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =============================================================================
# ECONOMIC FINGERPRINT DIMENSIONS
# =============================================================================

class InflationRegime(Enum):
    """Inflation regime classification."""
    HIGH = "high"      # > 4%
    MODERATE = "moderate"  # 2-4%
    LOW = "low"        # < 2%


class LaborMarket(Enum):
    """Labor market conditions."""
    TIGHT = "tight"      # Unemployment < 4%
    BALANCED = "balanced"  # Unemployment 4-5%
    SLACK = "slack"      # Unemployment > 5%


class FedStance(Enum):
    """Federal Reserve policy stance."""
    TIGHTENING = "tightening"
    HOLDING = "holding"
    EASING = "easing"


class GrowthRegime(Enum):
    """GDP growth classification."""
    ABOVE_TREND = "above_trend"  # > 2.5%
    TREND = "trend"              # 1.5-2.5%
    BELOW_TREND = "below_trend"  # < 1.5%


class YieldCurve(Enum):
    """Yield curve shape (10Y-2Y spread)."""
    STEEP = "steep"      # > 100bp
    FLAT = "flat"        # 0-100bp
    INVERTED = "inverted"  # < 0


@dataclass
class EconomicFingerprint:
    """
    Economic fingerprint representing conditions at a point in time.

    Each dimension captures a key aspect of the economic environment.
    """
    inflation: InflationRegime
    labor_market: LaborMarket
    fed_stance: FedStance
    growth: GrowthRegime
    yield_curve: YieldCurve

    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        return {
            "inflation": self.inflation.value,
            "labor_market": self.labor_market.value,
            "fed_stance": self.fed_stance.value,
            "growth": self.growth.value,
            "yield_curve": self.yield_curve.value,
        }


@dataclass
class HistoricalPeriod:
    """
    A historical economic period with its fingerprint and outcome.
    """
    name: str
    period: str  # e.g., "1994-95"
    fingerprint: EconomicFingerprint
    conditions: str  # Description of conditions at the time
    fed_action: str  # What the Fed did
    outcome: str  # What happened to the economy
    key_lesson: str  # Main takeaway

    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        return {
            "name": self.name,
            "period": self.period,
            "fingerprint": self.fingerprint.to_dict(),
            "conditions": self.conditions,
            "fed_action": self.fed_action,
            "outcome": self.outcome,
            "key_lesson": self.key_lesson,
        }


# =============================================================================
# HISTORICAL PERIODS DATABASE
# =============================================================================

HISTORICAL_PERIODS = [
    HistoricalPeriod(
        name="1994-95 Soft Landing",
        period="1994-1995",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.MODERATE,
            labor_market=LaborMarket.BALANCED,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.ABOVE_TREND,
            yield_curve=YieldCurve.FLAT,
        ),
        conditions="Economy growing strongly (4%+), inflation ticking up from 2.5% to 3%, "
                   "unemployment around 5.5-6%. Bond market worried about inflation.",
        fed_action="Greenspan raised rates 300bp in 12 months (3% to 6%), preemptive move "
                   "before inflation became entrenched. Doubled rates without waiting for "
                   "inflation to spike.",
        outcome="Soft landing achieved. Growth slowed to sustainable pace, inflation contained "
                "around 3%, no recession. Unemployment continued falling to 5% by 1996. "
                "Set stage for late-90s boom.",
        key_lesson="Early, aggressive tightening can slow economy without breaking it. "
                   "The key was acting before inflation became entrenched, not waiting for "
                   "clear evidence of overheating.",
    ),

    HistoricalPeriod(
        name="2000-01 Tech Bust",
        period="2000-2001",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.MODERATE,
            labor_market=LaborMarket.TIGHT,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.ABOVE_TREND,
            yield_curve=YieldCurve.INVERTED,
        ),
        conditions="Tech bubble at peak, irrational exuberance in markets, NASDAQ up 400% "
                   "in 5 years. Unemployment at 4%, inflation around 3.5%. Yield curve "
                   "inverted in early 2000.",
        fed_action="Fed raised rates from 4.75% to 6.5% through May 2000, then pivoted "
                   "to aggressive cuts starting Jan 2001 (cut 475bp by end of 2001).",
        outcome="Recession March-November 2001. NASDAQ crashed 78% from peak. "
                "Unemployment rose from 4% to 6%. Recovery slow, jobless into 2003. "
                "Tech sector devastated, many dot-coms failed.",
        key_lesson="Yield curve inversion was the warning sign. Asset bubbles can mask "
                   "underlying economic fragility. When curves invert, recession typically "
                   "follows within 12-18 months.",
    ),

    HistoricalPeriod(
        name="2006-08 Housing Bust",
        period="2006-2008",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.MODERATE,
            labor_market=LaborMarket.TIGHT,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.TREND,
            yield_curve=YieldCurve.INVERTED,
        ),
        conditions="Housing bubble peaked 2006, subprime lending rampant. Unemployment 4.4%, "
                   "inflation 3-4%. Yield curve inverted 2006. Housing starts falling, "
                   "cracks appearing in mortgage markets.",
        fed_action="Fed raised rates to 5.25% by June 2006, held through 2007. Started "
                   "cutting Sept 2007, then emergency cuts and QE in 2008.",
        outcome="Severe recession Dec 2007 - June 2009, worst since Great Depression. "
                "Unemployment peaked at 10%. Housing prices fell 33% nationally. Financial "
                "crisis, bank failures, $700B bailout. Recovery took years.",
        key_lesson="Inverted yield curve + asset bubble = severe risk. Financial system "
                   "leverage amplified the housing bust into systemic crisis. The Fed was "
                   "too slow to recognize systemic risk.",
    ),

    HistoricalPeriod(
        name="2018-19 Mid-Cycle Pause",
        period="2018-2019",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.LOW,
            labor_market=LaborMarket.TIGHT,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.TREND,
            yield_curve=YieldCurve.FLAT,
        ),
        conditions="Economy growing ~2.5%, unemployment fell to 3.5% (50-year low). "
                   "Inflation stubbornly below 2% target. Trade war uncertainty. "
                   "Yield curve flattened, briefly inverted in Aug 2019.",
        fed_action="Fed raised rates to 2.5% by Dec 2018 (9th hike of cycle). Markets "
                   "tanked in Dec 2018. Powell pivoted - cut rates 3x in 2019 despite "
                   "low unemployment. 'Insurance cuts' to extend expansion.",
        outcome="No recession. Economy continued growing through 2019 into 2020. "
                "The pivot worked - expansion extended to become longest on record "
                "(until COVID). Markets recovered strongly.",
        key_lesson="Fed can pivot without triggering recession if underlying fundamentals "
                   "are sound. Low inflation gave flexibility to cut. 'Insurance cuts' can "
                   "work when economy is healthy but facing headwinds.",
    ),

    HistoricalPeriod(
        name="2022-24 Post-COVID Inflation Fight",
        period="2022-2024",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.HIGH,
            labor_market=LaborMarket.TIGHT,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.ABOVE_TREND,
            yield_curve=YieldCurve.INVERTED,
        ),
        conditions="Inflation hit 9.1% (June 2022), highest since 1981. Supply chain "
                   "disruptions, energy shock from Ukraine war, fiscal stimulus hangover. "
                   "Unemployment 3.4-3.7%, very tight labor market. Yield curve deeply inverted.",
        fed_action="Most aggressive tightening since Volcker: 525bp in 16 months "
                   "(0% to 5.25-5.5%). Held rates at peak for over a year. Started "
                   "cutting Sept 2024 as inflation fell toward target.",
        outcome="Inflation fell from 9.1% to ~2.5% without recession (as of late 2024). "
                "Unemployment rose only slightly to 4.2%. 'Immaculate disinflation' - "
                "soft landing achieved despite inverted curve and high starting inflation.",
        key_lesson="Supply-side inflation can resolve faster than demand-driven. "
                   "Labor market can remain strong during disinflation if productivity "
                   "holds up. Inverted curve doesn't always mean recession.",
    ),

    HistoricalPeriod(
        name="1979-82 Volcker Shock",
        period="1979-1982",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.HIGH,
            labor_market=LaborMarket.BALANCED,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.BELOW_TREND,
            yield_curve=YieldCurve.FLAT,
        ),
        conditions="Stagflation: inflation 13%+, unemployment 6-7%, growth stagnant. "
                   "Oil shocks, wage-price spiral, inflation expectations unanchored. "
                   "Decade of failed attempts to tame inflation.",
        fed_action="Volcker raised Fed funds to 20% (June 1981). Committed to crushing "
                   "inflation regardless of economic pain. Explicit break from past Fed policy.",
        outcome="Double-dip recession (1980, 1981-82). Unemployment peaked at 10.8%. "
                "But inflation broken - fell from 13% to 3% by 1983. Set stage for "
                "Great Moderation and 1983-2007 growth.",
        key_lesson="Entrenched inflation requires painful measures. Credibility matters - "
                   "Volcker's commitment broke expectations. Short-term pain, long-term gain. "
                   "Don't let inflation become embedded.",
    ),

    HistoricalPeriod(
        name="2015-16 Manufacturing Slowdown",
        period="2015-2016",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.LOW,
            labor_market=LaborMarket.BALANCED,
            fed_stance=FedStance.TIGHTENING,
            growth=GrowthRegime.TREND,
            yield_curve=YieldCurve.FLAT,
        ),
        conditions="Oil price collapse (from $100 to $30), China slowdown fears, "
                   "manufacturing recession but services held up. Unemployment 5%, "
                   "inflation below 2%. Fed had just started hiking (Dec 2015).",
        fed_action="Fed hiked once in Dec 2015, then paused for full year (2016). "
                   "Only raised once more in Dec 2016. Patient approach given global headwinds.",
        outcome="No recession. Economy muddled through. Manufacturing recovered in "
                   "2017. Services-led economy proved resilient to manufacturing weakness. "
                   "Expansion continued.",
        key_lesson="Sector-specific recessions don't always spread. Services can carry "
                   "economy through manufacturing weakness. Fed patience paid off - no need "
                   "to cut rates, just pause.",
    ),

    HistoricalPeriod(
        name="1990-91 S&L/Gulf War Recession",
        period="1990-1991",
        fingerprint=EconomicFingerprint(
            inflation=InflationRegime.MODERATE,
            labor_market=LaborMarket.BALANCED,
            fed_stance=FedStance.EASING,
            growth=GrowthRegime.BELOW_TREND,
            yield_curve=YieldCurve.FLAT,
        ),
        conditions="S&L crisis fallout, commercial real estate bust, oil spike from "
                   "Gulf War. Unemployment rising toward 6%, inflation 5-6%. Consumer "
                   "confidence cratering.",
        fed_action="Fed cut rates from 8% to 3% over 1990-1992. Aggressive easing but "
                   "banks reluctant to lend (credit crunch).",
        outcome="Mild recession (8 months). Unemployment rose to 7.8% but peaked after "
                "recession ended (jobless recovery). Recovery sluggish, contributed to "
                "Bush losing 1992 election.",
        key_lesson="Credit crunches limit Fed effectiveness. Even aggressive rate cuts "
                   "can't force banks to lend or consumers to borrow. Recovery can be "
                   "jobless even after recession ends.",
    ),
]


# =============================================================================
# MATCHING AND SIMILARITY FUNCTIONS
# =============================================================================

def _dimension_match_score(current_value: Enum, historical_value: Enum) -> float:
    """
    Calculate similarity score for a single dimension.

    Returns:
        1.0 for exact match
        0.5 for adjacent values (e.g., HIGH vs MODERATE)
        0.0 for opposite values (e.g., HIGH vs LOW)
    """
    if current_value == historical_value:
        return 1.0

    # Define adjacency for each dimension type
    adjacency_maps = {
        # Inflation: HIGH <-> MODERATE <-> LOW
        InflationRegime: {
            (InflationRegime.HIGH, InflationRegime.MODERATE): 0.5,
            (InflationRegime.MODERATE, InflationRegime.LOW): 0.5,
            (InflationRegime.HIGH, InflationRegime.LOW): 0.0,
        },
        # Labor: TIGHT <-> BALANCED <-> SLACK
        LaborMarket: {
            (LaborMarket.TIGHT, LaborMarket.BALANCED): 0.5,
            (LaborMarket.BALANCED, LaborMarket.SLACK): 0.5,
            (LaborMarket.TIGHT, LaborMarket.SLACK): 0.0,
        },
        # Fed: TIGHTENING <-> HOLDING <-> EASING
        FedStance: {
            (FedStance.TIGHTENING, FedStance.HOLDING): 0.5,
            (FedStance.HOLDING, FedStance.EASING): 0.5,
            (FedStance.TIGHTENING, FedStance.EASING): 0.0,
        },
        # Growth: ABOVE_TREND <-> TREND <-> BELOW_TREND
        GrowthRegime: {
            (GrowthRegime.ABOVE_TREND, GrowthRegime.TREND): 0.5,
            (GrowthRegime.TREND, GrowthRegime.BELOW_TREND): 0.5,
            (GrowthRegime.ABOVE_TREND, GrowthRegime.BELOW_TREND): 0.0,
        },
        # Yield curve: STEEP <-> FLAT <-> INVERTED
        YieldCurve: {
            (YieldCurve.STEEP, YieldCurve.FLAT): 0.5,
            (YieldCurve.FLAT, YieldCurve.INVERTED): 0.5,
            (YieldCurve.STEEP, YieldCurve.INVERTED): 0.0,
        },
    }

    enum_type = type(current_value)
    adj_map = adjacency_maps.get(enum_type, {})

    # Check both orderings
    pair1 = (current_value, historical_value)
    pair2 = (historical_value, current_value)

    return adj_map.get(pair1, adj_map.get(pair2, 0.0))


def calculate_similarity(current: EconomicFingerprint, historical: EconomicFingerprint,
                        weights: Optional[dict] = None) -> float:
    """
    Calculate overall similarity score between two economic fingerprints.

    Args:
        current: Current economic conditions fingerprint
        historical: Historical period fingerprint
        weights: Optional dimension weights (default: equal weights)

    Returns:
        Similarity score from 0.0 to 1.0 (100%)
    """
    if weights is None:
        weights = {
            "inflation": 1.0,
            "labor_market": 1.0,
            "fed_stance": 1.0,
            "growth": 1.0,
            "yield_curve": 1.0,
        }

    total_weight = sum(weights.values())
    weighted_score = 0.0

    # Calculate score for each dimension
    scores = {
        "inflation": _dimension_match_score(current.inflation, historical.inflation),
        "labor_market": _dimension_match_score(current.labor_market, historical.labor_market),
        "fed_stance": _dimension_match_score(current.fed_stance, historical.fed_stance),
        "growth": _dimension_match_score(current.growth, historical.growth),
        "yield_curve": _dimension_match_score(current.yield_curve, historical.yield_curve),
    }

    for dim, score in scores.items():
        weighted_score += score * weights.get(dim, 1.0)

    return weighted_score / total_weight


def find_key_difference(current: EconomicFingerprint, historical: HistoricalPeriod) -> str:
    """
    Identify the most significant difference between current and historical conditions.

    Returns a human-readable description of the key difference.
    """
    hist_fp = historical.fingerprint
    differences = []

    # Check each dimension
    if current.inflation != hist_fp.inflation:
        differences.append(
            f"inflation is {current.inflation.value} vs {hist_fp.inflation.value} then"
        )

    if current.labor_market != hist_fp.labor_market:
        differences.append(
            f"labor market is {current.labor_market.value} vs {hist_fp.labor_market.value} then"
        )

    if current.fed_stance != hist_fp.fed_stance:
        differences.append(
            f"Fed is {current.fed_stance.value} vs {hist_fp.fed_stance.value} then"
        )

    if current.growth != hist_fp.growth:
        differences.append(
            f"growth is {current.growth.value} vs {hist_fp.growth.value} then"
        )

    if current.yield_curve != hist_fp.yield_curve:
        differences.append(
            f"yield curve is {current.yield_curve.value} vs {hist_fp.yield_curve.value} then"
        )

    if not differences:
        return "No significant differences"

    # Return most significant difference (first one, or combine if few)
    if len(differences) <= 2:
        return "; ".join(differences).capitalize()
    else:
        return differences[0].capitalize() + f" (and {len(differences)-1} other differences)"


@dataclass
class HistoricalAnalogue:
    """
    A matched historical analogue with similarity score and context.
    """
    period: HistoricalPeriod
    similarity_pct: float  # 0-100
    key_difference: str

    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        return {
            "name": self.period.name,
            "period": self.period.period,
            "similarity_pct": round(self.similarity_pct, 1),
            "conditions": self.period.conditions,
            "what_happened": self.period.outcome,
            "key_difference": self.key_difference,
            "key_lesson": self.period.key_lesson,
        }


def find_analogues(current: dict, top_n: int = 3) -> list[HistoricalAnalogue]:
    """
    Find historical periods most similar to current conditions.

    Args:
        current: Dictionary with current economic conditions:
            - inflation: float (e.g., 2.5 for 2.5%)
            - unemployment: float (e.g., 4.2 for 4.2%)
            - fed_stance: str ("tightening", "holding", "easing")
            - gdp_growth: float (e.g., 2.0 for 2.0%)
            - yield_spread: float (10Y-2Y spread in bp, e.g., -50 for -0.5%)
        top_n: Number of top matches to return

    Returns:
        List of HistoricalAnalogue objects, sorted by similarity (highest first)
    """
    # Convert raw values to fingerprint
    current_fp = _values_to_fingerprint(current)

    # Calculate similarity for each historical period
    matches = []
    for period in HISTORICAL_PERIODS:
        similarity = calculate_similarity(current_fp, period.fingerprint)
        key_diff = find_key_difference(current_fp, period)

        matches.append(HistoricalAnalogue(
            period=period,
            similarity_pct=similarity * 100,
            key_difference=key_diff,
        ))

    # Sort by similarity (highest first)
    matches.sort(key=lambda x: x.similarity_pct, reverse=True)

    return matches[:top_n]


def _values_to_fingerprint(values: dict) -> EconomicFingerprint:
    """
    Convert raw economic values to a fingerprint.

    Args:
        values: Dictionary with raw economic values

    Returns:
        EconomicFingerprint object
    """
    # Inflation regime
    inflation_val = values.get("inflation", 2.5)
    if inflation_val > 4:
        inflation = InflationRegime.HIGH
    elif inflation_val >= 2:
        inflation = InflationRegime.MODERATE
    else:
        inflation = InflationRegime.LOW

    # Labor market
    unemp_val = values.get("unemployment", 4.5)
    if unemp_val < 4:
        labor = LaborMarket.TIGHT
    elif unemp_val <= 5:
        labor = LaborMarket.BALANCED
    else:
        labor = LaborMarket.SLACK

    # Fed stance
    fed_str = values.get("fed_stance", "holding").lower()
    if fed_str == "tightening":
        fed = FedStance.TIGHTENING
    elif fed_str == "easing":
        fed = FedStance.EASING
    else:
        fed = FedStance.HOLDING

    # Growth regime
    growth_val = values.get("gdp_growth", 2.0)
    if growth_val > 2.5:
        growth = GrowthRegime.ABOVE_TREND
    elif growth_val >= 1.5:
        growth = GrowthRegime.TREND
    else:
        growth = GrowthRegime.BELOW_TREND

    # Yield curve (spread in basis points)
    spread_val = values.get("yield_spread", 50)  # Default to flat
    if spread_val > 100:
        curve = YieldCurve.STEEP
    elif spread_val >= 0:
        curve = YieldCurve.FLAT
    else:
        curve = YieldCurve.INVERTED

    return EconomicFingerprint(
        inflation=inflation,
        labor_market=labor,
        fed_stance=fed,
        growth=growth,
        yield_curve=curve,
    )


# =============================================================================
# NARRATIVE GENERATION
# =============================================================================

def explain_historical_context(analogues: list[HistoricalAnalogue]) -> str:
    """
    Generate a narrative explanation of historical analogues.

    Args:
        analogues: List of HistoricalAnalogue objects (from find_analogues)

    Returns:
        Human-readable narrative comparing current conditions to history
    """
    if not analogues:
        return "No historical analogues found."

    lines = []

    # Lead with the best match
    best = analogues[0]
    lines.append(
        f"Current conditions most resemble the **{best.period.name}** "
        f"({best.similarity_pct:.0f}% match)."
    )
    lines.append("")

    # Describe the best match
    lines.append(f"**Then ({best.period.period}):** {best.period.conditions}")
    lines.append("")
    lines.append(f"**What the Fed did:** {best.period.fed_action}")
    lines.append("")
    lines.append(f"**What happened:** {best.period.outcome}")
    lines.append("")
    lines.append(f"**Key difference today:** {best.key_difference}")
    lines.append("")
    lines.append(f"**Lesson:** {best.period.key_lesson}")

    # Briefly mention other matches
    if len(analogues) > 1:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("**Other relevant periods:**")
        lines.append("")

        for analogue in analogues[1:]:
            lines.append(
                f"- **{analogue.period.name}** ({analogue.similarity_pct:.0f}% match): "
                f"{analogue.period.key_lesson}"
            )

    return "\n".join(lines)


def get_analogue_summary(current: dict, top_n: int = 3) -> dict:
    """
    Convenience function to get analogues and narrative in one call.

    Args:
        current: Dictionary with current economic conditions
        top_n: Number of top matches to return

    Returns:
        Dictionary with:
            - analogues: List of analogue dictionaries
            - narrative: Human-readable explanation
            - current_fingerprint: The classified current conditions
    """
    # Convert to fingerprint for display
    current_fp = _values_to_fingerprint(current)

    # Find analogues
    analogues = find_analogues(current, top_n=top_n)

    # Generate narrative
    narrative = explain_historical_context(analogues)

    return {
        "analogues": [a.to_dict() for a in analogues],
        "narrative": narrative,
        "current_fingerprint": current_fp.to_dict(),
    }


# =============================================================================
# TEST WITH CURRENT CONDITIONS
# =============================================================================

if __name__ == "__main__":
    # Approximate current conditions (late 2024 / early 2025)
    # Adjust these values based on actual current data
    current_conditions = {
        "inflation": 2.7,        # CPI around 2.5-3%
        "unemployment": 4.2,     # Unemployment ~4.2%
        "fed_stance": "easing",  # Fed started cutting Sept 2024
        "gdp_growth": 2.8,       # GDP growth strong ~2.5-3%
        "yield_spread": 20,      # 10Y-2Y spread slightly positive (curve normalizing)
    }

    print("=" * 70)
    print("HISTORICAL ANALOGUES FOR CURRENT CONDITIONS")
    print("=" * 70)
    print()
    print("Current conditions:")
    for key, value in current_conditions.items():
        print(f"  {key}: {value}")
    print()

    # Get summary
    result = get_analogue_summary(current_conditions, top_n=3)

    print("Current fingerprint:")
    for dim, value in result["current_fingerprint"].items():
        print(f"  {dim}: {value}")
    print()

    print("-" * 70)
    print("NARRATIVE:")
    print("-" * 70)
    print()
    print(result["narrative"])
    print()

    print("-" * 70)
    print("RAW ANALOGUES:")
    print("-" * 70)
    for analogue in result["analogues"]:
        print()
        print(f"  {analogue['name']} ({analogue['period']})")
        print(f"    Similarity: {analogue['similarity_pct']}%")
        print(f"    Key difference: {analogue['key_difference']}")
        print(f"    Lesson: {analogue['key_lesson']}")
