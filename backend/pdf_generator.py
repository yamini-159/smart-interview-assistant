from io import BytesIO
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_report(history_data: list) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', 
        parent=styles['Heading1'], 
        fontSize=18, 
        textColor=colors.HexColor('#1E3A8A'), 
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'Heading', 
        parent=styles['Heading2'], 
        fontSize=14, 
        textColor=colors.HexColor('#0F766E'), 
        spaceAfter=8
    )
    body_style = ParagraphStyle(
        'Body', 
        parent=styles['Normal'], 
        fontSize=9, 
        leading=12
    )

    # Document Header
    story.append(Paragraph("Smart AI Interview Assistant - Candidate Summary", title_style))
    
    if history_data:
        df = pd.DataFrame(history_data)
        df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
        avg_score = round(df['score'].mean(), 1)
        max_score = int(df['score'].max())
        total_q = len(df)
    else:
        avg_score, max_score, total_q = 0, 0, 0

    story.append(Paragraph(f"<b>Total Questions:</b> {total_q} | <b>Average Score:</b> {avg_score}/10 | <b>Highest Score:</b> {max_score}/10", body_style))
    story.append(Spacer(1, 14))

    # Evaluation Table
    story.append(Paragraph("Detailed Evaluation Logs", heading_style))
    table_data = [["Round", "Question", "Score", "Feedback"]]
    
    for row in history_data:
        table_data.append([
            Paragraph(str(row.get('round_type', 'N/A')), body_style),
            Paragraph(str(row.get('question', 'N/A')), body_style),
            str(row.get('score', '0')),
            Paragraph(str(row.get('feedback', 'N/A')), body_style)
        ])

    pdf_table = Table(table_data, colWidths=[70, 180, 40, 250])
    pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    
    story.append(pdf_table)
    doc.build(story)
    
    buffer.seek(0)
    return buffer