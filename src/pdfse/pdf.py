import fitz
from pathlib import Path
from pdfse.wordspace import Word, WordSpace


def render_pdf(pdf_path: Path) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc[0]
    dpi = 300
    zoom = dpi / 72  # 72 is the PDF standard DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")
    doc.close()
    return image_bytes


def render_pdf_text(pdf_path: Path) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc[0]

    new_doc = fitz.open()
    new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)

    text_dict: dict = page.get_text("dict") # type: ignore
    for block in text_dict["blocks"]:
        if block["type"] != 0:
            continue  # Skip not text blocks
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue

                font = span.get("font", "helv")
                size = span["size"]
                color = span.get("color", 0)
                x0, _, _, y1 = span["bbox"]
                insert_point = (x0, y1)

                new_page.insert_text(
                    insert_point,
                    text,
                    fontsize=size,
                    fontname=font,
                    color=color,
                )
    dpi = 300
    zoom = dpi / 72  # 72 is the PDF standard DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = new_page.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")
    doc.close()
    new_doc.close()
    return image_bytes

def generate_marked_image(pdf_path: Path) -> bytes:
    """
    Render the PDF with its words surrounded by red rectangles.
    """
    doc = fitz.open(pdf_path)
    page = doc[0]

    words: dict = page.get_text("words") # type: ignore
    for word in words:
        x0, y0, x1, y1, *_ = word
        bbox = fitz.Rect(x0, y0, x1, y1)
        page.draw_rect(bbox, color=(1, 0, 0), width=0.5)

    dpi = 300
    zoom = dpi / 72  # 72 is the PDF standard DPI
    mat = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")

    doc.close()
    return image_bytes


def get_pdf_wordspace(pdf_path: Path) -> WordSpace:
    """
    Create a WordSpace object from a PDF
    """
    doc = fitz.open(pdf_path)
    page = doc[0]

    page_width: int = page.rect.width
    page_height: int = page.rect.height

    words: list[Word] = []
    page_words: dict = page.get_text("words", sort=True) # type: ignore
    for word in page_words:
        x0, y0, x1, y1, text, *_ = word
        words.append(Word(text, (x0, y0, x1, y1)))

    doc.close()
    return WordSpace(words, page_width, page_height)
