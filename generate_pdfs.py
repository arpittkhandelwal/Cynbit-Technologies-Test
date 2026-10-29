"""
Convert Markdown assessment reports to professional PDFs using ReportLab.
"""
import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted, KeepTogether, HRFlowable
)

def clean_markdown_inline(text: str) -> str:
    # Escape XML entities
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert bold **text** to <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Convert inline code `code`
    text = re.sub(r'`(.+?)`', r'<font face="Courier" color="#0F172A">\1</font>', text)
    return text

def md_to_pdf(md_path: Path, pdf_path: Path, title: str):
    print(f"Generating PDF: {pdf_path} from {md_path}")
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=12,
        spaceBefore=14
    )
    
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=8,
        spaceBefore=12
    )
    
    h3_style = ParagraphStyle(
        'DocH3',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#2563EB'),
        spaceAfter=6,
        spaceBefore=10
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=body_style,
        leftIndent=15,
        bulletIndent=5,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'DocCode',
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#E2E8F0'),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white
    )

    story = []

    # Title Banner
    story.append(Paragraph(title, h1_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=14))

    i = 0
    in_code_block = False
    code_lines = []

    while i < len(lines):
        line = lines[i].rstrip()

        # Handle Code Blocks
        if line.startswith("```"):
            if in_code_block:
                # End of code block
                block_text = "\n".join(code_lines)
                story.append(Preformatted(block_text[:3000], code_style))
                story.append(Spacer(1, 4))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Handle Markdown Tables
        if line.startswith("|") and i + 1 < len(lines) and lines[i+1].strip().startswith("|"):
            table_raw = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_str = lines[i].strip()
                # ignore separator line e.g. |---|---|
                if not re.match(r'^\|[\s\-:|]+\|$', row_str):
                    cols = [c.strip() for c in row_str.split("|")[1:-1]]
                    if cols:
                        table_raw.append(cols)
                i += 1

            if table_raw:
                # Build reportlab table
                num_cols = max(len(r) for r in table_raw)
                col_width = (doc.width) / max(num_cols, 1)
                
                table_data = []
                for row_idx, row in enumerate(table_raw):
                    formatted_row = []
                    is_header = (row_idx == 0)
                    for col_text in row:
                        style = table_header_style if is_header else table_cell_style
                        clean_text = clean_markdown_inline(col_text)
                        formatted_row.append(Paragraph(clean_text, style))
                    # pad if necessary
                    while len(formatted_row) < num_cols:
                        formatted_row.append(Paragraph("", table_cell_style))
                    table_data.append(formatted_row)

                tbl = Table(table_data, colWidths=[col_width] * num_cols)
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8FAFC')]),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 8))
            continue

        # Skip top title in file if already rendered in banner
        if line.startswith("# ") and i < 5:
            i += 1
            continue

        # Headings
        if line.startswith("# "):
            clean = clean_markdown_inline(line[2:].strip())
            story.append(Paragraph(clean, h1_style))
        elif line.startswith("## "):
            clean = clean_markdown_inline(line[3:].strip())
            story.append(Paragraph(clean, h2_style))
        elif line.startswith("### "):
            clean = clean_markdown_inline(line[4:].strip())
            story.append(Paragraph(clean, h3_style))
        elif line.startswith("#### "):
            clean = clean_markdown_inline(line[5:].strip())
            story.append(Paragraph(clean, h3_style))
        elif line.startswith("- ") or line.startswith("* "):
            clean = clean_markdown_inline(line[2:].strip())
            story.append(Paragraph(f"• &nbsp; {clean}", bullet_style))
        elif re.match(r'^\d+\.\s+', line):
            clean = clean_markdown_inline(re.sub(r'^\d+\.\s+', '', line).strip())
            story.append(Paragraph(f"1. &nbsp; {clean}", bullet_style))
        elif line.startswith("> "):
            clean = clean_markdown_inline(line[2:].strip())
            quote_style = ParagraphStyle('Quote', parent=body_style, leftIndent=12, textColor=colors.HexColor('#475569'))
            story.append(Paragraph(f"<i>{clean}</i>", quote_style))
        elif line.strip() == "---":
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=8, spaceBefore=4))
        elif line.strip():
            clean = clean_markdown_inline(line.strip())
            story.append(Paragraph(clean, body_style))
        else:
            story.append(Spacer(1, 3))

        i += 1

    doc.build(story)
    print(f"Successfully generated: {pdf_path}")

if __name__ == "__main__":
    base_dir = Path("/Users/arpitkhandelwal/.gemini/antigravity/scratch/cynbit-assessment")
    reports_dir = base_dir / "reports"
    pdf_dir = base_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    r1 = reports_dir / "01_AI_Opportunity_Report.md"
    p1 = pdf_dir / "01_AI_Opportunity_Report.pdf"
    md_to_pdf(r1, p1, "Cynbit Technologies — AI Opportunity Report")

    r2 = reports_dir / "02_Technical_Approach_Report.md"
    p2 = pdf_dir / "02_Technical_Approach_Report.pdf"
    md_to_pdf(r2, p2, "Cynbit Technologies — Technical Approach Report")
