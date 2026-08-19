import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

pdf_path = r'C:\Users\musab\.gemini\antigravity-ide\brain\8e08ff91-0a77-46a0-a991-9febd63f98b9\deepstream_saas_video_steps.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'DocTitle',
    parent=styles['Heading1'],
    fontName='Helvetica-Bold',
    fontSize=20,
    leading=24,
    textColor=colors.HexColor('#0f172a'),
    spaceAfter=4
)
subtitle_style = ParagraphStyle(
    'DocSubTitle',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=10,
    leading=13,
    textColor=colors.HexColor('#475569'),
    spaceAfter=10
)
heading_style = ParagraphStyle(
    'SectionHeading',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=12,
    leading=16,
    textColor=colors.HexColor('#0284c7'),
    spaceBefore=10,
    spaceAfter=4
)
body_style = ParagraphStyle(
    'BodyTextCustom',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    leading=12,
    textColor=colors.HexColor('#334155'),
    spaceAfter=4
)
header_cell_style = ParagraphStyle(
    'HeaderCell',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=9,
    leading=11,
    textColor=colors.white
)

story = []

# Title & Header
story.append(Paragraph('Deepstream — SaaS Demo Video Master Guide', title_style))
story.append(Paragraph('Step-by-Step Production Roadmap, Storyboard & Non-ElevenLabs Audio Guide', subtitle_style))
story.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=8))

# Section 1: Overview & Stack
story.append(Paragraph('1. Production Tooling Stack (Non-ElevenLabs)', heading_style))
tool_data = [
    [Paragraph('<b>Category</b>', body_style), Paragraph('<b>Tool</b>', body_style), Paragraph('<b>Details & Voice</b>', body_style)],
    [Paragraph('Voiceover (Generated)', body_style), Paragraph('Microsoft Neural TTS', body_style), Paragraph('Voice: <i>en-US-ChristopherNeural</i> (Generated MP3)', body_style)],
    [Paragraph('Voiceover (Alt 1)', body_style), Paragraph('OpenAI TTS API', body_style), Paragraph('Voice: <i>onyx</i> or <i>echo</i> ($0.015 / 1k chars)', body_style)],
    [Paragraph('Voiceover (Alt 2)', body_style), Paragraph('Play.ht', body_style), Paragraph('Voice: <i>Larry</i> (SaaS Promo Model)', body_style)],
    [Paragraph('Screen Capture', body_style), Paragraph('Screen Studio / OBS', body_style), Paragraph('4K recording with smooth cursor tracking & auto-zoom', body_style)],
    [Paragraph('Video Editor', body_style), Paragraph('CapCut / Premiere Pro', body_style), Paragraph('Auto kinetic captions, ambient background music (-22dB)', body_style)]
]
tool_table = Table(tool_data, colWidths=[120, 130, 290])
tool_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e0f2fe')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('PADDING', (0,0), (-1,-1), 4),
]))
story.append(tool_table)
story.append(Spacer(1, 6))

# Section 2: Step-by-Step Production Roadmap
story.append(Paragraph('2. Step-by-Step Production Roadmap', heading_style))
steps_data = [
    [Paragraph('<b>Step</b>', body_style), Paragraph('<b>Action Item</b>', body_style), Paragraph('<b>Instructions & Target</b>', body_style)],
    [Paragraph('Step 1', body_style), Paragraph('Prepare Environment', body_style), Paragraph('Launch local server or live landing page at <i>deepstreamofficial.netlify.app</i> in 4K/1080p resolution.', body_style)],
    [Paragraph('Step 2', body_style), Paragraph('Record Screen Scenes', body_style), Paragraph('Capture 5 key views: (1) Hero banner, (2) Active Trade Signals (Copper/Tuna), (3) 26-Yr Walk-Forward Track Record, (4) Telegram Pro alerts, (5) Cashfree checkout modal.', body_style)],
    [Paragraph('Step 3', body_style), Paragraph('Attach Voiceover MP3', body_style), Paragraph('Import the generated <i>deepstream_voiceover.mp3</i> (or OpenAI TTS Onyx model) into video editor audio timeline.', body_style)],
    [Paragraph('Step 4', body_style), Paragraph('Edit & Synchronize', body_style), Paragraph('Align Screen Studio auto-zooms with voiceover cues in CapCut/Premiere. Add auto-captions and ambient background music (-22dB).', body_style)],
    [Paragraph('Step 5', body_style), Paragraph('Export & Publish', body_style), Paragraph('Export in 1080p 60fps MP4 format for Twitter/X, YouTube Shorts, LinkedIn, and website embeds.', body_style)],
]
steps_table = Table(steps_data, colWidths=[45, 125, 370])
steps_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('PADDING', (0,0), (-1,-1), 4),
]))
story.append(steps_table)
story.append(Spacer(1, 6))

# Section 3: 60-Second Storyboard Table
story.append(Paragraph('3. 60-Second Storyboard & Voiceover Script', heading_style))
sb_data = [
    [Paragraph('Time', header_cell_style), Paragraph('Scene', header_cell_style), Paragraph('Visual Action', header_cell_style), Paragraph('Voiceover Text', header_cell_style)],
    [
        Paragraph('0:00 - 0:10', body_style),
        Paragraph('The Hook', body_style),
        Paragraph('Zoom from stock chart into dark globe map with ocean thermal currents', body_style),
        Paragraph('"Traditional commodity traders rely on lagging price charts... but 71% of Earth is ocean. What if ocean data held the leading edge?"', body_style)
    ],
    [
        Paragraph('0:10 - 0:25', body_style),
        Paragraph('The Solution', body_style),
        Paragraph('Transition to Deepstream UI; auto-zoom on active signal cards for Copper and Tuna', body_style),
        Paragraph('"Meet Deepstream — the quantitative platform that converts ocean indicators into actionable commodity trade setups."', body_style)
    ],
    [
        Paragraph('0:25 - 0:45', body_style),
        Paragraph('Track Record', body_style),
        Paragraph('Pan across 26-year walk-forward backtest chart and historical trade log', body_style),
        Paragraph('"Every signal is backed by 26+ years of walk-forward backtesting. No hindsight bias. Just raw statistical correlation."', body_style)
    ],
    [
        Paragraph('0:45 - 0:55', body_style),
        Paragraph('Telegram Alert', body_style),
        Paragraph('Split screen showing daily position updates and Pro channel alerts on mobile', body_style),
        Paragraph('"Get full entry parameters and daily position updates delivered instantly to your private Telegram channel."', body_style)
    ],
    [
        Paragraph('0:55 - 1:05', body_style),
        Paragraph('Call to Action', body_style),
        Paragraph('Cashfree checkout modal transition to deepstreamofficial.netlify.app', body_style),
        Paragraph('"Gain your unfair quantitative advantage today. Visit deepstreamofficial.netlify.app and subscribe to Deepstream Pro."', body_style)
    ]
]
sb_table = Table(sb_data, colWidths=[55, 65, 170, 250])
sb_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('PADDING', (0,0), (-1,-1), 4),
]))
story.append(sb_table)

doc.build(story)
print('PDF generated successfully at:', pdf_path)
