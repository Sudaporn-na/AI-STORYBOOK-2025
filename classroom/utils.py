from openai import OpenAI
from io import BytesIO
import PyPDF2
import json
import logging
import re

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

client = OpenAI()

# 1. แปลงข้อความเป็นเสียง 
def generate_tts_audio(text, voice="nova"):
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    return response.read()  # bytes ของไฟล์ mp3


# 2. ดึงข้อความจาก PDF ]
def extract_text_from_pdf(file_obj) -> str:
    text = ""
    reader = PyPDF2.PdfReader(file_obj)
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        logger.info(f"----- Extracted from page {page_number} -----")
        for line in page_text.splitlines():
            logger.info(line[:200])
        text += f"\n--- หน้า {page_number} ---\n" + page_text + "\n"
    logger.info("===== Total extracted text length: %d chars =====", len(text))
    return text


# 3. สรุปเป็นนิทาน 20 ฉาก 
def summarize_to_scenes(raw_text):
    system_prompt = (
        "คุณคือผู้ช่วย AI ที่เชี่ยวชาญด้านการแปลงบทเรียนยาก ๆ ให้กลายเป็นนิทานภาพที่เด็กประถมเข้าใจได้ "
        "ภารกิจของคุณคือช่วยให้เด็กอายุ 7–12 ปีเข้าใจเนื้อหาทางวิชาการ เช่น วิทยาศาสตร์ คณิตศาสตร์ ภาษาไทย "
        "ผ่านเรื่องเล่าแบบนิทานที่มีตัวละคร ฉาก และภาพที่น่าสนใจ "
        "คุณต้องแปลงเนื้อหาให้เป็นเรื่องราว 20 ของแต่ละฉากให้มีความยาวประมาณ 1 ย่อหน้า (60–80 คำ) ไม่เกิน 2 บรรทัด ใช้ภาษาที่กระชับ เหมาะสำหรับเด็กประถม และเข้าใจง่าย ฉากต่อเนื่อง โดยใช้ภาษาง่าย สนุก และเชื่อมโยงกับชีวิตจริงของเด็ก "
        "ภาพประกอบจะใช้ prompt สำหรับสร้างภาพจาก DALL·E โดยต้องระบุอย่างละเอียด ฉาก, ตัวละครในเเต่ละฉากต้องเหมือนกัน, สีสัน, อารมณ์ และ **สไตล์นิทานแนวการ์ตูน**(cartoon style, storybook illustration, soft lighting, warm colors, vibrant, highly detailed) ซึ่งต้องสื่อฉากและตัวละครให้ชัดเจน"
    )

    user_prompt = f"""
บทเรียนต้นฉบับ:
\"\"\" 
{raw_text}
\"\"\"

จุดประสงค์ของการแปลง:
- ให้เด็กเข้าใจบทเรียนยาก ๆ ผ่านเรื่องราวที่สนุก
- ใช้ตัวละคร/ฉากที่เชื่อมโยงกับชีวิตประจำวัน
- เสริมทักษะการคิด เช่น การสังเกต คำนวณ คิดวิเคราะห์ ผ่านการเล่าเรื่อง
- ให้เด็กสนุกและไม่กลัวเนื้อหาทางวิชาการ
- กรุณาเขียน "text" ของแต่ละฉากให้มีความยาวประมาณ 1 ย่อหน้า (40–60 คำ) ไม่เกิน 2 บรรทัด ใช้ภาษาที่กระชับ เหมาะสำหรับเด็กประถม และเข้าใจง่าย พร้อมเชื่อมโยงกับฉากก่อนหน้า

กรุณาสรุปบทเรียนนี้เป็น **นิทานสำหรับเด็ก 20 ฉาก** (scene 1-20) โดยมีรูปแบบ JSON ล้วน ๆ เท่านั้น
ห้ามมีคำอธิบายอื่นนอกจาก JSON

**แต่ละฉาก** ต้องประกอบด้วย:
- `"scene"`: เลขฉาก เช่น 1, 2, 3 ...
- `"text"`: เนื้อหานิทานในฉากนั้น ใช้ภาษาที่เข้าใจง่าย เหมาะกับเด็กประถม และเนื้อหาควรต่อเนื่องจากฉากก่อนหน้า โดยมีความยาวประมาณ 1 ย่อหน้า (40–60 คำ) ไม่เกิน 2 บรรทัด เพื่อให้กระชับและเหมาะสำหรับแสดงต่อฉากภาพประกอบ
- `"image_prompt"`: prompt สำหรับสร้างภาพจาก DALL·E โดยต้องระบุอย่างละเอียด: ฉาก, ตัวละคร, สีสัน, อารมณ์ และ **สไตล์นิทานแนวการ์ตูน** โดยใช้ลักษณะตัวละครหลักเหมือนเดิมทุกฉาก (ใช้ same character design as previous หรืออธิบายลักษณะซ้ำของตัวละครน้องแนน)
  (เช่น “เด็กชายกำลังถือสมุดภาพในห้องเรียนที่อบอุ่น มีครูใจดียืนข้างๆ แสงแดดส่องเข้าหน้าต่าง สไตล์การ์ตูน cartoon style, storybook illustration”)

**คำเตือนสำคัญ:
- ห้ามตอบ JSON ที่ไม่สมบูรณ์ เช่น ขาด ] หรือ " หรือ ปิดไม่ครบ
- หากฉากสุดท้ายไม่แน่ใจ ให้เว้นไว้หรือปิดด้วย []

ตัวอย่างรูปแบบ JSON:
[
  {{
    "scene": 3,
    "text": "น้องแนนเดินเข้าไปในสวนของคุณตา เธอเห็นต้นไม้ที่กำลังออกผล พร้อมกับผึ้งที่บินไปมา...",
    "image_prompt": "น้องแนน (same character design as previous) ยืนอยู่ในสวนผลไม้ที่เต็มไปด้วยต้นไม้และผึ้งบิน สไตล์การ์ตูน cartoon style, storybook illustration"
  }},
  ...
]
"""

    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )

    result_text = response.choices[0].message.content.strip()

    # ล้าง ```json หรือ ```
    if result_text.startswith("```json"):
        result_text = result_text[7:]
    elif result_text.startswith("```"):
        result_text = result_text[3:]
    if result_text.endswith("```"):
        result_text = result_text[:-3]

    logger.warning("===== JSON TAIL (last 1000 chars) =====\n%s", result_text)

    try:
        return json.loads(result_text)

    except json.JSONDecodeError as e:
        logger.warning(" JSONDecodeError: %s", str(e))
        if not result_text.endswith("]"):
            fixed = result_text.rsplit('{', 1)[0].rstrip(', \n') + "\n]"
            try:
                return json.loads(fixed)
            except Exception as e2:
                raise ValueError("แก้แล้วแต่ยังพังอยู่: " + str(e2))
        else:
            raise ValueError("ไม่สามารถแปลง JSON ได้: " + str(e))


# 4. กรองคำต้องห้ามแบบเหมารวม 
def sanitize_prompt(prompt: str) -> str:
    bad_words = [
        # คำเกี่ยวกับร่างกายและความรุนแรง
        r"อวัยวะ", r"อวัยวะเพศ", r"อวัยวะภายใน", r"นม", r"หน้าอก", r"เต้านม", r"สะโพก",
        r"เลือด", r"ตาย", r"ฆ่า", r"ตัด", r"กรีด", r"กระชาก", r"แทง", r"บีบคอ",
        r"ทะเลาะ", r"ทำร้าย", r"กระโดดจาก", r"ทรมาน",

        # คำล่อแหลม/ลามก/เพศ
        r"เปลือย", r"โป๊", r"นู้ด", r"ลามก", r"มีเพศ", r"ร่วมเพศ", r"กอด", r"จูบ",
        r"อาบน้ำ", r"ถอดเสื้อ", r"ยั่ว", r"เซ็กซี่", r"ข่มขืน", r"อนาจาร",

        # คำผิดศีลธรรม/ยาเสพติด
        r"ยาเสพติด", r"กัญชา", r"เฮโรอีน", r"เสพ", r"ดูด", r"ฉีด", r"เหล้า", r"เบียร์", r"เมา",
        r"สูบบุหรี่", r"บุหรี่", r"เครื่องดื่มแอลกอฮอล์",

        # อาวุธ/ภัย
        r"ปืน", r"มีด", r"ระเบิด", r"ควัน", r"ไฟไหม้", r"อาวุธ", r"ระเบิดนิวเคลียร์", r"สงคราม",

        # สัตว์และสิ่งไม่เหมาะสม
        r"หนอน", r"ไส้เดือน", r"แมลง", r"แมลงวัน", r"แมลงสาบ", r"ศพ", r"ผี", r"ซากศพ",

        # คำต้องห้ามทั่วไปที่มัก trigger ระบบ
        r"ทดลอง", r"การทดลอง", r"ไวรัส", r"พิษ", r"เชื้อโรค", r"ของเหลว", r"ของเหลวในร่างกาย",
        r"กระดูก", r"เนื้อ", r"คราบเลือด", r"ฆาตกร", r"การล่า", r"การล่วงละเมิด",
    ]


    filtered = []
    for pattern in bad_words:
        if re.search(pattern, prompt, flags=re.IGNORECASE):
            filtered.append(pattern)
            prompt = re.sub(pattern, "[คำปลอดภัย]", prompt, flags=re.IGNORECASE)

    if filtered:
        logger.warning(" Filtered prompt due to: %s", ", ".join(filtered))

    return prompt


#  5. สร้างภาพจาก DALL·E พร้อม fallback 
def simplify_prompt(text: str) -> str:
    """
    แปลงข้อความ text ที่ใช้ไม่ได้ มาเป็น prompt ที่ปลอดภัย
    """
    keywords = [
        "ห้องเรียน", "เด็กหญิง", "เด็กชาย", "คุณครู", "หนังสือ", "วิทยาศาสตร์", "ธรรมชาติ",
        "สนามเด็กเล่น", "แสงแดด", "สวน", "เพื่อน", "สัตว์", "ครอบครัว", "รอยยิ้ม", "ความสุข"
    ]
    found = [word for word in keywords if word in text]
    description = "และ".join(found[:2]) if found else "เด็กนักเรียนในบรรยากาศอบอุ่น"
    return f"{description} สไตล์การ์ตูน cartoon style, storybook illustration, soft lighting, happy atmosphere, child-friendly"


def generate_dalle_image(prompt: str) -> str:
    """
    สร้างภาพจาก prompt (หรือ fallback prompt ถ้า content policy reject)
    """
    safe_prompt = sanitize_prompt(prompt)
    styled_prompt = safe_prompt + ", cartoon style, storybook illustration, soft lighting, warm colors, vibrant, highly detailed, happy atmosphere, cozy, child-friendly"

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=styled_prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        return response.data[0].url

    except Exception as e:
        logger.warning("สร้างภาพจาก prompt เดิมไม่สำเร็จ: %s", str(e))

        # fallback
        fallback_prompt = simplify_prompt(prompt)
        logger.info("ใช้ fallback prompt: %s", fallback_prompt)

        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=fallback_prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )
            return response.data[0].url

        except Exception as e2:
            logger.error("fallback prompt ก็ล้มเหลว: %s", str(e2))
            return "https://yourdomain.com/static/default_image.png"


if __name__ == "__main__":
    pdf_path = "example_lesson.pdf"
    with open(pdf_path, "rb") as f:
        raw_text = extract_text_from_pdf(f)

    scenes = summarize_to_scenes(raw_text)
    logger.info("รวมทั้งหมด %d ฉาก", len(scenes))

    for scene in scenes:
        try:
            logger.info("🔹 สร้างฉากที่ %d …", scene["scene"])
            image_url = generate_dalle_image(scene["image_prompt"])
            tts_bytes = generate_tts_audio(scene["text"])

            logger.info(" ฉาก %d สร้างเสร็จ: ภาพ = %s, เสียง = %d bytes", scene["scene"], image_url, len(tts_bytes))

            # อัปโหลด Supabase หรือบันทึกที่นี่ได้

        except Exception as e:
            logger.error(" ฉาก %d มีปัญหา: %s", scene["scene"], str(e))
            continue

    logger.info(" ทุกฉากประมวลผลเสร็จสิ้น!")
