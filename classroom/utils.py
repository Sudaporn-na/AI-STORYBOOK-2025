# utils.py 
import os
import logging
import json
import re
from io import BytesIO
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI
import PyPDF2

from google import genai
from google.genai import types

from pydub import AudioSegment

load_dotenv()


FFMPEG_BIN = os.getenv("FFMPEG_BIN", r"D:\Acer\Download\ffmpeg-8.0-full_build\ffmpeg-8.0-full_build\bin\ffmpeg.exe")
FFPROBE_BIN = os.getenv("FFPROBE_BIN", r"D:\Acer\Download\ffmpeg-8.0-full_build\ffmpeg-8.0-full_build\bin\ffprobe.exe")


AudioSegment.converter = FFMPEG_BIN
AudioSegment.ffprobe  = FFPROBE_BIN

DEFAULT_VOICE = os.getenv("GEMINI_TTS_VOICE", "Leda")
DEFAULT_LANG = os.getenv("GEMINI_TTS_LANG", "th-TH")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

client = OpenAI() # Client สำหรับ DALL·E (ตอนนี้ไม่ใช้แล้ว แต่ยังเก็บไว้)
gclient = genai.Client() # Client สำหรับ Gemini

# ฟังก์ชันช่วยเปลี่ยนความถี่เสียง
def pitch_shift(seg: AudioSegment, semitones: float) -> AudioSegment:
    new_sr = int(seg.frame_rate * (2 ** (semitones / 12)))
    shifted = seg._spawn(seg.raw_data, overrides={'frame_rate': new_sr})
    return shifted.set_frame_rate(seg.frame_rate)

def style_postprocess(mp3_bytes: bytes, *, speed=1.0, semitones=0.0, gain_db=0.0, pause_ms=0) -> bytes:
    seg = AudioSegment.from_file(BytesIO(mp3_bytes), format="mp3")
    if speed != 1.0:
        seg = seg.speedup(playback_speed=speed, chunk_size=50, crossfade=10)
    if semitones != 0.0:
        seg = pitch_shift(seg, semitones)
    if gain_db != 0.0:
        seg = seg + gain_db
    if pause_ms > 0:
        seg = seg + AudioSegment.silent(duration=pause_ms)
    buf = BytesIO()
    seg.export(buf, format="mp3", bitrate="64k")
    return buf.getvalue()

# 1 แปลงข้อความเป็นเสียง MP3 (ใช้ Gemini TTS)
def generate_tts_audio(text: str, voice_name: str = DEFAULT_VOICE, language_code: str = DEFAULT_LANG) -> bytes:
    try:
        resp = gclient.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                    ),
                    language_code=language_code,
                ),
            ),
        )
        pcm = resp.candidates[0].content.parts[0].inline_data.data
    except Exception as e:
        logger.error("TTS error: %s", e)
        raise

    audio = AudioSegment.from_raw(BytesIO(pcm), sample_width=2, frame_rate=24000, channels=1)
    buf = BytesIO()
    audio.export(buf, format="mp3", bitrate="64k")
    return buf.getvalue()

# 2 ดึงข้อความจาก PDF
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


# 3 สรุปเป็นนิทาน 20 ฉาก ใช้ Gemini 2.5 Pro 
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

**คำสั่งสำคัญ:** ก่อนเริ่มนิทาน ให้คุณสุ่มเลือก **ชื่อตัวละครหลัก (ภาษาไทย)** และ **คำอธิบายลักษณะของตัวละคร (เพศ, อายุ, ลักษณะทางกายภาพ, การแต่งกาย)** มาหนึ่งชุด และใช้ชื่อและคำอธิบายนั้นอย่างสม่ำเสมอในทุกฉาก (ทั้งในส่วน "text" และ "image_prompt")

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
- `"image_prompt"`: prompt สำหรับสร้างภาพจาก DALL·E โดยต้องระบุอย่างละเอียด: ฉาก, ตัวละคร, สีสัน, อารมณ์ และ **สไตล์นิทานแนวการ์ตูน** โดยต้องระบุชื่อและลักษณะตัวละครที่สุ่มเลือกมาในทุกฉาก และเพิ่มวลี **(same character design throughout the story)** เข้าไปเพื่อเน้นย้ำความสอดคล้อง

**คำเตือนสำคัญ:
- ห้ามตอบ JSON ที่ไม่สมบูรณ์ เช่น ขาด ] หรือ " หรือ ปิดไม่ครบ
- หากฉากสุดท้ายไม่แน่ใจ ให้เว้นไว้หรือปิดด้วย []

ตัวอย่างรูปแบบ JSON:
[
  {{
    "scene": 1,
    "text": "เด็กชายต้นกล้า (เด็กชาย, อายุ 7 ปี, ผมสีดำสั้น, สวมเสื้อยืดสีส้ม) กำลังเดินเล่นในห้องเรียนที่เต็มไปด้วยแสงแดด...",
    "image_prompt": "ต้นกล้า (เด็กชายอายุ 7 ขวบ ผมสีดำสั้น สวมเสื้อยืดสีส้ม) (same character design throughout the story) ยืนอยู่ในห้องเรียนที่เต็มไปด้วยแสงแดดอ่อนๆ สไตล์การ์ตูน cartoon style, storybook illustration"
  }},
  ...
]
"""
    
    try:
        full_prompt = f'{system_prompt}\n\n{user_prompt}'
        
        response = gclient.models.generate_content(
            model='gemini-2.5-pro',
            contents=[
                types.Content(
                    role='user', 
                    parts=[
                        types.Part.from_text(text=full_prompt)
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json" # บังคับให้ output เป็น JSON ล้วนๆ
            )
        )

        result_text = response.text.strip()
        logger.warning("===== JSON TAIL (last 1000 chars) =====\n%s", result_text)

        return json.loads(result_text)

    except json.JSONDecodeError as e:
        logger.warning(" JSONDecodeError: %s", str(e))
        if not result_text.endswith("]"): # โค้ดสำหรับแก้ไข JSON ที่ไม่สมบูรณ์
            fixed = result_text.rsplit('{', 1)[0].rstrip(', \n') + "\n]"
            try:
                return json.loads(fixed)
            except Exception as e2:
                raise ValueError("แก้แล้วแต่ยังพังอยู่: " + str(e2))
        else:
            raise ValueError("ไม่สามารถแปลง JSON ได้: " + str(e))
    except Exception as e:
        logger.error("Gemini generation error: %s", e)
        raise

# 4 กรองคำต้องห้ามแบบเหมารวม (ใช้สำหรับ DALL·E)
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


#  5 สร้างภาพจาก DALL·E พร้อม fallback แปลงข้อความ text ที่ใช้ไม่ได้ มาเป็น prompt ที่ปลอดภัย
def simplify_prompt(text: str) -> str:
    keywords = [
        "ห้องเรียน", "เด็กหญิง", "เด็กชาย", "คุณครู", "หนังสือ", "วิทยาศาสตร์", "ธรรมชาติ",
        "สนามเด็กเล่น", "แสงแดด", "สวน", "เพื่อน", "สัตว์", "ครอบครัว", "รอยยิ้ม", "ความสุข"
    ]
    found = [word for word in keywords if word in text]
    description = "และ".join(found[:2]) if found else "เด็กนักเรียนในบรรยากาศอบอุ่น"
    return f"{description} สไตล์การ์ตูน cartoon style, storybook illustration, soft lighting, happy atmosphere, child-friendly"


def generate_dalle_image(prompt: str) -> str:
    """
    ใช้ Gemini 2.5 Flash Image (2025 SDK)
    ดึงภาพแบบ raw bytes จาก inline_data.data
    """
    from .supabase_utils import upload_file_from_bytes

    safe_prompt = sanitize_prompt(prompt)
    styled_prompt = (
        safe_prompt +
        ", cartoon style, storybook illustration, warm colors, soft lighting, highly detailed"
    )

    try:
        response = gclient.models.generate_content(
            model="models/gemini-2.5-flash-image",
            contents=[styled_prompt]
        )

        # วนหาชิ้นส่วนภาพที่มี inline_data
        for part in response.parts:
            if part.inline_data:
                # ได้ raw bytes PNG
                img_bytes = part.inline_data.data  

                file_path = f"scenes/gemini25_{uuid4().hex}.png"
                return upload_file_from_bytes(img_bytes, file_path)

        raise Exception("Gemini image response has no inline_data")

    except Exception as e:
        logger.error("Gemini Image Generation Error: %s", e)

        # fallback 1×1 PNG
        BLANK = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00"
            b"\x1f\xf3\xffa\x00\x00\x00\x0cIDATx\x9cc`\xa0\x1f\x00"
            b"\x05\xfe\x02\xfe\xa7~\x81\x81\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        fallback_path = f"scenes/default_{uuid4().hex}.png"
        return upload_file_from_bytes(BLANK, fallback_path)



if __name__ == "__main__":
    pdf_path = "example_lesson.pdf"
    with open(pdf_path, "rb") as f:
        raw_text = extract_text_from_pdf(f)

    scenes = summarize_to_scenes(raw_text)
    logger.info("รวมทั้งหมด %d ฉาก", len(scenes))

    for scene in scenes:
        try:
            logger.info("สร้างฉากที่ %d …", scene["scene"])
            image_url = generate_dalle_image(scene["image_prompt"])
            tts_bytes = generate_tts_audio(scene["text"])

            logger.info(" ฉาก %d สร้างเสร็จ: ภาพ = %s, เสียง = %d bytes", scene["scene"], image_url, len(tts_bytes)) 

        except Exception as e: 
            logger.error(" ฉาก %d มีปัญหา: %s", scene["scene"], str(e))
            continue

    logger.info(" ทุกฉากประมวลผลเสร็จสิ้น!")