"""An update as a PDF with the company's logo and colour (FR-6.6).

ReportLab draws it in pure Python, so nothing outside the Python packages is needed to run
it. Output is byte-for-byte repeatable, which is what the snapshot test checks. Text that
came from people or files (names, file names) is escaped for ReportLab's markup and has
formula starts neutralised, in case the text is copied into a spreadsheet. Figures are
formatted by code and printed as they are.
"""

import io
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from boardroom.security.export import safe_cell

# From design-system/tokens.json: the defaults when a company has not set its own colour.
INK = colors.HexColor("#123C4A")
MUTED = colors.HexColor("#4A6670")
LINE = colors.HexColor("#D6E1E4")
SURFACE = colors.HexColor("#EEF3F4")
WHITE = colors.HexColor("#FFFFFF")


@dataclass(frozen=True)
class FigureLine:
    label: str
    period: str
    display: str
    source: str
    changed: str | None = None


@dataclass(frozen=True)
class UpdateDocument:
    company_name: str
    colour: str | None
    logo: bytes | None
    headline: str
    detail: str
    labels: list[str] = field(default_factory=list)
    figures: list[FigureLine] = field(default_factory=list)


def text(value: str) -> str:
    """People's and files' words, made safe for the markup and for spreadsheets."""
    return escape(safe_cell(value))


def _on(colour: colors.Color) -> colors.Color:
    """White or ink, whichever reads on the colour (WCAG relative luminance)."""

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lum = (
        0.2126 * channel(colour.red)
        + 0.7152 * channel(colour.green)
        + 0.0722 * channel(colour.blue)
    )
    return WHITE if (1.05 / (lum + 0.05)) >= 4.5 else INK


def _month(period: str) -> str:
    year, month = period.split("-")
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][
        int(month) - 1
    ] + f" {year}"


def render(doc: UpdateDocument) -> bytes:
    brand = colors.HexColor(doc.colour) if doc.colour else INK
    on_brand = _on(brand)
    styles = {
        "band": ParagraphStyle(
            "band", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=on_brand
        ),
        "head": ParagraphStyle(
            "head", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=INK
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10, leading=14, textColor=INK
        ),
        "muted": ParagraphStyle(
            "muted", fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=MUTED
        ),
        "figure": ParagraphStyle(
            "figure",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
    }
    out = io.BytesIO()
    page = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{doc.company_name} update",
        author="BoardRoom.io",
        creator="BoardRoom.io",
        invariant=1,
    )
    width = A4[0] - 36 * mm

    band_cells: list[object] = [Paragraph(text(doc.company_name), styles["band"])]
    widths = [width]
    if doc.logo:
        reader = ImageReader(io.BytesIO(doc.logo))
        w, h = reader.getSize()
        height = 12 * mm
        band_cells.insert(0, Image(io.BytesIO(doc.logo), width=height * w / h, height=height))
        widths = [height * w / h + 6 * mm, width - height * w / h - 6 * mm]
    band = Table([band_cells], colWidths=widths)
    band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), brand),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    story: list[object] = [
        band,
        Spacer(0, 7 * mm),
        Paragraph(text(doc.headline), styles["head"]),
        Spacer(0, 1 * mm),
        Paragraph(escape(doc.detail), styles["body"]),
    ]
    for label in doc.labels:
        story += [Spacer(0, 1 * mm), Paragraph(text(label), styles["muted"])]
    story.append(Spacer(0, 6 * mm))

    if doc.figures:
        rows = []
        for f in doc.figures:
            left = [
                Paragraph(escape(f.label.upper()), styles["label"]),
                Paragraph(escape(_month(f.period)), styles["muted"]),
                Paragraph("Source: " + text(f.source), styles["muted"]),
            ]
            if f.changed:
                left.append(Paragraph(text(f.changed), styles["muted"]))
            rows.append([left, Paragraph(escape(f.display), styles["figure"])])
        table = Table(rows, colWidths=[width * 0.7, width * 0.3])
        table.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -2), 0.6, LINE),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("This update has no figures.", styles["muted"]))
    story += [
        Spacer(0, 8 * mm),
        Paragraph(
            "Figures are calculated by code from the company's own files, except where a "
            "figure says a person changed it. Each one can be traced to its source rows in "
            "BoardRoom.io."
            if any(f.changed for f in doc.figures)
            else "Every figure is calculated by code from the company's own files. "
            "Each one can be traced to its source rows in BoardRoom.io.",
            styles["muted"],
        ),
    ]
    page.build(story)
    return out.getvalue()
