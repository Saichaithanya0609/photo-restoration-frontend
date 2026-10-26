"""Generate a reference-layout project poster as a print-size PDF."""

from pathlib import Path
import math

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "Poster"
OUT_PATH = OUT_DIR / "photo_restoration_reference_layout.pdf"

PAGE_W, PAGE_H = 30 * inch, 48 * inch
GOLD = colors.HexColor("#FFBE00")
INK = colors.HexColor("#171717")
MUTED = colors.HexColor("#414141")
PALE = colors.HexColor("#F7F8FA")
RULE = colors.HexColor("#D5D9DE")

MARGIN = 58
GAP = 38
COL_W = (PAGE_W - 2 * MARGIN - 2 * GAP) / 3
BODY_TOP = 505
FOOTER_H = 58
SECTION_H = 56


BODY = ParagraphStyle(
    "PosterBody",
    fontName="Helvetica",
    fontSize=29,
    leading=37,
    textColor=INK,
    alignment=TA_LEFT,
    spaceAfter=11,
)
BULLET = ParagraphStyle(
    "PosterBullet",
    parent=BODY,
    leftIndent=25,
    firstLineIndent=-18,
    spaceAfter=12,
)
SMALL = ParagraphStyle(
    "PosterSmall",
    fontName="Helvetica",
    fontSize=23,
    leading=30,
    textColor=INK,
    alignment=TA_LEFT,
    spaceAfter=8,
)
CAPTION = ParagraphStyle(
    "PosterCaption",
    fontName="Helvetica-Bold",
    fontSize=24,
    leading=29,
    textColor=INK,
    alignment=TA_CENTER,
)


def draw_top_rect(pdf, x, top, width, height, fill, stroke=None, radius=0):
    y = PAGE_H - top - height
    pdf.setFillColor(fill)
    if stroke:
        pdf.setStrokeColor(stroke)
        pdf.setLineWidth(1.5)
    else:
        pdf.setStrokeColor(fill)
    if radius:
        pdf.roundRect(x, y, width, height, radius, fill=1, stroke=1 if stroke else 0)
    else:
        pdf.rect(x, y, width, height, fill=1, stroke=1 if stroke else 0)


def draw_section_bar(pdf, x, top, width, title):
    draw_top_rect(pdf, x, top, width, SECTION_H, GOLD)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 31)
    pdf.drawCentredString(x + width / 2, PAGE_H - top - SECTION_H + 16, title)
    return top + SECTION_H + 18


def draw_section(pdf, x, top, width, title, items, style=BODY, gap=13):
    top = draw_section_bar(pdf, x, top, width, title)
    for item in items:
        paragraph = Paragraph(item, style)
        _, height = paragraph.wrap(width - 28, PAGE_H)
        paragraph.drawOn(pdf, x + 14, PAGE_H - top - height)
        top += height + gap
    return top + 12


def draw_bullets(pdf, x, top, width, title, items):
    return draw_section(
        pdf,
        x,
        top,
        width,
        title,
        [f"&#8226;&nbsp; {item}" for item in items],
        style=BULLET,
        gap=5,
    )


def draw_flow(pdf, x, top, width):
    top = draw_section_bar(pdf, x, top, width, "Processing Workflow")
    def node(node_x, node_top, node_w, heading, detail, fill=PALE):
        draw_top_rect(pdf, node_x, node_top, node_w, 94, fill, RULE, radius=10)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 23)
        pdf.drawCentredString(node_x + node_w / 2, PAGE_H - node_top - 34, heading)
        pdf.setFont("Helvetica", 19)
        pdf.setFillColor(MUTED)
        pdf.drawCentredString(node_x + node_w / 2, PAGE_H - node_top - 64, detail)

    def arrow(x1, y1, x2, y2, label=None):
        pdf.setStrokeColor(MUTED)
        pdf.setFillColor(MUTED)
        pdf.setLineWidth(2.4)
        pdf.line(x1, y1, x2, y2)
        angle = math.atan2(y2 - y1, x2 - x1)
        head = 9
        for offset in (2.55, -2.55):
            pdf.line(x2, y2, x2 + head * math.cos(angle + offset), y2 + head * math.sin(angle + offset))
        if label:
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 18)
            pdf.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 8, label)

    center = x + width / 2
    box_w = width - 80
    box_x = x + 40
    node(box_x, top, box_w, "01  Upload + validation", "React upload · FastAPI decode")
    top += 94
    arrow(center, PAGE_H - top - 2, center, PAGE_H - top - 24)
    top += 27

    # Branch in the flowchart makes the user's optional denoising choice explicit.
    diamond_w, diamond_h = 170, 94
    diamond_y = PAGE_H - top - diamond_h
    pdf.setFillColor(colors.HexColor("#FFF1BF"))
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(2)
    pdf.line(center, diamond_y + diamond_h, center + diamond_w / 2, diamond_y + diamond_h / 2)
    pdf.line(center + diamond_w / 2, diamond_y + diamond_h / 2, center, diamond_y)
    pdf.line(center, diamond_y, center - diamond_w / 2, diamond_y + diamond_h / 2)
    pdf.line(center - diamond_w / 2, diamond_y + diamond_h / 2, center, diamond_y + diamond_h)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawCentredString(center, diamond_y + 49, "Remove noise?")
    top += diamond_h + 20

    branch_gap = 20
    branch_w = (width - 50 - branch_gap) / 2
    left_x, right_x = x + 25, x + 25 + branch_w + branch_gap
    branch_top = top
    node(left_x, branch_top, branch_w, "YES · NLM", "Strength 25; optional", colors.HexColor("#FFF8E3"))
    node(right_x, branch_top, branch_w, "NO · Preserve", "Use decoded image", colors.HexColor("#F0F4F8"))
    branch_y = PAGE_H - branch_top - 2
    decision_y = PAGE_H - (branch_top - 20)
    arrow(center - 32, decision_y, left_x + branch_w / 2, branch_y, "YES")
    arrow(center + 32, decision_y, right_x + branch_w / 2, branch_y, "NO")
    top += 94
    rail_y = PAGE_H - top - 12
    pdf.setStrokeColor(MUTED)
    pdf.setLineWidth(2.4)
    pdf.line(left_x + branch_w / 2, PAGE_H - top - 2, left_x + branch_w / 2, rail_y)
    pdf.line(right_x + branch_w / 2, PAGE_H - top - 2, right_x + branch_w / 2, rail_y)
    pdf.line(left_x + branch_w / 2, rail_y, right_x + branch_w / 2, rail_y)
    arrow(center, rail_y, center, rail_y - 17)
    top += 35

    for heading, detail in [
        ("02  Detect + refine mask", "Directional and ridge responses · filter candidates"),
        ("03  Inpaint damaged regions", "Select method based on mask coverage"),
        ("04  Return restored PNG", "Browser preview and download"),
    ]:
        node(box_x, top, box_w, heading, detail)
        top += 94
        if heading != "04  Return restored PNG":
            arrow(center, PAGE_H - top - 2, center, PAGE_H - top - 22)
            top += 24
    return top + 18


def draw_image_figure(pdf, path, x, top, width, max_height, caption):
    image = ImageReader(str(path))
    image_w, image_h = image.getSize()
    scale = min((width - 30) / image_w, max_height / image_h)
    draw_w, draw_h = image_w * scale, image_h * scale
    draw_top_rect(pdf, x, top, width, draw_h + 24, colors.white, RULE, radius=6)
    draw_x = x + (width - draw_w) / 2
    draw_y = PAGE_H - top - 12 - draw_h
    pdf.drawImage(image, draw_x, draw_y, width=draw_w, height=draw_h, mask="auto")
    top += draw_h + 31
    paragraph = Paragraph(caption, CAPTION)
    _, caption_h = paragraph.wrap(width - 20, 100)
    paragraph.drawOn(pdf, x + 10, PAGE_H - top - caption_h)
    return top + caption_h + 20


def draw_results_figures(pdf, x, top, width):
    top = draw_section_bar(pdf, x, top, width, "Implementation Results")
    assets = [
        (OUT_DIR / "assets" / "portrait_input.jpeg", "Fig. 1  Input photograph"),
        (
            OUT_DIR / "assets" / "portrait_damage_mask.png",
            "Fig. 2  Binary damage mask",
        ),
        (
            OUT_DIR / "assets" / "portrait_damage_overlay.png",
            "Fig. 3  Detected damage overlay",
        ),
        (
            OUT_DIR / "assets" / "portrait_restored.png",
            "Fig. 4  Output using the current mask",
        ),
    ]
    for path, caption in assets:
        top = draw_image_figure(pdf, path, x, top, width, 390, caption)
    return top


def draw_results_table(pdf, x, top, width):
    cell = ParagraphStyle("TableCell", parent=SMALL, fontSize=19, leading=24, spaceAfter=0)
    head = ParagraphStyle("TableHead", parent=cell, fontName="Helvetica-Bold", textColor=INK)
    data = [
        [Paragraph("Stage", head), Paragraph("Method", head), Paragraph("Observed result", head)],
        [Paragraph("Noise option", cell), Paragraph("NLM · strength 25", cell), Paragraph("Off by default; both settings returned valid PNG output.", cell)],
        [Paragraph("Mask · image02", cell), Paragraph("Symmetry + ridge detection", cell), Paragraph("6.94% coverage; scratch gaps and texture false positives remain.", cell)],
        [Paragraph("Inpainting", cell), Paragraph("Biharmonic", cell), Paragraph("Repairs masked pixels; quality depends on mask accuracy.", cell)],
    ]
    table = Table(data, colWidths=[width * 0.22, width * 0.31, width * 0.47], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 1, RULE),
        ("BOX", (0, 0), (-1, -1), 1.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    _, table_h = table.wrap(width, PAGE_H)
    table.drawOn(pdf, x, PAGE_H - top - table_h)
    return top + table_h + 18


def draw_qr_placeholder(pdf, x, width):
    """Reserve the reference poster's bottom-center QR-code position."""
    top = PAGE_H - FOOTER_H - 250
    draw_top_rect(pdf, x, top, width, 232, colors.HexColor("#EAF5FC"), RULE)
    draw_top_rect(pdf, x, top, width, 42, GOLD)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(x + width / 2, PAGE_H - top - 29, "PROJECT LINK")
    qr_size = 142
    qr_x = x + (width - qr_size) / 2
    qr_top = top + 62
    draw_top_rect(pdf, qr_x, qr_top, qr_size, qr_size, colors.white, RULE)
    pdf.saveState()
    pdf.setDash(5, 4)
    pdf.setStrokeColor(MUTED)
    pdf.rect(qr_x + 8, PAGE_H - qr_top - qr_size + 8, qr_size - 16, qr_size - 16, fill=0, stroke=1)
    pdf.restoreState()
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(x + width / 2, PAGE_H - qr_top - qr_size / 2 + 4, "PLACE QR CODE")
    pdf.setFont("Helvetica", 17)
    pdf.drawCentredString(x + width / 2, PAGE_H - top - 218, "Link to the project demo or repository")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUT_PATH), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    pdf.setTitle("Photo Restoration using Digital Image Processing")
    pdf.setAuthor("Sai Chaithanya Gosula, Sai Ram Ruttala, Sai Tharun Geddam, Siva Krishna Manchineella")

    # Gold title band follows the reference poster's visual hierarchy.
    header_h = 465
    draw_top_rect(pdf, 0, 0, PAGE_W, header_h, GOLD)
    logo = OUT_DIR / "assets" / "poster_image_8.jpeg"
    pdf.drawImage(str(logo), 65, PAGE_H - 95 - 245, width=235, height=245, preserveAspectRatio=True, mask="auto")

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 75)
    pdf.drawCentredString(PAGE_W / 2 + 95, PAGE_H - 118, "PHOTO RESTORATION")
    pdf.setFont("Helvetica-Bold", 62)
    pdf.drawCentredString(PAGE_W / 2 + 95, PAGE_H - 198, "USING DIGITAL IMAGE PROCESSING")
    pdf.setFont("Helvetica", 34)
    pdf.drawCentredString(PAGE_W / 2 + 95, PAGE_H - 260, "Automated scratch detection and localized image repair")

    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawCentredString(PAGE_W / 2 + 95, PAGE_H - 324, "Sai Chaithanya Gosula (BT24ECI057)  ·  Sai Ram Ruttala (BT24ECI054)")
    pdf.drawCentredString(PAGE_W / 2 + 95, PAGE_H - 362, "Sai Tharun Geddam (BT24ECI003)  ·  Siva Krishna Manchineella (BT24ECI053)")
    pdf.setFont("Helvetica", 25)
    pdf.drawCentredString(PAGE_W / 2 + 95, PAGE_H - 413, "Indian Institute of Information Technology, Nagpur  |  Department of ECE")

    # Three-column body layout matching the reference PDF.
    xs = [MARGIN, MARGIN + COL_W + GAP, MARGIN + 2 * (COL_W + GAP)]
    for x in (xs[1] - GAP / 2, xs[2] - GAP / 2):
        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(1)
        pdf.line(x, FOOTER_H + 18, x, PAGE_H - BODY_TOP + 18)

    top1 = BODY_TOP
    top1 = draw_section(
        pdf,
        xs[0],
        top1,
        COL_W,
        "Abstract",
        [
            "Old photographs often contain scratches, cracks, and image noise. This project presents a web-based restoration workflow that detects candidate damage, builds a repair mask, and reconstructs masked regions using image inpainting.",
            "A React interface connects to a FastAPI backend. Noise removal is optional, allowing users to keep original detail when denoising is not needed.",
        ],
    )
    top1 = draw_section(
        pdf,
        xs[0],
        top1,
        COL_W,
        "Problem and Objectives",
        [
            "Physical photo damage can cross important image content, making manual repair slow and automatic restoration difficult.",
            "&#8226;&nbsp; Detect bright, line-like scratches and cracks.<br/>&#8226;&nbsp; Refine candidate pixels into a binary damage mask.<br/>&#8226;&nbsp; Repair masked pixels while limiting changes elsewhere.<br/>&#8226;&nbsp; Provide a simple upload, preview, and download workflow.",
        ],
    )
    top1 = draw_flow(pdf, xs[0], top1, COL_W)
    top1 = draw_bullets(
        pdf,
        xs[0],
        top1,
        COL_W,
        "Technology Stack",
        [
            "React frontend for image selection and result preview.",
            "FastAPI upload and PNG response endpoint.",
            "Python, OpenCV, NumPy, and Pillow for image processing.",
        ],
    )
    top1 = draw_section(
        pdf,
        xs[0],
        top1,
        COL_W,
        "Scope and Design Choices",
        [
            "The workflow targets visible, line-like scratches and cracks in a single uploaded photograph. A pixel-level damage mask limits where the repair stage changes the image.",
            "Noise removal is optional because smoothing can suppress fine texture as well as unwanted noise. Leaving it off preserves the decoded image before damage analysis.",
            "This is a classical image-processing workflow. It fills masked areas from surrounding pixels and does not infer missing scene details from a learned model.",
        ],
        style=SMALL,
        gap=5,
    )

    top2 = BODY_TOP
    top2 = draw_bullets(
        pdf,
        xs[1],
        top2,
        COL_W,
        "Methodology",
        [
            "Input images are decoded to 8-bit BGR arrays for OpenCV processing.",
            "Optional Non-Local Means (NLM) noise removal is off by default. When selected, it uses a conservative fixed strength.",
            "Crack detection combines directional brightness symmetry responses with a multi-scale ridge response.",
            "Mask refinement joins short gaps, filters candidate components by shape, thickness, and local contrast, then expands repair seams.",
            "Tharun's pipeline uses Navier&#8211;Stokes inpainting for very small masks and biharmonic inpainting for larger masks.",
        ],
    )
    top2 = draw_section(
        pdf,
        xs[1],
        top2,
        COL_W,
        "Backend and Frontend Integration",
        [
            "The browser sends a multipart image upload and an optional noise-removal flag to <b>POST /restore</b>.",
            "FastAPI validates the file, calls the root processing pipeline, encodes the returned BGR image as PNG, and streams it back to the browser.",
            "The React editor displays the original and restored images and provides a PNG download.",
        ],
    )
    top2 = draw_section_bar(pdf, xs[1], top2, COL_W, "Experiments and Results")
    setup = Paragraph(
        "Test setup: qualitative inspection of an 800 &#215; 500 portrait with a prominent vertical scratch at input, mask, overlay, and restored stages.",
        SMALL,
    )
    _, setup_h = setup.wrap(COL_W - 28, PAGE_H)
    setup.drawOn(pdf, xs[1] + 14, PAGE_H - top2 - setup_h)
    top2 += setup_h + 14
    top2 = draw_results_table(pdf, xs[1] + 14, top2, COL_W - 28)
    top2 = draw_section(
        pdf,
        xs[1],
        top2,
        COL_W,
        "Key Findings",
        [
            "Mask precision is the main quality bottleneck: texture creates false positives, while fragmented scratches are missed.",
            "Optional denoising preserves detail when the input is already clean.",
        ],
    )
    top2 = draw_section(
        pdf,
        xs[1],
        top2,
        COL_W,
        "Interpreting the Mask",
        [
            "The 6.94% value is the share of pixels marked for repair, not a detection-accuracy score. Accuracy requires a manually labeled ground-truth mask for comparison.",
            "The binary mask shows which pixels are sent to inpainting. Its overlay exposes false positives on ordinary portrait texture; unmasked scratch gaps explain damage retained in the output.",
            "Judge the restored image together with the input and mask. A smooth-looking repair alone does not confirm that the correct regions were selected.",
        ],
        style=SMALL,
        gap=5,
    )
    top2 = draw_section(
        pdf,
        xs[1],
        top2,
        COL_W,
        "Conclusion",
        [
            "The project connects browser upload and preview to a modular restoration pipeline and demonstrates the path from input image to downloadable PNG.",
            "Improving mask precision is the clearest next step because detection errors directly limit inpainting quality.",
        ],
        style=SMALL,
        gap=5,
    )

    top3 = BODY_TOP
    top3 = draw_results_figures(pdf, xs[2], top3, COL_W)
    top3 = draw_section(
        pdf,
        xs[2],
        top3,
        COL_W,
        "Limitations and Next Steps",
        [
            "Texture can be mistaken for damage, faint scratch segments can be missed, and classical inpainting cannot recover unseen details.",
            "Next: compare masks with manual annotations, reconnect scratch fragments, reduce texture false positives, and add manual mask correction.",
        ],
    )
    top3 = draw_section(
        pdf,
        xs[2],
        top3,
        COL_W,
        "References",
        [
            "[1] A. Telea, &#8220;An Image Inpainting Technique Based on the Fast Marching Method,&#8221; Journal of Graphics Tools, 2004.",
            "[2] M. Bertalmio et al., &#8220;Navier&#8211;Stokes, Fluid Dynamics, and Image and Video Inpainting,&#8221; CVPR, 2001.",
            "[3] A. Buades et al., &#8220;A Non-Local Algorithm for Image Denoising,&#8221; CVPR, 2005.",
        ],
        style=SMALL,
        gap=7,
    )

    top3 = draw_section(
        pdf,
        xs[2],
        top3,
        COL_W,
        "Visual Result Notes",
        [
            "The overlay shows the detector also selecting facial and clothing texture around the prominent vertical scratch.",
            "Missed mask pixels retain the original scratch; extra mask pixels can soften undamaged regions. This is why mask quality is central to the final result.",
        ],
        style=SMALL,
        gap=5,
    )

    draw_qr_placeholder(pdf, xs[1], COL_W)

    # Footer bar and understated document labels.
    draw_top_rect(pdf, 0, PAGE_H - FOOTER_H, PAGE_W, FOOTER_H, GOLD)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 22)
    pdf.drawString(35, 20, "IIIT Nagpur  |  ECE Department")
    pdf.drawCentredString(PAGE_W / 2, 20, "DIGITAL IMAGE PROCESSING PROJECT")
    pdf.drawRightString(PAGE_W - 35, 20, "PHOTO RESTORATION")

    print("Column bottoms (from page top):", round(top1), round(top2), round(top3))
    pdf.showPage()
    pdf.save()
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
