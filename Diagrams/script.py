# Fetch Images from a DOCX file and save them in chapter-wise folders based on captions.

import os
import re
from docx import Document

DOCX_FILE = "Report.docx"   # change if your filename differs
OUTPUT_DIR = "UI Output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

doc = Document(DOCX_FILE)

current_chapter = "Unsorted"
image_buffer = []

def sanitize(text):
    text = text.replace(" ", "_")
    return re.sub(r'[^\w\-_.]', '', text)

def save_buffer(caption):
    global image_buffer, current_chapter

    if not image_buffer:
        return

    caption = sanitize(caption)

    chapter_folder = os.path.join(OUTPUT_DIR, sanitize(current_chapter))

    # ensure chapter folder exists
    os.makedirs(chapter_folder, exist_ok=True)

    for idx, (image_bytes, ext) in enumerate(image_buffer, start=1):

        # if multiple images for one caption → add a,b,c
        suffix = chr(96 + idx) if len(image_buffer) > 1 else ""
        filename = f"{caption}{suffix}.{ext}"

        save_path = os.path.join(chapter_folder, filename)

        with open(save_path, "wb") as f:
            f.write(image_bytes)

    image_buffer = []


for para in doc.paragraphs:

    # Detect chapter (Heading 1)
    if para.style and para.style.name.startswith("Heading 1"):
        current_chapter = para.text.strip()
        image_buffer = []
        continue

    text = para.text.strip()

    # Detect caption (Figure 6.1 ...)
    if re.match(r'^(Figure|Fig\.?)\s+\d+(\.\d+)*', text, re.IGNORECASE):
        save_buffer(text)
        continue

    # Detect images
    for run in para.runs:
        if "graphic" in run._element.xml:
            drawing = run._element.xpath('.//a:blip')
            if drawing:
                rId = drawing[0].get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                )

                image_part = doc.part.related_parts[rId]
                image_bytes = image_part.blob
                ext = image_part.content_type.split("/")[-1]

                image_buffer.append((image_bytes, ext))


# Save remaining images
save_buffer("Uncaptioned")

print("Done! Images extracted chapter-wise.")