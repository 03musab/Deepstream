import os
import sys
import time
import shutil
import http.server
import socketserver
import threading
from PIL import Image as PILImage, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

ARTIFACT_DIR = r"C:\Users\musab\.gemini\antigravity-ide\brain\582f9e5f-9adf-4c77-9a9c-518f6bc67c84"
DOCS_DIR = r"c:\Users\musab\Desktop\Deepstream\docs"
SCREENSHOTS_DIR = r"c:\Users\musab\Desktop\Deepstream\plots\video_screenshots"

os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# ---------------------------------------------------------
# STEP 1: CAPTURE SCREENSHOTS & TELEGRAM PLACEHOLDER
# ---------------------------------------------------------

# Create Telegram Placeholder Image
def create_telegram_placeholder():
    w, h = 1280, 720
    img = PILImage.new('RGB', (w, h), color='#0f172a')
    draw = ImageDraw.Draw(img)

    # Frame & Grid
    draw.rectangle([20, 20, w-20, h-20], outline='#0284c7', width=4)
    draw.rectangle([30, 30, w-30, h-30], outline='#334155', width=1)

    # Top Header
    draw.rectangle([20, 20, w-20, 100], fill='#1e293b')
    draw.text((60, 48), "TELEGRAM PRO SIGNAL DELIVERY — CUSTOM USER IMAGE PLACEHOLDER", fill='#38bdf8')

    # Main Card Area
    draw.rectangle([100, 140, w-100, h-80], outline='#38bdf8', fill='#1e293b', width=2)

    # Text instructions
    draw.text((140, 190), "📸 PLACE YOUR TELEGRAM SCREENSHOT HERE", fill='#f8fafc')
    draw.text((140, 250), "1. Open Telegram Desktop or Telegram Mobile App.", fill='#cbd5e1')
    draw.text((140, 290), "2. Capture your @DeepstreamPro channel alert with trade parameters (Entry / Stop / Target).", fill='#cbd5e1')
    draw.text((140, 330), "3. Capture the single-use invite link or subscriber notification message.", fill='#cbd5e1')
    draw.text((140, 370), "4. Crop/Overlay this image into your video editor (Screen Studio / CapCut / Premiere).", fill='#cbd5e1')

    draw.rectangle([140, 430, w-140, 540], fill='#0f172a', outline='#0284c7', width=1)
    draw.text((170, 460), "[ USER DIRECTIVE ENFORCED: Telegram photo slot kept blank/placeholder for manual inclusion ]", fill='#38bdf8')

    path = os.path.join(SCREENSHOTS_DIR, "scene5_telegram_placeholder.png")
    img.save(path)
    print("Telegram placeholder generated at:", path)
    return path

create_telegram_placeholder()

PORT = 8095
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='signal_site', **kwargs)
    def log_message(self, format, *args):
        pass

def capture_ui_screenshots():
    httpd = socketserver.TCPServer(('', PORT), QuietHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(1)

    print("Launching Edge browser for UI screenshots...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.goto(f'http://localhost:{PORT}/index.html')
        time.sleep(2)

        # 1. Hero
        page.evaluate('window.scrollTo(0, 0)')
        time.sleep(0.5)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, 'scene1_hero.png'))
        print("Captured Scene 1: Hero")

        # 2. Signals Table
        page.locator('#signals').scroll_into_view_if_needed()
        time.sleep(0.8)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, 'scene2_signals.png'))
        print("Captured Scene 2: Signals Table")

        # 3. Track Record & Performance
        page.locator('#performance').scroll_into_view_if_needed()
        time.sleep(0.8)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, 'scene3_trackrecord.png'))
        print("Captured Scene 3: Track Record")

        # 4. Econometric Proof Table
        page.locator('#compare').scroll_into_view_if_needed()
        time.sleep(0.8)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, 'scene4_proof.png'))
        print("Captured Scene 4: Proof Table")

        # 6. Pricing Section
        page.locator('#pricing').scroll_into_view_if_needed()
        time.sleep(0.8)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, 'scene6_pricing.png'))
        print("Captured Scene 6: Pricing")

        # 7. Checkout Modal
        page.evaluate('document.getElementById("checkout-modal").classList.add("open")')
        time.sleep(0.8)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, 'scene6_checkout_modal.png'))
        print("Captured Scene 6: Checkout Modal")

        browser.close()
    httpd.shutdown()

capture_ui_screenshots()

# ---------------------------------------------------------
# STEP 2: BUILD MASTER PDF DOCUMENT WITH PROMPTS & SCREENSHOTS
# ---------------------------------------------------------

pdf_filename = "deepstream_saas_video_prompts_guide.pdf"
pdf_docs_path = os.path.join(DOCS_DIR, pdf_filename)
pdf_artifact_path = os.path.join(ARTIFACT_DIR, pdf_filename)

doc = SimpleDocTemplate(
    pdf_docs_path,
    pagesize=letter,
    rightMargin=36,
    leftMargin=36,
    topMargin=36,
    bottomMargin=36
)

styles = getSampleStyleSheet()

# Typography Styles
title_style = ParagraphStyle(
    'DocTitle',
    parent=styles['Heading1'],
    fontName='Helvetica-Bold',
    fontSize=22,
    leading=26,
    textColor=colors.HexColor('#0f172a'),
    spaceAfter=4
)

subtitle_style = ParagraphStyle(
    'DocSubtitle',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=10,
    leading=14,
    textColor=colors.HexColor('#0284c7'),
    spaceAfter=12
)

h1_style = ParagraphStyle(
    'SectionH1',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=14,
    leading=18,
    textColor=colors.HexColor('#0f172a'),
    spaceBefore=14,
    spaceAfter=6
)

h2_style = ParagraphStyle(
    'SectionH2',
    parent=styles['Heading3'],
    fontName='Helvetica-Bold',
    fontSize=11,
    leading=15,
    textColor=colors.HexColor('#0284c7'),
    spaceBefore=10,
    spaceAfter=4
)

body_style = ParagraphStyle(
    'BodyDark',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    leading=13,
    textColor=colors.HexColor('#334155'),
    spaceAfter=6
)

bullet_style = ParagraphStyle(
    'BulletText',
    parent=body_style,
    leftIndent=12,
    bulletIndent=4,
    spaceAfter=3
)

prompt_box_style = ParagraphStyle(
    'PromptCode',
    parent=styles['Normal'],
    fontName='Courier',
    fontSize=8.5,
    leading=11,
    textColor=colors.HexColor('#0f172a'),
    backColor=colors.HexColor('#f1f5f9'),
    borderColor=colors.HexColor('#cbd5e1'),
    borderWidth=0.5,
    borderPadding=6,
    spaceBefore=4,
    spaceAfter=8
)

table_header_style = ParagraphStyle(
    'TableHeader',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=9,
    leading=11,
    textColor=colors.white
)

table_cell_style = ParagraphStyle(
    'TableCell',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8.5,
    leading=11,
    textColor=colors.HexColor('#1e293b')
)

story = []

# Title Banner
story.append(Paragraph("Deepstream — SaaS Demo Video Blueprint & Prompt Master Guide", title_style))
story.append(Paragraph("Complete Storyboard · UI Screenshots · Generative AI Video & Voiceover Prompts", subtitle_style))
story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0284c7'), spaceAfter=10))

# Executive Overview
story.append(Paragraph("1. Executive Summary & Video Strategy", h1_style))
story.append(Paragraph(
    "This master guide outlines the complete 60–90 second SaaS product demo video production strategy for <b>Deepstream</b> (<i>The Ocean Pricer</i>). "
    "It combines high-resolution UI screen captures with precise Gen-AI prompts (Sora / Gen-3 / Midjourney / ElevenLabs) to produce a high-converting promotional video.",
    body_style
))

overview_data = [
    [Paragraph("<b>Target Audience</b>", table_cell_style), Paragraph("Commodity Traders, Quantitative Analysts, Macro Hedge Funds, Energy/Agri Futures Traders", table_cell_style)],
    [Paragraph("<b>Core Value Prop</b>", table_cell_style), Paragraph("Physical oceanography precedes commodity futures (Copper, Tuna, Crude Oil). 26-yr walk-forward backtest.", table_cell_style)],
    [Paragraph("<b>Video Format</b>", table_cell_style), Paragraph("60s / 90s 4K MP4 (16:9 for Web/YouTube, 9:16 crop for X/Reels/Shorts)", table_cell_style)],
    [Paragraph("<b>Voiceover Tone</b>", table_cell_style), Paragraph("Authoritative, crisp, Wall Street quantitative research tone (Non-hype, institutional)", table_cell_style)],
]
t_overview = Table(overview_data, colWidths=[130, 410])
t_overview.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e0f2fe')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('PADDING', (0,0), (-1,-1), 4),
]))
story.append(t_overview)
story.append(Spacer(1, 10))

# Storyboard & Script Table
story.append(Paragraph("2. 60-Second Video Storyboard & Voiceover Script", h1_style))

sb_data = [
    [Paragraph("Time", table_header_style), Paragraph("Scene Name", table_header_style), Paragraph("Visual Action & UI Element", table_header_style), Paragraph("Voiceover Text (Onyx / ElevenLabs)", table_header_style)],
    [
        Paragraph("0:00 - 0:10", table_cell_style),
        Paragraph("Scene 1: Hook", table_cell_style),
        Paragraph("SST Thermal satellite ocean overlay zooming into Hero section", table_cell_style),
        Paragraph('"Traditional commodity traders rely on lagging price charts... but 71% of Earth is ocean. What if ocean physical data held the leading edge?"', table_cell_style)
    ],
    [
        Paragraph("0:10 - 0:25", table_cell_style),
        Paragraph("Scene 2: Setups", table_cell_style),
        Paragraph("Pan across live Active Signals table (Copper, Tuna, Crude Oil)", table_cell_style),
        Paragraph('"Meet Deepstream — the quantitative platform translating ocean temperature, chlorophyll, and plume signals into trade setups before markets react."', table_cell_style)
    ],
    [
        Paragraph("0:25 - 0:40", table_cell_style),
        Paragraph("Scene 3: Track Record", table_cell_style),
        Paragraph("Auto-zoom onto 26-Year Walk-Forward cumulative return (+140.5%)", table_cell_style),
        Paragraph('"Every setup is validated out-of-sample over 26 years of history. No lookahead bias. Just raw Granger-causality proven edge."', table_cell_style)
    ],
    [
        Paragraph("0:40 - 0:50", table_cell_style),
        Paragraph("Scene 4: Proof", table_cell_style),
        Paragraph("Highlight zero-lookahead methodology & econometric comparison table", table_cell_style),
        Paragraph('"Unlike typical signal providers, Deepstream publishes every single trade trade-by-trade and never fabricates setups in low-confidence regimes."', table_cell_style)
    ],
    [
        Paragraph("0:50 - 1:00", table_cell_style),
        Paragraph("Scene 5: Telegram", table_cell_style),
        Paragraph("Telegram Mobile/Desktop app notification card (User Screenshot Slot)", table_cell_style),
        Paragraph('"Receive daily position updates and full entry parameters directly in your private Telegram Pro channel instantly upon publication."', table_cell_style)
    ],
    [
        Paragraph("1:00 - 1:10", table_cell_style),
        Paragraph("Scene 6: CTA", table_cell_style),
        Paragraph("Transition to Cashfree hosted checkout modal & pricing options", table_cell_style),
        Paragraph('"Gain your quantitative ocean advantage today. Visit deepstreamofficial.netlify.app and activate your subscription."', table_cell_style)
    ]
]

t_sb = Table(sb_data, colWidths=[55, 75, 170, 240])
t_sb.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('PADDING', (0,0), (-1,-1), 4),
]))
story.append(t_sb)

story.append(PageBreak())

# Section 3: UI Screenshots & Scene Requirements
story.append(Paragraph("3. Scene Breakdown & UI Screenshots", h1_style))
story.append(Paragraph("Below are the exact UI screenshots captured for each scene in the SaaS video guide.", body_style))

def add_scene_image_block(title, img_name, description):
    img_path = os.path.join(SCREENSHOTS_DIR, img_name)
    story.append(Paragraph(title, h2_style))
    story.append(Paragraph(description, body_style))
    if os.path.exists(img_path):
        # Scale to 520pt width x 260pt height (approx 2:1 ratio)
        story.append(RLImage(img_path, width=520, height=260))
    else:
        story.append(Paragraph(f"<i>[ Image file missing: {img_name} ]</i>", body_style))
    story.append(Spacer(1, 8))

add_scene_image_block(
    "Scene 1: Hero Section & Ocean Intelligence Header",
    "scene1_hero.png",
    "<b>Visual Action:</b> Slow pan across top navigation bar, main headline <i>'The ocean moves commodities. We trade that signal.'</i>, and live snapshot terminal."
)

add_scene_image_block(
    "Scene 2: Active Trade Signal Setups",
    "scene2_signals.png",
    "<b>Visual Action:</b> Zoom in on Active Signals Table showcasing weekly setups (Pacific ENSO → Copper, Atlantic Chlorophyll → Tuna, Gulf Plumes → Crude Oil)."
)

story.append(PageBreak())

add_scene_image_block(
    "Scene 3: 26-Year Walk-Forward Track Record",
    "scene3_trackrecord.png",
    "<b>Visual Action:</b> Highlight cumulative performance statistics: 362 simulated trades, +140.5% return, 41.1% win rate, out-of-sample replay."
)

add_scene_image_block(
    "Scene 4: Econometric Proof & Methodology",
    "scene4_proof.png",
    "<b>Visual Action:</b> Display comparison chart pitting Deepstream's Granger-causality tested methodology against typical curve-fitted signal services."
)

story.append(PageBreak())

add_scene_image_block(
    "Scene 5: Private Telegram Pro Signal Delivery",
    "scene5_telegram_placeholder.png",
    "<b>Visual Action & User Note:</b> <i>[USER DIRECTIVE ENFORCED]</i> This slot is reserved for your Telegram screenshot. Capture your Telegram mobile or desktop window showing instant alerts and drop it into this scene."
)

add_scene_image_block(
    "Scene 6: Pricing & Cashfree Hosted Checkout Modal",
    "scene6_checkout_modal.png",
    "<b>Visual Action:</b> Smooth zoom onto ₹2,499/mo subscription card and the Cashfree payment modal with email/phone input fields."
)

story.append(PageBreak())

# Section 4: Master AI Prompts Collection
story.append(Paragraph("4. Complete Master AI Prompt Collection", h1_style))
story.append(Paragraph("Use these copy-paste prompts in your Gen-AI tools to generate stock footage, voiceovers, thumbnails, and marketing copy for the SaaS video.", body_style))

# Sub-section A: Video Generators
story.append(Paragraph("A. Generative AI Video Prompts (Runway Gen-3 / Sora / Hailuo / Luma)", h2_style))
story.append(Paragraph("<b>Prompt 1: Dark Ocean Thermal Currents (Hero Intro)</b>", body_style))
story.append(Paragraph(
    "Cinematic 4k video, dark futuristic oceanic globe with glowing neon blue and cyan sea-surface temperature (SST) anomaly heatmaps. "
    "Camera slowly zooms past Pacific Ocean thermal currents into digital data streams, dark aesthetic, octane render, 60fps --ar 16:9",
    prompt_box_style
))

story.append(Paragraph("<b>Prompt 2: Subsea Chemical Plumes & Sensor Array</b>", body_style))
story.append(Paragraph(
    "Underwater ultra-HD camera shot of subsea sensor array monitoring deep Gulf of Mexico ocean floor, glowing telemetry data points connecting ocean currents to energy pipelines, dark blue atmosphere, photorealistic lighting --ar 16:9",
    prompt_box_style
))

story.append(Paragraph("<b>Prompt 3: Commodity Futures Holographic Trading Desk</b>", body_style))
story.append(Paragraph(
    "High-tech financial quantitative trading desk at night, dual monitors showing dark mode commodity futures candlestick charts synchronized with ocean satellite imagery, smooth camera glide, cinematic depth of field --ar 16:9",
    prompt_box_style
))

# Sub-section B: Voiceover Prompts
story.append(Paragraph("B. Voiceover & Audio Prompts (ElevenLabs / OpenAI TTS / Play.ht)", h2_style))
story.append(Paragraph("<b>ElevenLabs Voice Model Settings:</b> Voice: <i>Adam</i> or <i>Onyx</i> | Stability: 0.65 | Clarity: 0.85 | Style Exaggeration: 0.15", body_style))
story.append(Paragraph("<b>Script with SSML Timing Tags:</b>", body_style))
story.append(Paragraph(
    "&lt;speak&gt;<br/>"
    "Traditional commodity traders rely on lagging price charts... &lt;break time=\"0.4s\"/&gt;<br/>"
    "but seventy-one percent of Earth is ocean. What if ocean physical data held the leading edge? &lt;break time=\"0.6s\"/&gt;<br/>"
    "Meet Deepstream — the quantitative platform that converts sea surface temperature, chlorophyll, and chemical plumes into actionable trade setups. &lt;break time=\"0.6s\"/&gt;<br/>"
    "Every signal is validated out-of-sample over twenty-six years of history. Zero hindsight bias. &lt;break time=\"0.5s\"/&gt;<br/>"
    "Get full entry parameters and daily position updates delivered directly to your private Telegram channel. &lt;break time=\"0.5s\"/&gt;<br/>"
    "Gain your unfair ocean edge today at deepstreamofficial.netlify.app.<br/>"
    "&lt;/speak&gt;",
    prompt_box_style
))

# Sub-section C: Thumbnail Prompts
story.append(Paragraph("C. Video Thumbnail & Cover Art Prompts (Midjourney / Flux)", h2_style))
story.append(Paragraph(
    "Dark sleek YouTube video thumbnail, glowing 3D holographic globe with ocean thermal wave lines pointing directly into Copper and Crude Oil price tickers, bold text 'THE OCEAN PRICER', ultra-modern UI elements, 8k resolution --ar 16:9 --v 6.0",
    prompt_box_style
))

# Sub-section D: Marketing Copy
story.append(Paragraph("D. Social Media Launch Copy Prompts (Claude / ChatGPT)", h2_style))
story.append(Paragraph(
    "Write a high-converting X (Twitter) thread launching a new SaaS video for Deepstream (The Ocean Pricer). Highlight: 1) Why physical oceanography precedes commodity markets, 2) The 26-yr walk-forward track record (+140.5% return), 3) Telegram Pro channel delivery. Include call to action link to deepstreamofficial.netlify.app. Tone: sharp, quantitative, non-hype.",
    prompt_box_style
))

# Sub-section E: Screen Studio & Editing Specs
story.append(Paragraph("E. Video Editor & Screen Studio Configuration Specs", h2_style))
specs_data = [
    [Paragraph("<b>Setting</b>", table_cell_style), Paragraph("<b>Recommended Configuration</b>", table_cell_style)],
    [Paragraph("Canvas Resolution", table_cell_style), Paragraph("3840 x 2160 (4K) exported to 1080p 60fps MP4", table_cell_style)],
    [Paragraph("Cursor Smoothing", table_cell_style), Paragraph("Screen Studio: Smart Auto-Zoom on Active Signal Table & Chart elements", table_cell_style)],
    [Paragraph("Background Music", table_cell_style), Paragraph("Dark synth/ambient tech track (e.g. 'Deep Ocean Quant'), audio level -22 dB with voiceover ducking", table_cell_style)],
    [Paragraph("Kinetic Captions", table_cell_style), Paragraph("Font: <i>Inter SemiBold</i>, Yellow accent color (#38bdf8 / #f59e0b), 2-3 words per burst", table_cell_style)],
]
t_specs = Table(specs_data, colWidths=[140, 400])
t_specs.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('PADDING', (0,0), (-1,-1), 4),
]))
story.append(t_specs)

# Build Document
doc.build(story)

# Copy to Artifact directory
shutil.copy(pdf_docs_path, pdf_artifact_path)

print("PDF successfully generated!")
print("Docs path:", pdf_docs_path)
print("Artifact path:", pdf_artifact_path)
