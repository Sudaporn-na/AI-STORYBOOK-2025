import os
from dotenv import load_dotenv
from google import genai

# โหลด .env ที่อยู่บน root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

API_KEY = os.getenv("GEMINI_API_KEY")
print("API KEY =", API_KEY)

if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=API_KEY)

print("\n=== Available Models ===")

# client.models.list() ส่งคืน Pager object ซึ่งเป็น iterable
pager = client.models.list()

# แก้ไข: วนซ้ำที่ Pager object โดยตรงเพื่อรับผลลัพธ์
for model in pager: 
    # model ในที่นี้คือ types.Model
    print("-", model.name)