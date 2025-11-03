import fitz

def generate_annotated_pdf(input_path: str, output_path: str) -> None:
    """
    Generates a new PDF containing just the text of the original surrounded
    by enumerated rectangles.

    :param input_path: Path to the input PDF.
    :param output_path: Path to save the output PDF.
    """
    # Open the input PDF
    doc = fitz.open(input_path)

    # Assuming single page as per problem constraints
    page = doc[0]

    # Get page dimensions
    page_rect = page.rect

    # Create a new PDF
    new_doc = fitz.open()
    new_page = new_doc.new_page(
        width=page_rect.width,
        height=page_rect.height
    )

    # Extract text structure
    text_dict = page.get_text("dict")

    # Collect all spans
    spans = []
    for block in text_dict["blocks"]:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    spans.append(span)

    # Sort spans: top-to-bottom (increasing y0), then left-to-right (increasing x0)
    spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))

    # Process each span
    for idx, span in enumerate(spans, start=1):
        bbox = fitz.Rect(span["bbox"])
        text = span["text"].strip()  # Strip to avoid extra spaces
        if not text:
            continue  # Skip empty texts

        font_size = span["size"]
        origin = fitz.Point(span["origin"])

        # Insert the text in Helvetica, same size, black color
        new_page.insert_text(origin, text, fontsize=font_size, fontname="helvetica", color=(0, 0, 0))

        # Draw red bounding box (thin line)
        new_page.draw_rect(bbox, color=(1, 0, 0), width=0.5)

        # For the enumeration label with white rectangular background
        label_fontsize = 8
        label_text = str(idx)
        label_fontname = "helvetica"
        label_color = (1, 0, 0)  # Red
        text_length = fitz.get_text_length(label_text, fontname=label_fontname, fontsize=label_fontsize)
        label_height = label_fontsize
        label_width = text_length

        # Label rect in the top-left corner
        label_rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x0 + label_width, bbox.y0 + label_height)

        # Draw white filled rectangle
        new_page.draw_rect(label_rect, color=(1, 0, 0), fill=(1, 1, 1), width=0.5)

        # Insert point: baseline at bottom with padding
        insert_x = bbox.x0
        insert_y = bbox.y0 + label_height
        insert_point = fitz.Point(insert_x, insert_y)

        # Insert the red number
        new_page.insert_text(insert_point, label_text, fontsize=label_fontsize, fontname=label_fontname, color=label_color)

    # Save the new PDF
    new_doc.save(output_path)
    new_doc.close()
    doc.close()
