from PIL import Image, ImageDraw, ImageFont
import os
import uuid
import requests
from io import BytesIO
from django.conf import settings

FONT_PATH = os.path.join(settings.BASE_DIR, "classroom", "static", "fonts", "THSarabunNew.ttf")

def wrap_text_px_center(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def create_story_slide(image_url, text, width=1280, height=900):
    response = requests.get(image_url)
    base_img = Image.open(BytesIO(response.content)).convert("RGB")
    base_img = base_img.resize((width, height))

    # กล่องเล็กลง
    BOX_MARGIN_X = 100
    BOX_BOTTOM_MARGIN = 50
    BOX_HEIGHT = 140
    BOX_RADIUS = 28

    box_width = width - (BOX_MARGIN_X * 2)
    box_y_top = height - BOX_HEIGHT - BOX_BOTTOM_MARGIN
    box_y_bottom = box_y_top + BOX_HEIGHT

    overlay = Image.new("RGBA", (width, height), (0,0,0,0))
    overlay_draw = ImageDraw.Draw(overlay)

    overlay_draw.rounded_rectangle(
        [(BOX_MARGIN_X, box_y_top), (BOX_MARGIN_X + box_width, box_y_bottom)],
        radius=BOX_RADIUS,
        fill=(0,0,0,150)
    )

    base_img = Image.alpha_composite(base_img.convert("RGBA"), overlay)

    font = ImageFont.truetype(FONT_PATH, 28)
    draw = ImageDraw.Draw(base_img)

    # ตัดข้อความแบบ pixel + center align
    lines = wrap_text_px_center(text, font, box_width - 40, draw)

    # เริ่มวาดข้อความ
    text_y = box_y_top + 20  

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]

        # ตำแหน่งกึ่งกลางแนวนอน
        text_x = BOX_MARGIN_X + (box_width - line_width) // 2

        draw.text((text_x, text_y), line, font=font, fill=(255,255,255))
        text_y += bbox[3] - bbox[1] + 4   # spacing

    filename = f"/tmp/story_{uuid.uuid4().hex}.jpg"
    base_img.convert("RGB").save(filename, "JPEG", quality=95)

    return filename


# ---------------------------------------------
#   รวมสไลด์เป็น PDF
# ---------------------------------------------
def slides_to_pdf(image_files, output_path):
    imgs = [Image.open(i).convert("RGB") for i in image_files]
    imgs[0].save(output_path, save_all=True, append_images=imgs[1:])
    return output_path
