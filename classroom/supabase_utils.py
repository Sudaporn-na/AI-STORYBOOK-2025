import os
import time
import requests
from uuid import uuid4
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "storybook")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def guess_mime_type(filename):
    if filename.endswith(".png"):
        return "image/png"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    elif filename.endswith(".mp3"):
        return "audio/mpeg"
    elif filename.endswith(".wav"):
        return "audio/wav"
    else:
        return "application/octet-stream"


def upload_file_from_bytes(file_bytes: bytes, dest_path: str, max_retries=3, retry_delay=5) -> str:
    """
    อัปโหลดไฟล์จาก bytes ไปยัง Supabase Storage พร้อม retry หากเกิด timeout
    """
    file_name = f"{uuid4().hex}_{os.path.basename(dest_path)}"
    final_path = f"{os.path.dirname(dest_path)}/{file_name}"
    mime_type = guess_mime_type(final_path)
    headers = {"content-type": str(mime_type)}

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f" Uploading to Supabase: {final_path} (attempt {attempt})")
            res = supabase.storage.from_(SUPABASE_BUCKET).upload(
                final_path,
                file_bytes,
                file_options=headers
            )
            if isinstance(res, dict) and res.get("error"):
                raise Exception(res["error"])
            return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{final_path}"

        except Exception as e:
            logger.warning(f" Upload failed on attempt {attempt}: {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Upload failed after {max_retries} attempts: {final_path}")
            time.sleep(retry_delay)


def upload_file_from_url(file_url: str, dest_path: str, timeout=30) -> str:
    """
    ดาวน์โหลดไฟล์จาก URL แล้วอัปโหลดไปยัง Supabase Storage พร้อม timeout
    """
    try:
        response = requests.get(file_url, timeout=timeout)
        response.raise_for_status()
        file_bytes = response.content
        return upload_file_from_bytes(file_bytes, dest_path)
    except requests.Timeout:
        logger.error(f" Download from URL timed out: {file_url}")
        raise
    except requests.RequestException as e:
        logger.error(f" Failed to download file from: {file_url} ({e})")
        raise
