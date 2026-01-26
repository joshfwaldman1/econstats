"""
Citation and Attribution System for EconStats.

Provides source attribution for economic claims beyond raw data.
Supports expert opinions, competing views, and forecast attribution.

The Problem:
    Economic analysis often goes beyond raw data to include interpretations,
    forecasts, and expert opinions. Without proper attribution:
    - Opinions can be mistaken for facts
    - Forecast sources are unclear
    - Competing expert views are hidden
    - Intellectual dishonesty creeps in

    BAD (unsourced opinion):
        "The Fed will likely cut rates twice in 2026"

    GOOD (attributed):
        "Goldman Sachs expects two rate cuts in 2026, while Morgan Stanley sees only one"

    BAD (asserted as fact):
        "Inflation will continue to moderate"

    GOOD (with competing views):
        "Most forecasters expect inflation to continue moderating, though some
        analysts warn about persistent services inflation"

Key Principles:
    1. Raw data doesn't need citation - "Unemployment is 4.1%" is a fact
    2. Interpretations need attribution - "This suggests cooling" should note who says this
    3. Forecasts always need sources - "Rates will fall" -> "Goldman expects rates to fall"
    4. Competing views are valuable - Show when experts disagree
    5. Tier sources by authority - Fed > Academic > Finance > Press

Usage:
    from core.citations import (
        Citation,
        EXPERT_VIEWS,
        get_expert_views,
        format_with_attribution,
        format_competing_views,
        should_cite,
        add_citations_to_analysis,
        format_citation_footer,
    )

    # Check if a claim needs citation
    if should_cite("forecast"):
        views = get_expert_views("fed_rate_path")
        attributed_text = format_with_attribution(claim, views)

    # Get competing views formatted for display
    competing = format_competing_views("recession_risk")

    # Add a citation footer to analysis
    footer = format_citation_footer(citations_used)
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Citation:
    """
    A citation for a claim about economic conditions or forecasts.

    Attributes:
        source: The organization or individual making the claim
                (e.g., "Goldman Sachs", "Federal Reserve", "BLS")
        claim: What they said (the actual claim or forecast)
        date: When they said it (e.g., "January 2026", "December 2024")
        url: Optional link to the source material
        tier: Source credibility tier (1=Fed/Govt highest, 4=Press lowest)
        category: Optional category like 'forecast', 'opinion', 'research'

    Tier System:
        1 = Federal Reserve and Government (highest authority)
        2 = Academic/Research institutions
        3 = Financial institutions (banks, asset managers)
        4 = Press and media outlets
    """
    source: str
    claim: str
    date: Optional[str] = None
    url: Optional[str] = None
    tier: int = 3
    category: Optional[str] = None

    def __str__(self) -> str:
        """Format citation as a readable string."""
        date_part = f" ({self.date})" if self.date else ""
        return f"{self.source}{date_part}: {self.claim}"

    def as_dict(self) -> Dict[str, Any]:
        """Convert citation to dictionary for JSON serialization."""
        return {
            'source': self.source,
            'claim': self.claim,
            'date': self.date,
            'url': self.url,
            'tier': self.tier,
            'category': self.category,
        }


@dataclass
class ExpertView:
    """
    A single expert's view on an economic topic.

    This is a lighter-weight structure than Citation, used for storing
    expert opinions in the EXPERT_VIEWS database.

    Attributes:
        source: Who holds this view
        view: Their specific position or forecast
        date: When this view was expressed
        tier: Source credibility tier
        rationale: Optional explanation for why they hold this view
    """
    source: str
    view: str
    date: Optional[str] = None
    tier: int = 3
    rationale: Optional[str] = None

    def to_citation(self, topic: str = "") -> Citation:
        """Convert to a full Citation object."""
        return Citation(
            source=self.source,
            claim=self.view,
            date=self.date,
            tier=self.tier,
            category='expert_view',
        )


@dataclass
class TopicViews:
    """
    Collection of expert views on a specific economic topic.

    Attributes:
        topic: The economic topic (e.g., "Federal Reserve rate path")
        views: List of expert views on this topic
        last_updated: When this collection was last updated
        consensus: Optional description of the consensus view
        key_disagreement: Optional description of main points of disagreement
    """
    topic: str
    views: List[ExpertView] = field(default_factory=list)
    last_updated: Optional[str] = None
    consensus: Optional[str] = None
    key_disagreement: Optional[str] = None


# =============================================================================
# SOURCE TIER DEFINITIONS
# =============================================================================

# Tier 1: Federal Reserve and Government (highest authority)
# These sources have primary data and official policy positions
TIER_1_FED_GOVT = {
    'Federal Reserve': 1,
    'Federal Reserve (Dot Plot)': 1,
    'FOMC': 1,
    'Fed Chair Powell': 1,
    'Bureau of Labor Statistics': 1,
    'Bureau of Economic Analysis': 1,
    'Treasury Department': 1,
    'Congressional Budget Office': 1,
    'Cleveland Fed': 1,
    'Atlanta Fed': 1,
    'New York Fed': 1,
    'St. Louis Fed': 1,
    'San Francisco Fed': 1,
    'BLS': 1,
    'BEA': 1,
    'Census Bureau': 1,
}

# Tier 2: Academic and Research institutions
# Credible research with peer review and methodological rigor
TIER_2_ACADEMIC = {
    'National Bureau of Economic Research': 2,
    'NBER': 2,
    'Brookings Institution': 2,
    'Peterson Institute': 2,
    'Conference Board': 2,
    'University of Michigan': 2,
    'MIT': 2,
    'Harvard': 2,
    'Princeton': 2,
    'IMF': 2,
    'World Bank': 2,
    'OECD': 2,
    'Federal Reserve Bank Research': 2,
}

# Tier 3: Financial institutions
# Have skin in the game, motivated to be accurate, but potential conflicts
TIER_3_FINANCE = {
    'Goldman Sachs': 3,
    'Morgan Stanley': 3,
    'JP Morgan': 3,
    'JPMorgan': 3,
    'Bank of America': 3,
    'Citigroup': 3,
    'Wells Fargo': 3,
    'BlackRock': 3,
    'Bridgewater': 3,
    'PIMCO': 3,
    'Vanguard': 3,
    'Deutsche Bank': 3,
    'UBS': 3,
    'Credit Suisse': 3,
    'Barclays': 3,
    'Nomura': 3,
    'CME FedWatch': 3,
    'Polymarket': 3,
}

# Tier 4: Press and media
# Good for news, less reliable for analysis/forecasts
TIER_4_PRESS = {
    'Wall Street Journal': 4,
    'Financial Times': 4,
    'Bloomberg': 4,
    'Reuters': 4,
    'The Economist': 4,
    'CNBC': 4,
    'MarketWatch': 4,
    "Barron's": 4,
    'New York Times': 4,
    'Washington Post': 4,
}

# Combined lookup for tier assignment
ALL_SOURCE_TIERS = {
    **TIER_1_FED_GOVT,
    **TIER_2_ACADEMIC,
    **TIER_3_FINANCE,
    **TIER_4_PRESS,
}


def get_source_tier(source: str) -> int:
    """
    Get the tier for a source, defaulting to 4 if unknown.

    Args:
        source: The source name to look up

    Returns:
        Tier number (1=highest authority, 4=press/unknown)
    """
    # Try exact match first
    if source in ALL_SOURCE_TIERS:
        return ALL_SOURCE_TIERS[source]

    # Try partial match (source name might be part of a longer string)
    source_lower = source.lower()
    for known_source, tier in ALL_SOURCE_TIERS.items():
        if known_source.lower() in source_lower or source_lower in known_source.lower():
            return tier

    return 4  # Default to press tier for unknown sources


def get_tier_label(tier: int) -> str:
    """
    Get a human-readable label for a source tier.

    Args:
        tier: The tier number (1-4)

    Returns:
        Human-readable tier description
    """
    tier_labels = {
        1: 'Official (Fed/Govt)',
        2: 'Research/Academic',
        3: 'Financial Institution',
        4: 'Press/Media',
    }
    return tier_labels.get(tier, 'Unknown')


# =============================================================================
# EXPERT VIEWS DATABASE
# =============================================================================

# Pre-loaded expert views on key economic topics.
# These are updated periodically from news searches and Fed communications.
# The views dictionary maps topic keys to TopicViews objects.

EXPERT_VIEWS: Dict[str, TopicViews] = {
    # =========================================================================
    # MONETARY POLICY
    # =========================================================================
    'fed_rate_path': TopicViews(
        topic='Federal Reserve rate path',
        last_updated='January 2026',
        consensus='Most expect gradual rate cuts through 2026, though pace is debated',
        key_disagreement='Timing and number of cuts in 2026',
        views=[
            ExpertView(
                source='Federal Reserve (Dot Plot)',
                view='Median projection shows rates falling to 3.4% by end of 2026',
                date='December 2024',
                tier=1,
                rationale='Official FOMC projections based on committee median',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='Expects two 25bp rate cuts in 2026, likely in June and December',
                date='January 2026',
                tier=3,
                rationale='Citing sticky services inflation requiring patience',
            ),
            ExpertView(
                source='Morgan Stanley',
                view='Projects cuts in June and September 2026, with risk of delay',
                date='January 2026',
                tier=3,
                rationale='Labor market remains stronger than Fed expected',
            ),
            ExpertView(
                source='JP Morgan',
                view='Sees 75bp of cuts in 2026, quarterly pace',
                date='January 2026',
                tier=3,
                rationale='Inflation progress likely to continue',
            ),
            ExpertView(
                source='CME FedWatch',
                view='Markets pricing in two 25bp cuts by December 2026',
                date='January 2026',
                tier=3,
                rationale='Fed funds futures implied probabilities',
            ),
        ],
    ),

    'fed_terminal_rate': TopicViews(
        topic='Fed terminal/neutral rate',
        last_updated='January 2026',
        consensus='Terminal rate likely between 2.5% and 3.5%',
        key_disagreement='Whether neutral rate has risen post-pandemic',
        views=[
            ExpertView(
                source='Federal Reserve',
                view='Longer-run neutral rate estimate around 2.5-3.0%',
                date='December 2024',
                tier=1,
                rationale='From Summary of Economic Projections',
            ),
            ExpertView(
                source='PIMCO',
                view='Neutral rate may have risen to 3.0-3.5% post-pandemic',
                date='January 2026',
                tier=3,
                rationale='Structural factors like fiscal deficits and deglobalization',
            ),
            ExpertView(
                source='Bridgewater',
                view='Neutral rate could be higher than pre-pandemic at 3.5%+',
                date='January 2026',
                tier=3,
                rationale='Productivity growth and investment demand shifts',
            ),
        ],
    ),

    # =========================================================================
    # INFLATION OUTLOOK
    # =========================================================================
    'inflation_outlook': TopicViews(
        topic='Inflation trajectory',
        last_updated='January 2026',
        consensus='Core inflation expected to gradually decline toward 2% target',
        key_disagreement='Persistence of services inflation',
        views=[
            ExpertView(
                source='Cleveland Fed Inflation Nowcast',
                view='Projects core PCE at 2.6% for coming months',
                date='January 2026',
                tier=1,
                rationale='Real-time inflation tracking model',
            ),
            ExpertView(
                source='Federal Reserve',
                view='Core PCE projected to reach 2.2% by end of 2026',
                date='December 2024',
                tier=1,
                rationale='FOMC Summary of Economic Projections',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='Core PCE to remain sticky around 2.4-2.6% through mid-2026',
                date='January 2026',
                tier=3,
                rationale='Services inflation proving more persistent than expected',
            ),
            ExpertView(
                source='Bank of America',
                view='Risk of re-acceleration if labor market stays tight',
                date='January 2026',
                tier=3,
                rationale='Wage growth remains elevated in services sector',
            ),
            ExpertView(
                source='Peterson Institute',
                view='Shelter inflation should decline as new rent data flows through',
                date='January 2026',
                tier=2,
                rationale='CPI shelter lags market rents by 12-18 months',
            ),
        ],
    ),

    'shelter_inflation': TopicViews(
        topic='Shelter/housing inflation',
        last_updated='January 2026',
        consensus='Shelter inflation expected to decline as market rents flow through',
        key_disagreement='Timing and pace of shelter inflation decline',
        views=[
            ExpertView(
                source='Federal Reserve',
                view='Shelter inflation should moderate as lagged rent data catches up',
                date='December 2024',
                tier=1,
                rationale='Fed Chair Powell commentary on housing inflation',
            ),
            ExpertView(
                source='Zillow',
                view='Market rents have already decelerated to pre-pandemic norms',
                date='January 2026',
                tier=3,
                rationale='Zillow Observed Rent Index shows 3.5% annual growth',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='CPI shelter should drop to 4% by end of 2026 from current 5%+',
                date='January 2026',
                tier=3,
                rationale='Market rent deceleration with 12-month lag to CPI',
            ),
        ],
    ),

    # =========================================================================
    # RECESSION RISK
    # =========================================================================
    'recession_risk': TopicViews(
        topic='Recession probability',
        last_updated='January 2026',
        consensus='Soft landing remains base case, recession risk modest',
        key_disagreement='Whether economy can avoid recession with elevated rates',
        views=[
            ExpertView(
                source='Conference Board LEI',
                view='Leading indicators no longer signaling elevated recession risk',
                date='January 2026',
                tier=2,
                rationale='LEI has stopped declining after prior deterioration',
            ),
            ExpertView(
                source='Polymarket',
                view='Prediction markets show ~15-20% recession probability for 2026',
                date='January 2026',
                tier=3,
                rationale='Aggregated market-based probability estimate',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='12-month recession probability at 15%',
                date='January 2026',
                tier=3,
                rationale='Growth remains resilient despite higher rates',
            ),
            ExpertView(
                source='Morgan Stanley',
                view='20% recession probability, risks tilted to downside',
                date='January 2026',
                tier=3,
                rationale='Consumer spending showing signs of fatigue',
            ),
            ExpertView(
                source='NBER',
                view='No recession declared as of late 2025; economy expanding',
                date='December 2025',
                tier=2,
                rationale='Official business cycle dating committee',
            ),
        ],
    ),

    'soft_landing': TopicViews(
        topic='Soft landing scenario',
        last_updated='January 2026',
        consensus='Soft landing increasingly likely but not guaranteed',
        key_disagreement='Sustainability of current labor market strength',
        views=[
            ExpertView(
                source='Federal Reserve',
                view='Balanced approach to achieving soft landing; no rush to cut',
                date='December 2024',
                tier=1,
                rationale='Powell press conference remarks',
            ),
            ExpertView(
                source='JP Morgan',
                view='Soft landing base case with 60% probability',
                date='January 2026',
                tier=3,
                rationale='Inflation declining while employment holds up',
            ),
            ExpertView(
                source='Bridgewater',
                view='Soft landing achievable but narrow path; risks both ways',
                date='January 2026',
                tier=3,
                rationale='Balanced upside and downside scenarios',
            ),
        ],
    ),

    # =========================================================================
    # LABOR MARKET
    # =========================================================================
    'labor_market_outlook': TopicViews(
        topic='Labor market trajectory',
        last_updated='January 2026',
        consensus='Labor market gradually cooling but remains healthy',
        key_disagreement='Whether cooling is orderly or accelerating',
        views=[
            ExpertView(
                source='Federal Reserve',
                view='Labor market in better balance; unemployment to rise modestly to 4.3%',
                date='December 2024',
                tier=1,
                rationale='FOMC Summary of Economic Projections',
            ),
            ExpertView(
                source='BLS',
                view='Job gains averaging 150-200K per month; unemployment stable at 4.1%',
                date='January 2026',
                tier=1,
                rationale='Official employment statistics',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='Labor market cooling will continue but no spike in unemployment',
                date='January 2026',
                tier=3,
                rationale='Job openings declining, quits rate normalizing',
            ),
            ExpertView(
                source='Bank of America',
                view='Risk of faster labor market weakening if spending slows',
                date='January 2026',
                tier=3,
                rationale='Initial claims trending higher',
            ),
        ],
    ),

    'wage_growth': TopicViews(
        topic='Wage growth outlook',
        last_updated='January 2026',
        consensus='Wage growth moderating toward sustainable levels',
        key_disagreement='Whether current pace is still inflationary',
        views=[
            ExpertView(
                source='Atlanta Fed Wage Tracker',
                view='Median wage growth at 4.5%, down from 6%+ peak',
                date='January 2026',
                tier=1,
                rationale='Official wage tracking from Fed district',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='Wage growth needs to fall to 3.5% to be consistent with 2% inflation',
                date='January 2026',
                tier=3,
                rationale='Based on productivity growth assumptions',
            ),
            ExpertView(
                source='Peterson Institute',
                view='Current wage growth may be sustainable if productivity improves',
                date='January 2026',
                tier=2,
                rationale='Recent productivity gains creating room for higher wages',
            ),
        ],
    ),

    # =========================================================================
    # GDP AND GROWTH
    # =========================================================================
    'gdp_outlook': TopicViews(
        topic='GDP growth outlook',
        last_updated='January 2026',
        consensus='Growth expected to moderate to trend pace of ~2%',
        key_disagreement='Consumer spending sustainability',
        views=[
            ExpertView(
                source='Federal Reserve',
                view='GDP growth projected at 2.0% for 2026',
                date='December 2024',
                tier=1,
                rationale='FOMC Summary of Economic Projections',
            ),
            ExpertView(
                source='Atlanta Fed GDPNow',
                view='Real-time tracking model shows current quarter growth at ~2.5%',
                date='January 2026',
                tier=1,
                rationale='Nowcast model incorporating latest data',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='GDP growth of 2.3% for 2026, above consensus',
                date='January 2026',
                tier=3,
                rationale='Consumer and investment spending remain solid',
            ),
            ExpertView(
                source='Morgan Stanley',
                view='GDP growth of 1.8% for 2026, risks to downside',
                date='January 2026',
                tier=3,
                rationale='Consumer spending expected to slow as savings deplete',
            ),
        ],
    ),

    # =========================================================================
    # HOUSING MARKET
    # =========================================================================
    'housing_outlook': TopicViews(
        topic='Housing market outlook',
        last_updated='January 2026',
        consensus='Housing activity constrained by high rates; prices resilient',
        key_disagreement='Whether prices will decline or plateau',
        views=[
            ExpertView(
                source='National Association of Realtors',
                view='Home sales to remain weak until mortgage rates decline',
                date='January 2026',
                tier=3,
                rationale='Existing home sales near multi-decade lows',
            ),
            ExpertView(
                source='Zillow',
                view='Home prices up 3-4% year-over-year; supply constraints supporting prices',
                date='January 2026',
                tier=3,
                rationale='Zillow Home Value Index tracking',
            ),
            ExpertView(
                source='Goldman Sachs',
                view='Home prices to rise 3% in 2026 despite high rates',
                date='January 2026',
                tier=3,
                rationale='Low inventory keeping prices elevated',
            ),
            ExpertView(
                source='Moody\'s',
                view='Some markets overvalued by 20%+; correction risk if rates stay high',
                date='January 2026',
                tier=3,
                rationale='Affordability at worst levels since 1980s',
            ),
        ],
    ),

    # =========================================================================
    # FINANCIAL CONDITIONS
    # =========================================================================
    'financial_conditions': TopicViews(
        topic='Financial conditions',
        last_updated='January 2026',
        consensus='Financial conditions have eased despite Fed holding rates',
        key_disagreement='Whether easing conditions undermine Fed policy',
        views=[
            ExpertView(
                source='Chicago Fed NFCI',
                view='Financial conditions loosening, now in accommodative territory',
                date='January 2026',
                tier=1,
                rationale='National Financial Conditions Index tracking',
            ),
            ExpertView(
                source='Goldman Sachs FCI',
                view='Financial conditions eased significantly in late 2025',
                date='January 2026',
                tier=3,
                rationale='Stock gains and credit spread tightening',
            ),
            ExpertView(
                source='Federal Reserve',
                view='Some concern about easing conditions offsetting policy stance',
                date='December 2024',
                tier=1,
                rationale='FOMC minutes discussion',
            ),
        ],
    ),
}


# =============================================================================
# CLAIM TYPE DETECTION
# =============================================================================

# Keywords indicating different types of claims that need citation
FORECAST_KEYWORDS = [
    'forecast', 'prediction', 'expect', 'project', 'anticipate',
    'outlook', 'estimate for', 'will be', 'will likely', 'will probably',
    'going forward', 'by end of', 'by year-end', 'next year',
    'will cut', 'will raise', 'will hike', 'will hold', 'will pause',
    'will fall', 'will rise', 'will increase', 'will decrease',
    'will continue', 'will remain', 'will stay', 'will moderate',
]

OPINION_KEYWORDS = [
    'interpretation', 'opinion', 'view', 'assessment', 'belief',
    'argues', 'contends', 'believes', 'thinks', 'suggests',
    'indicates', 'implies', 'signals',
]

PROBABILITY_KEYWORDS = [
    'likely', 'probably', 'expected to', 'may', 'could', 'might',
    'should', 'appears to', 'seems to', 'looks like',
    'odds of', 'probability', 'chance of', 'risk of',
]

COMPARISON_KEYWORDS = [
    'compared to consensus', 'relative to expectations', 'versus forecasts',
    'better than expected', 'worse than expected', 'ahead of estimates',
    'behind expectations', 'surprised to the',
]

# Claims that do NOT need citation (factual statements)
NO_CITATION_KEYWORDS = [
    'is', 'was', 'stands at', 'came in at', 'reported', 'released',
    'rose to', 'fell to', 'increased to', 'decreased to',
    'the data shows', 'according to BLS', 'according to BEA',
]


def should_cite(claim_type: str = '', claim_text: str = '') -> bool:
    """
    Determine if a claim type or text needs citation.

    This function analyzes either a claim type label or the actual claim text
    to determine if it should be attributed to a source.

    Needs citation:
        - Forecasts and predictions
        - Opinions and interpretations
        - Probabilistic statements
        - Comparisons to consensus

    No citation needed:
        - Raw data values
        - Simple math/calculations
        - Definitions
        - Official statistics cited with source

    Args:
        claim_type: A label for the type of claim (e.g., 'forecast', 'opinion')
        claim_text: The actual text of the claim to analyze

    Returns:
        True if the claim should be cited, False otherwise.

    Examples:
        >>> should_cite(claim_type='forecast')
        True
        >>> should_cite(claim_text='The Fed will likely cut rates twice')
        True
        >>> should_cite(claim_text='Unemployment is 4.1%')
        False
    """
    # Check claim type
    claim_type_lower = claim_type.lower()
    if any(keyword in claim_type_lower for keyword in FORECAST_KEYWORDS):
        return True
    if any(keyword in claim_type_lower for keyword in OPINION_KEYWORDS):
        return True

    # Check claim text
    claim_text_lower = claim_text.lower()

    # Check for forecast keywords
    if any(keyword in claim_text_lower for keyword in FORECAST_KEYWORDS):
        return True

    # Check for opinion keywords
    if any(keyword in claim_text_lower for keyword in OPINION_KEYWORDS):
        return True

    # Check for probability keywords
    if any(keyword in claim_text_lower for keyword in PROBABILITY_KEYWORDS):
        return True

    # Check for comparison keywords
    if any(keyword in claim_text_lower for keyword in COMPARISON_KEYWORDS):
        return True

    return False


def detect_claim_type(text: str) -> str:
    """
    Detect what type of claim a piece of text represents.

    Args:
        text: The text to analyze

    Returns:
        Claim type string: 'forecast', 'opinion', 'probability',
        'comparison', or 'factual'
    """
    text_lower = text.lower()

    if any(keyword in text_lower for keyword in FORECAST_KEYWORDS):
        return 'forecast'

    if any(keyword in text_lower for keyword in OPINION_KEYWORDS):
        return 'opinion'

    if any(keyword in text_lower for keyword in PROBABILITY_KEYWORDS):
        return 'probability'

    if any(keyword in text_lower for keyword in COMPARISON_KEYWORDS):
        return 'comparison'

    return 'factual'


# =============================================================================
# EXPERT VIEW RETRIEVAL
# =============================================================================

def get_expert_views(topic: str) -> List[ExpertView]:
    """
    Get expert views on a topic for citation.

    This function looks up pre-loaded expert views on economic topics.
    Views are sorted by tier (highest authority first).

    Args:
        topic: The topic key (e.g., 'fed_rate_path', 'inflation_outlook')

    Returns:
        List of ExpertView objects, sorted by tier (highest first)

    Example:
        >>> views = get_expert_views('fed_rate_path')
        >>> for v in views[:3]:
        ...     print(f"{v.source}: {v.view}")
        Federal Reserve (Dot Plot): Median projection shows rates falling to 3.4%...
        Goldman Sachs: Expects two 25bp rate cuts in 2026...
    """
    if topic not in EXPERT_VIEWS:
        return []

    topic_views = EXPERT_VIEWS[topic]
    # Sort by tier (lowest tier number = highest authority)
    return sorted(topic_views.views, key=lambda v: v.tier)


def get_topic_consensus(topic: str) -> Optional[str]:
    """
    Get the consensus view on a topic, if available.

    Args:
        topic: The topic key

    Returns:
        Consensus description or None if not available
    """
    if topic not in EXPERT_VIEWS:
        return None
    return EXPERT_VIEWS[topic].consensus


def get_topic_disagreement(topic: str) -> Optional[str]:
    """
    Get the key point of disagreement on a topic, if available.

    Args:
        topic: The topic key

    Returns:
        Key disagreement description or None if not available
    """
    if topic not in EXPERT_VIEWS:
        return None
    return EXPERT_VIEWS[topic].key_disagreement


def list_available_topics() -> List[str]:
    """
    List all topics with available expert views.

    Returns:
        List of topic keys
    """
    return list(EXPERT_VIEWS.keys())


def find_topic_for_query(query: str) -> Optional[str]:
    """
    Find the most relevant topic for a user query.

    Args:
        query: The user's query text

    Returns:
        Most relevant topic key, or None if no match
    """
    query_lower = query.lower()

    # Topic keyword mappings
    topic_keywords = {
        'fed_rate_path': [
            'fed rate', 'rate cut', 'rate hike', 'fed funds', 'fomc', 'rate path',
            'interest rate', 'federal reserve', 'the fed', 'what will the fed',
            'fed do', 'fed going to', 'monetary policy', 'powell',
        ],
        'fed_terminal_rate': ['terminal rate', 'neutral rate', 'long-run rate', 'r-star'],
        'inflation_outlook': ['inflation', 'cpi', 'pce', 'prices', 'price level'],
        'shelter_inflation': ['shelter', 'rent inflation', 'housing cost', 'housing inflation'],
        'recession_risk': ['recession', 'downturn', 'economic contraction', 'is a recession'],
        'soft_landing': ['soft landing', 'hard landing', 'avoid recession'],
        'labor_market_outlook': [
            'labor market', 'jobs', 'employment', 'unemployment', 'hiring',
            'job market', 'layoffs', 'workforce',
        ],
        'wage_growth': ['wage', 'earnings', 'pay', 'compensation', 'salary'],
        'gdp_outlook': ['gdp', 'economic growth', 'expansion', 'output growth'],
        'housing_outlook': ['housing', 'home prices', 'real estate', 'mortgage', 'home values'],
        'financial_conditions': ['financial conditions', 'credit', 'lending', 'credit spreads'],
    }

    for topic, keywords in topic_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return topic

    return None


# =============================================================================
# FORMATTING FUNCTIONS
# =============================================================================

def format_with_attribution(
    claim: str,
    sources: List[Citation],
    include_dates: bool = True,
) -> str:
    """
    Format a claim with proper attribution.

    This transforms an unsourced claim into an attributed statement
    that cites the relevant sources.

    Args:
        claim: The claim to attribute (e.g., "Rate cuts expected in 2026")
        sources: List of Citation objects supporting the claim
        include_dates: Whether to include dates in the attribution

    Returns:
        Attributed version of the claim

    Examples:
        Input:  "Rate cuts expected in 2026"
        Output: "Goldman Sachs and Morgan Stanley both expect rate cuts in 2026,
                though timing differs (GS: Q1, MS: June/Sept)"

        Input:  "Inflation will moderate"
        Output: "The Federal Reserve projects inflation will moderate to 2.2%
                by end of 2026, a view broadly shared by major forecasters"
    """
    if not sources:
        return claim

    # Sort by tier (highest authority first)
    sorted_sources = sorted(sources, key=lambda s: s.tier)

    if len(sorted_sources) == 1:
        # Single source: simple attribution
        source = sorted_sources[0]
        date_part = f" ({source.date})" if include_dates and source.date else ""
        return f"{source.source}{date_part} {claim.lower()}"

    # Multiple sources: show agreement/disagreement
    tier_1_sources = [s for s in sorted_sources if s.tier == 1]
    other_sources = [s for s in sorted_sources if s.tier > 1]

    if tier_1_sources:
        # Lead with official source
        lead = tier_1_sources[0]
        lead_date = f" ({lead.date})" if include_dates and lead.date else ""

        if other_sources:
            others_text = ', '.join([s.source for s in other_sources[:2]])
            return f"{lead.source}{lead_date} {claim.lower()}, a view supported by {others_text}"
        else:
            return f"{lead.source}{lead_date} {claim.lower()}"

    # No official source, multiple private sources
    source_names = [s.source for s in sorted_sources[:3]]
    if len(source_names) == 2:
        names_text = f"{source_names[0]} and {source_names[1]}"
    else:
        names_text = f"{', '.join(source_names[:-1])}, and {source_names[-1]}"

    return f"{names_text} {claim.lower()}"


def format_competing_views(
    topic: str,
    max_views: int = 4,
    include_rationale: bool = False,
) -> str:
    """
    Format competing expert views on a topic.

    This creates a balanced presentation of different expert opinions,
    highlighting where there is agreement and disagreement.

    Args:
        topic: The topic key (e.g., 'fed_rate_path')
        max_views: Maximum number of views to include
        include_rationale: Whether to include the reasoning behind each view

    Returns:
        Formatted text showing competing views

    Example:
        Output: "Views on the Fed's rate path vary: the dot plot suggests
                four cuts by end-2026, while Goldman expects only two,
                citing persistent inflation concerns."
    """
    if topic not in EXPERT_VIEWS:
        return f"No expert views available for topic: {topic}"

    topic_data = EXPERT_VIEWS[topic]
    views = sorted(topic_data.views, key=lambda v: v.tier)[:max_views]

    if not views:
        return f"No expert views available for topic: {topic}"

    # Build narrative
    parts = []

    # Add consensus if available
    if topic_data.consensus:
        parts.append(f"Consensus view: {topic_data.consensus}.")

    # Add key disagreement if available
    if topic_data.key_disagreement:
        parts.append(f"Key debate: {topic_data.key_disagreement}.")

    # Add individual views
    parts.append("")
    parts.append("Expert views:")

    for view in views:
        tier_label = get_tier_label(view.tier)
        date_part = f" ({view.date})" if view.date else ""
        view_text = f"- {view.source}{date_part} [{tier_label}]: {view.view}"

        if include_rationale and view.rationale:
            view_text += f" (Rationale: {view.rationale})"

        parts.append(view_text)

    return '\n'.join(parts)


def format_single_view(view: ExpertView, include_tier: bool = True) -> str:
    """
    Format a single expert view for display.

    Args:
        view: The ExpertView to format
        include_tier: Whether to include the tier label

    Returns:
        Formatted string
    """
    tier_part = f" [{get_tier_label(view.tier)}]" if include_tier else ""
    date_part = f" ({view.date})" if view.date else ""
    return f"{view.source}{date_part}{tier_part}: {view.view}"


def format_citation_footer(
    citations_used: List[Citation],
    include_urls: bool = True,
) -> str:
    """
    Format a footer with all sources cited.

    This creates a proper source attribution section for the end of an analysis,
    sorted by tier (most authoritative first).

    Args:
        citations_used: List of Citation objects used in the analysis
        include_urls: Whether to include URLs when available

    Returns:
        Formatted footer text

    Example:
        Output:
        ---
        Sources:
        - Federal Reserve Dot Plot (December 2024)
        - Goldman Sachs Research (January 2026)
        - Morgan Stanley Economics (January 2026)
    """
    if not citations_used:
        return ""

    # Deduplicate by source name
    seen_sources = set()
    unique_citations = []
    for citation in citations_used:
        if citation.source not in seen_sources:
            seen_sources.add(citation.source)
            unique_citations.append(citation)

    # Sort by tier
    sorted_citations = sorted(unique_citations, key=lambda c: c.tier)

    lines = ["---", "Sources:"]

    for citation in sorted_citations:
        date_part = f" ({citation.date})" if citation.date else ""
        line = f"- {citation.source}{date_part}"

        if include_urls and citation.url:
            line += f" - {citation.url}"

        lines.append(line)

    return '\n'.join(lines)


def format_inline_citation(citation: Citation) -> str:
    """
    Format a citation for inline use in text.

    Args:
        citation: The Citation to format

    Returns:
        Inline citation text (e.g., "(Goldman Sachs, Jan 2026)")
    """
    date_part = f", {citation.date}" if citation.date else ""
    return f"({citation.source}{date_part})"


# =============================================================================
# ANALYSIS ENHANCEMENT
# =============================================================================

def add_citations_to_analysis(
    analysis_text: str,
    available_topics: Optional[List[str]] = None,
) -> Tuple[str, List[Citation]]:
    """
    Enhance analysis text with appropriate citations.

    This function scans the analysis for claims that need attribution
    and adds source references where appropriate. It also returns a list
    of citations used for creating a footer.

    Args:
        analysis_text: The analysis text to enhance
        available_topics: Topics to check for relevant views (defaults to all)

    Returns:
        Tuple of (enhanced_text, citations_used)
    """
    if available_topics is None:
        available_topics = list(EXPERT_VIEWS.keys())

    citations_used: List[Citation] = []
    enhanced_text = analysis_text

    # Find sentences that need citation
    sentences = re.split(r'(?<=[.!?])\s+', analysis_text)
    enhanced_sentences = []

    for sentence in sentences:
        if not sentence.strip():
            enhanced_sentences.append(sentence)
            continue

        # Check if this sentence needs citation
        if should_cite(claim_text=sentence):
            # Find relevant topic
            relevant_topic = None
            for topic in available_topics:
                if _sentence_matches_topic(sentence, topic):
                    relevant_topic = topic
                    break

            if relevant_topic:
                views = get_expert_views(relevant_topic)
                if views:
                    # Add inline attribution
                    top_view = views[0]  # Highest tier
                    citation = top_view.to_citation(relevant_topic)
                    citations_used.append(citation)

                    # Add attribution if not already present
                    source_lower = top_view.source.lower()
                    if source_lower not in sentence.lower():
                        inline_cite = format_inline_citation(citation)
                        enhanced_sentences.append(f"{sentence.rstrip('.')} {inline_cite}.")
                    else:
                        enhanced_sentences.append(sentence)
                else:
                    enhanced_sentences.append(sentence)
            else:
                enhanced_sentences.append(sentence)
        else:
            enhanced_sentences.append(sentence)

    enhanced_text = ' '.join(enhanced_sentences)
    return enhanced_text, citations_used


def _sentence_matches_topic(sentence: str, topic: str) -> bool:
    """Check if a sentence is related to a topic."""
    sentence_lower = sentence.lower()
    topic_lower = topic.lower()

    # Topic keyword mappings (simplified)
    topic_keywords = {
        'fed_rate_path': ['rate cut', 'rate hike', 'fed rate', 'rate path'],
        'inflation_outlook': ['inflation', 'cpi', 'pce', 'prices'],
        'recession_risk': ['recession', 'downturn'],
        'labor_market_outlook': ['unemployment', 'jobs', 'labor'],
        'gdp_outlook': ['gdp', 'growth'],
        'housing_outlook': ['housing', 'home prices'],
    }

    keywords = topic_keywords.get(topic, [topic.replace('_', ' ')])
    return any(keyword in sentence_lower for keyword in keywords)


# =============================================================================
# FRESH VIEW FETCHING (INTEGRATION WITH news_context.py)
# =============================================================================

def fetch_fresh_views(topic: str) -> List[ExpertView]:
    """
    Fetch fresh expert views using news_context.py search.

    This updates expert views with current information from trusted news sources.
    Falls back to cached views if search fails.

    Args:
        topic: The topic to search for (e.g., 'fed_rate_path')

    Returns:
        List of ExpertView objects from recent news

    Note:
        Requires news_context.py and SERPAPI_KEY environment variable.
    """
    try:
        from core.news_context import search_news, get_source_tier as news_tier
    except ImportError:
        # news_context not available, return cached views
        return get_expert_views(topic)

    # Map topic to search query
    topic_queries = {
        'fed_rate_path': 'Federal Reserve rate path forecast 2026',
        'inflation_outlook': 'inflation forecast outlook 2026',
        'recession_risk': 'recession probability forecast 2026',
        'labor_market_outlook': 'labor market employment outlook 2026',
        'gdp_outlook': 'GDP growth forecast 2026',
        'housing_outlook': 'housing market forecast 2026',
    }

    query = topic_queries.get(topic, f'{topic.replace("_", " ")} forecast')

    try:
        results = search_news(query, num_results=5)

        fresh_views = []
        for result in results:
            # Convert search result to ExpertView
            view = ExpertView(
                source=result.get('source', 'Unknown'),
                view=result.get('snippet', '')[:200],  # Truncate long snippets
                date=result.get('date'),
                tier=result.get('tier', 4),
            )
            fresh_views.append(view)

        return fresh_views

    except Exception as e:
        # Search failed, return cached views
        print(f"[Citations] Fresh view fetch failed for {topic}: {e}")
        return get_expert_views(topic)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_view_for_topic_and_source(topic: str, source: str) -> Optional[ExpertView]:
    """
    Get a specific source's view on a topic.

    Args:
        topic: The topic key
        source: The source name to look for

    Returns:
        The ExpertView if found, None otherwise
    """
    views = get_expert_views(topic)
    source_lower = source.lower()

    for view in views:
        if source_lower in view.source.lower():
            return view

    return None


def get_official_view(topic: str) -> Optional[ExpertView]:
    """
    Get the official (Tier 1) view on a topic.

    Args:
        topic: The topic key

    Returns:
        The highest-authority ExpertView if available
    """
    views = get_expert_views(topic)

    for view in views:
        if view.tier == 1:
            return view

    return None


def get_wall_street_consensus(topic: str) -> Optional[str]:
    """
    Get a summary of Wall Street (Tier 3) views on a topic.

    Args:
        topic: The topic key

    Returns:
        Summary text of financial institution views
    """
    views = get_expert_views(topic)
    tier_3_views = [v for v in views if v.tier == 3]

    if not tier_3_views:
        return None

    sources = [v.source for v in tier_3_views]
    if len(sources) == 1:
        return f"{sources[0]}: {tier_3_views[0].view}"

    # Summarize multiple views
    source_list = ', '.join(sources)
    return f"Major forecasters ({source_list}) broadly expect similar outcomes, with some variation in timing."


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CITATION AND ATTRIBUTION SYSTEM - TESTS")
    print("=" * 70)

    # Test 1: Check if claims need citation
    print("\n1. CLAIM TYPE DETECTION")
    print("-" * 40)

    test_claims = [
        "Unemployment is 4.1%",
        "The Fed will likely cut rates twice in 2026",
        "Inflation will continue to moderate",
        "GDP grew 2.5% in Q3",
        "Most forecasters expect inflation to decline",
        "This suggests labor market cooling",
    ]

    for claim in test_claims:
        needs_cite = should_cite(claim_text=claim)
        claim_type = detect_claim_type(claim)
        status = "NEEDS CITATION" if needs_cite else "OK (factual)"
        print(f"  [{status}] ({claim_type}): {claim}")

    # Test 2: Get expert views
    print("\n\n2. EXPERT VIEWS RETRIEVAL")
    print("-" * 40)

    for topic in ['fed_rate_path', 'inflation_outlook', 'recession_risk']:
        print(f"\nTopic: {topic}")
        views = get_expert_views(topic)
        for v in views[:3]:
            print(f"  - {format_single_view(v)}")

    # Test 3: Format competing views
    print("\n\n3. COMPETING VIEWS FORMAT")
    print("-" * 40)

    print(format_competing_views('fed_rate_path', max_views=4))

    # Test 4: Format with attribution
    print("\n\n4. ATTRIBUTION FORMATTING")
    print("-" * 40)

    citations = [
        Citation(source='Goldman Sachs', claim='expects two rate cuts', date='January 2026', tier=3),
        Citation(source='Morgan Stanley', claim='sees cuts in June and September', date='January 2026', tier=3),
        Citation(source='Federal Reserve', claim='dot plot suggests four cuts', date='December 2024', tier=1),
    ]

    claim = "Rate cuts expected in 2026"
    attributed = format_with_attribution(claim, citations)
    print(f"Original: {claim}")
    print(f"Attributed: {attributed}")

    # Test 5: Citation footer
    print("\n\n5. CITATION FOOTER")
    print("-" * 40)

    footer = format_citation_footer(citations)
    print(footer)

    # Test 6: Topic finding
    print("\n\n6. TOPIC FINDING FOR QUERIES")
    print("-" * 40)

    test_queries = [
        "What is the Fed going to do with rates?",
        "Is a recession coming?",
        "How will inflation evolve?",
        "What's the labor market outlook?",
    ]

    for query in test_queries:
        topic = find_topic_for_query(query)
        print(f"  Query: '{query}'")
        print(f"  Matched topic: {topic}")
        print()

    # Test 7: Get official view
    print("\n7. OFFICIAL VIEWS")
    print("-" * 40)

    for topic in ['fed_rate_path', 'inflation_outlook']:
        official = get_official_view(topic)
        if official:
            print(f"  {topic}: {official.source} - {official.view}")
        else:
            print(f"  {topic}: No official view available")

    # Test 8: Tier detection
    print("\n\n8. SOURCE TIER DETECTION")
    print("-" * 40)

    test_sources = [
        'Federal Reserve',
        'Goldman Sachs',
        'Wall Street Journal',
        'NBER',
        'Random Blog',
    ]

    for source in test_sources:
        tier = get_source_tier(source)
        label = get_tier_label(tier)
        print(f"  {source}: Tier {tier} ({label})")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
