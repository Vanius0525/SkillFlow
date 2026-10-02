"""Build the Chinese research brief with embedded fonts and clickable references."""
from pathlib import Path
import re
from html import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parent
SRC = ROOT / '研究定位与相关工作_20261003.md'
OUT = SRC.with_suffix('.pdf')
FONT = '/mnt/c/Windows/Fonts/msyh.ttc'
pdfmetrics.registerFont(TTFont('CJK', FONT))
pdfmetrics.registerFontFamily('CJK', normal='CJK', bold='CJK', italic='CJK', boldItalic='CJK')
styles = {
    'body': ParagraphStyle('body', fontName='CJK', fontSize=9.5, leading=14.6, spaceAfter=7, wordWrap='CJK', textColor=colors.HexColor('#243247')),
    'h1': ParagraphStyle('h1', fontName='CJK', fontSize=20, leading=28, spaceAfter=17, textColor=colors.HexColor('#163b63')),
    'h2': ParagraphStyle('h2', fontName='CJK', fontSize=11.5, leading=17, spaceBefore=5, spaceAfter=8, textColor=colors.HexColor('#146c83')),
    'ref': ParagraphStyle('ref', fontName='CJK', fontSize=8, leading=12.5, spaceAfter=3, wordWrap='CJK'),
}
def inline(text):
    text = escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<font color="#143b63">\1</font>', text)
    return re.sub(r'(https://[^\s]+)', r'<link href="\1" color="#146c83">\1</link>', text)

def footer(c, doc):
    c.setStrokeColor(colors.HexColor('#c9d4df'))
    c.line(43, 42, A4[0]-43, 42)
    c.setFont('CJK', 8)
    c.setFillColor(colors.HexColor('#63768a'))
    c.drawString(43, 28, 'SkillFlow · 研究定位审查 · 2026-10-03')
    c.drawRightString(A4[0]-43, 28, str(doc.page))

story=[]
for line in SRC.read_text().splitlines():
    if not line.strip():
        continue
    if line == '---PAGE---':
        story.append(PageBreak())
        continue
    key = 'h1' if line.startswith('# ') else 'h2' if line.startswith('## ') else 'ref' if re.match(r'\[R\d+\]', line) else 'body'
    line = re.sub(r'^#{1,2} ', '', line)
    story.append(Paragraph(inline(line), styles[key]))
doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=43, leftMargin=43, topMargin=40, bottomMargin=54, title='当前论文的竞争力与研究定位', author='SkillFlow Research Review')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
