"""Generate EconStats Architecture PDF."""

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Colors
BLUE = HexColor("#2563eb")
DARK_BLUE = HexColor("#1e40af")
GREEN = HexColor("#16a34a")
ORANGE = HexColor("#ea580c")
PURPLE = HexColor("#9333ea")
GRAY = HexColor("#6b7280")
LIGHT_GRAY = HexColor("#f3f4f6")
DARK = HexColor("#1f2937")
RED = HexColor("#dc2626")

def draw_box(c, x, y, w, h, title, items=None, color=BLUE, fill=True):
    """Draw a rounded box with title and optional items."""
    # Background
    if fill:
        c.setFillColor(HexColor("#f8fafc"))
        c.roundRect(x, y, w, h, 8, fill=1, stroke=0)

    # Border
    c.setStrokeColor(color)
    c.setLineWidth(2)
    c.roundRect(x, y, w, h, 8, fill=0, stroke=1)

    # Title bar
    c.setFillColor(color)
    c.roundRect(x, y + h - 24, w, 24, 8, fill=1, stroke=0)
    c.rect(x, y + h - 24, w, 12, fill=1, stroke=0)

    # Title text
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x + w/2, y + h - 18, title)

    # Items
    if items:
        c.setFillColor(DARK)
        c.setFont("Helvetica", 8)
        for i, item in enumerate(items):
            c.drawString(x + 8, y + h - 40 - i*12, item)

def draw_arrow(c, x1, y1, x2, y2, color=GRAY):
    """Draw an arrow from (x1,y1) to (x2,y2)."""
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(2)
    c.line(x1, y1, x2, y2)

    # Arrowhead
    import math
    angle = math.atan2(y2-y1, x2-x1)
    arrow_len = 8
    c.line(x2, y2, x2 - arrow_len*math.cos(angle - 0.4), y2 - arrow_len*math.sin(angle - 0.4))
    c.line(x2, y2, x2 - arrow_len*math.cos(angle + 0.4), y2 - arrow_len*math.sin(angle + 0.4))

def create_architecture_pdf(filename):
    """Create the architecture PDF."""
    c = canvas.Canvas(filename, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(DARK)
    c.drawCentredString(width/2, height - 40, "EconStats Architecture")

    c.setFont("Helvetica", 12)
    c.setFillColor(GRAY)
    c.drawCentredString(width/2, height - 58, "Economic Data Query & Visualization System")

    # === ROW 1: User Query ===
    draw_box(c, width/2 - 60, height - 110, 120, 35, "USER QUERY", color=DARK_BLUE)

    # Arrow down
    draw_arrow(c, width/2, height - 110, width/2, height - 130)

    # === ROW 2: Query Preprocessing ===
    preprocess_y = height - 200
    draw_box(c, 50, preprocess_y, 700, 65, "QUERY PREPROCESSING (app.py)", color=BLUE)

    # Sub-boxes for preprocessing
    sub_w = 155
    sub_h = 35
    sub_y = preprocess_y + 8

    c.setFillColor(HexColor("#dbeafe"))
    for i, (title, example) in enumerate([
        ("Temporal Extraction", '"in 2022", "pre-covid"'),
        ("Demographic Extract", '"Black", "Hispanic", "women"'),
        ("Geographic Detection", '"Texas", "California"'),
        ("Synonym Mapping", '"jobs" → "employment"'),
    ]):
        sub_x = 60 + i * 170
        c.roundRect(sub_x, sub_y, sub_w, sub_h, 4, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(sub_x + sub_w/2, sub_y + 22, title)
        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY)
        c.drawCentredString(sub_x + sub_w/2, sub_y + 8, example)
        c.setFillColor(HexColor("#dbeafe"))

    # Arrow down
    draw_arrow(c, width/2, preprocess_y, width/2, preprocess_y - 20)

    # === ROW 3: Smart Query Router ===
    router_y = preprocess_y - 75
    draw_box(c, 200, router_y, 400, 50, "SMART QUERY ROUTER (query_router.py)", color=PURPLE)

    c.setFont("Helvetica", 8)
    c.setFillColor(DARK)
    c.drawString(210, router_y + 25, '"US vs Eurozone" → is_comparison=True → Multi-source')
    c.drawString(210, router_y + 12, '"UK economy" → source=dbnomics → International only')

    # Arrows to three sources
    draw_arrow(c, 300, router_y, 150, router_y - 30)
    draw_arrow(c, 400, router_y, 400, router_y - 30)
    draw_arrow(c, 500, router_y, 650, router_y - 30)

    # === ROW 4: Query Planning Sources ===
    plan_y = router_y - 110

    # Pre-computed plans
    draw_box(c, 30, plan_y, 200, 75, "PRE-COMPUTED PLANS",
             ["plans_employment.json", "plans_inflation.json", "plans_gdp.json",
              "plans_demographics.json", "+ stocks.py, dbnomics.py"], color=GREEN)

    # RAG Catalog
    draw_box(c, 300, plan_y, 200, 75, "RAG CATALOG",
             ["115+ curated FRED series", "TF-IDF semantic search", "series_rag.py"], color=GREEN)

    # FRED API Search
    draw_box(c, 570, plan_y, 200, 75, "FRED API SEARCH",
             ["Dynamic state series", "TXUR, CAUR, etc.", "Fallback for unknowns"], color=GREEN)

    # Arrows down converging
    draw_arrow(c, 130, plan_y, 130, plan_y - 20)
    draw_arrow(c, 400, plan_y, 400, plan_y - 20)
    draw_arrow(c, 670, plan_y, 670, plan_y - 20)

    # Merge line
    c.setStrokeColor(GRAY)
    c.setLineWidth(2)
    c.line(130, plan_y - 20, 670, plan_y - 20)
    draw_arrow(c, 400, plan_y - 20, 400, plan_y - 40)

    # === ROW 5: LLM Validation ===
    llm_y = plan_y - 110
    draw_box(c, 150, llm_y, 500, 65, "LLM ENSEMBLE VALIDATION (agent_ensemble.py)", color=ORANGE)

    # LLM sub-boxes
    c.setFillColor(HexColor("#ffedd5"))
    for i, name in enumerate(["Claude (Opus)", "Gemini (1.5 Pro)", "GPT (4o-mini)"]):
        lx = 180 + i * 150
        c.roundRect(lx, llm_y + 8, 120, 25, 4, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(lx + 60, llm_y + 17, name)
        c.setFillColor(HexColor("#ffedd5"))

    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(160, llm_y + 40, "validate_series_relevance() • validate_presentation() • discover_dimensions()")

    # Arrow down
    draw_arrow(c, 400, llm_y, 400, llm_y - 20)

    # === PAGE 2 ===
    c.showPage()

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(DARK)
    c.drawCentredString(width/2, height - 40, "EconStats Architecture (cont.)")

    # === Data Fetching ===
    fetch_y = height - 140

    # FRED
    draw_box(c, 30, fetch_y, 230, 90, "US DATA (FRED API)", color=BLUE)
    c.setFont("Helvetica", 8)
    c.setFillColor(DARK)
    c.drawString(40, fetch_y + 55, "GDPC1  UNRATE  PAYEMS  CPIAUCSL")
    c.drawString(40, fetch_y + 42, "FEDFUNDS  SP500  T10Y2Y")
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(40, fetch_y + 25, "Transform: Level → YoY % change")
    c.drawString(40, fetch_y + 12, "(for stocks like GDP, CPI)")

    # DBnomics
    draw_box(c, 280, fetch_y, 280, 90, "INTERNATIONAL DATA (DBnomics API)", color=PURPLE)

    providers = [("Eurostat", "EZ GDP/CPI"), ("IMF WEO", "JP/CN/DE"),
                 ("ECB", "ECB Rate"), ("BOE", "UK GDP/CPI")]
    for i, (prov, data) in enumerate(providers):
        px = 295 + i * 65
        c.setFillColor(HexColor("#f3e8ff"))
        c.roundRect(px, fetch_y + 35, 55, 35, 3, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(px + 27, fetch_y + 58, prov)
        c.setFont("Helvetica", 6)
        c.setFillColor(GRAY)
        c.drawCentredString(px + 27, fetch_y + 45, data)

    c.setFont("Helvetica", 7)
    c.setFillColor(GRAY)
    c.drawString(290, fetch_y + 12, "Metadata: measure_type, change_type, frequency")

    # Polymarket
    draw_box(c, 580, fetch_y, 180, 90, "FORWARD-LOOKING (Polymarket)", color=RED)
    c.setFont("Helvetica", 8)
    c.setFillColor(DARK)
    c.drawString(590, fetch_y + 55, "Recession odds")
    c.drawString(590, fetch_y + 42, "Fed rate expectations")
    c.drawString(590, fetch_y + 29, "GDP forecasts")
    c.drawString(590, fetch_y + 16, "Tariff revenue predictions")

    # Arrows down
    draw_arrow(c, 145, fetch_y, 145, fetch_y - 25)
    draw_arrow(c, 420, fetch_y, 420, fetch_y - 25)
    draw_arrow(c, 670, fetch_y, 670, fetch_y - 25)

    # Merge
    c.setStrokeColor(GRAY)
    c.line(145, fetch_y - 25, 670, fetch_y - 25)
    draw_arrow(c, 400, fetch_y - 25, 400, fetch_y - 45)

    # === Presentation Layer ===
    pres_y = fetch_y - 135
    draw_box(c, 100, pres_y, 600, 80, "PRESENTATION LAYER", color=DARK_BLUE)

    # Sub-boxes
    for i, (title, items) in enumerate([
        ("CHARTS (Altair)", ["Line charts", "Multi-series", "Recession bands"]),
        ("AI SUMMARY (LLM)", ["Trend analysis", "Key insights", "Context"]),
        ("POLYMARKET", ["Prediction display", "Probability %", "Market links"])
    ]):
        bx = 120 + i * 190
        c.setFillColor(HexColor("#e0e7ff"))
        c.roundRect(bx, pres_y + 8, 170, 45, 4, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(bx + 85, pres_y + 40, title)
        c.setFont("Helvetica", 7)
        c.setFillColor(GRAY)
        for j, item in enumerate(items):
            c.drawCentredString(bx + 85, pres_y + 27 - j*9, item)

    # Display rules
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(DARK)
    c.drawString(110, pres_y + 60, "Display Rules:")
    c.setFont("Helvetica", 8)
    c.drawString(200, pres_y + 60, "STOCK (GDP) → YoY%  |  FLOW (claims) → Level  |  RATE (unemp) → Level")

    # === Comparison Validation Box ===
    comp_y = pres_y - 120
    draw_box(c, 150, comp_y, 500, 100, "COMPARISON VALIDATION (Critical)", color=RED)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(DARK)
    c.drawCentredString(400, comp_y + 70, "NEVER compare apples to oranges!")

    # US box
    c.setFillColor(HexColor("#fef2f2"))
    c.roundRect(180, comp_y + 15, 140, 45, 4, fill=1, stroke=0)
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(250, comp_y + 48, "US GDP (GDPC1)")
    c.setFont("Helvetica", 8)
    c.drawString(190, comp_y + 35, "measure: real")
    c.drawString(190, comp_y + 23, "change: yoy")
    c.setFillColor(GREEN)
    c.drawString(260, comp_y + 35, "✓")
    c.drawString(255, comp_y + 23, "✓")

    # vs
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(GRAY)
    c.drawCentredString(400, comp_y + 35, "vs")

    # Eurozone box
    c.setFillColor(HexColor("#fef2f2"))
    c.roundRect(480, comp_y + 15, 140, 45, 4, fill=1, stroke=0)
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(550, comp_y + 48, "Eurozone GDP")
    c.setFont("Helvetica", 8)
    c.drawString(490, comp_y + 35, "measure: real")
    c.drawString(490, comp_y + 23, "change: yoy")
    c.setFillColor(GREEN)
    c.drawString(560, comp_y + 35, "✓")
    c.drawString(555, comp_y + 23, "✓")

    # Result
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GREEN)
    c.drawCentredString(400, comp_y + 5, "2.3% vs 1.5% = Valid Comparison ✓")

    # === Key Files ===
    files_y = comp_y - 130
    draw_box(c, 100, files_y, 600, 110, "KEY FILES", color=GRAY)

    files = [
        ("app.py", "Main Streamlit app, query orchestration"),
        ("agents/agent_ensemble.py", "LLM ensemble (Claude + Gemini + GPT)"),
        ("agents/series_rag.py", "115+ curated series with semantic search"),
        ("agents/query_router.py", "Smart routing for comparisons"),
        ("agents/dbnomics.py", "International data (Eurostat, IMF, ECB, BOE)"),
        ("agents/polymarket.py", "Prediction market data"),
        ("agents/plans_*.json", "350+ pre-computed query→series mappings"),
    ]

    c.setFont("Courier", 8)
    for i, (fname, desc) in enumerate(files):
        c.setFillColor(BLUE)
        c.drawString(115, files_y + 75 - i*12, fname)
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 8)
        c.drawString(300, files_y + 75 - i*12, desc)
        c.setFont("Courier", 8)

    c.save()
    print(f"PDF saved to: {filename}")

if __name__ == "__main__":
    output_path = "/Users/josh/Desktop/econstats/EconStats_Architecture.pdf"
    create_architecture_pdf(output_path)
