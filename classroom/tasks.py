from celery import shared_task
from .models import Storybook, Scene
from .supabase_utils import upload_file_from_url, upload_file_from_bytes
from .utils import extract_text_from_pdf, summarize_to_scenes, generate_dalle_image, generate_tts_audio
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@shared_task
def process_storybook_async(storybook_id):
    try:
        storybook = Storybook.objects.get(id=storybook_id)
        lesson_path = storybook.file.path

        # 1 ดึงเนื้อหาจาก PDF แล้วสรุปเป็นฉาก
        raw_text = extract_text_from_pdf(lesson_path)
        scenes_data = summarize_to_scenes(raw_text)

        # 2 เตรียม WebSocket Channel
        channel_layer = get_channel_layer()

        # 3 วนลูปสร้างฉากทีละฉาก
        for scene_dict in scenes_data:
            scene_number = scene_dict["scene"]
            text = scene_dict["text"]
            prompt = scene_dict["image_prompt"]

            # 4 สร้างภาพจาก DALL·E และอัปโหลด
            dalle_url = generate_dalle_image(prompt)
            supabase_image_url = upload_file_from_url(
                dalle_url,
                f"scenes/storybook_{storybook.id}_scene_{scene_number}.png"
            )

            # 5 สร้างเสียงจาก GPT-4o TTS และอัปโหลด
            audio_bytes = generate_tts_audio(text)
            supabase_audio_url = upload_file_from_bytes(
                audio_bytes,
                f"audios/storybook_{storybook.id}_scene_{scene_number}.mp3"
            )

            # 6 บันทึก Scene ลงฐานข้อมูล (commit ทันที) ไม่ต้องรอให้สร้างครบ 20 ฉาก
            Scene.objects.create(
                storybook=storybook,
                scene_number=scene_number,
                text=text,
                image_prompt=prompt,
                image_url=supabase_image_url,
                audio_url=supabase_audio_url
            )

            # 7 ส่ง WebSocket แจ้ง browser ให้แสดงฉากนี้ทันที
            async_to_sync(channel_layer.group_send)(
                f'storybook_{storybook.id}',
                {
                    'type': 'send_scene_update',
                    'data': {
                        'scene_number': scene_number,
                        'text': text,
                        'image_url': supabase_image_url,
                        'audio_url': supabase_audio_url
                    }
                }
            )

        # 8 หลังจากครบทุกฉาก ตั้งสถานะว่าพร้อมใช้งาน
        storybook.is_ready = True
        storybook.save()

    except Exception as e:
        # กรณี error ระหว่างสร้าง
        storybook = Storybook.objects.filter(id=storybook_id).first()
        if storybook:
            storybook.is_failed = True
            storybook.save()
        raise e


# # tasks.py
# from celery import shared_task
# from django.db import transaction
# from .models import Storybook, Scene
# from .supabase_utils import upload_file_from_url, upload_file_from_bytes
# from .utils import extract_text_from_pdf, summarize_to_scenes, generate_dalle_image, generate_tts_audio
# from channels.layers import get_channel_layer
# from asgiref.sync import async_to_sync
# import logging

# logger = logging.getLogger(__name__)

# def _send_ws(group, evt, payload):
#     """Helper ส่ง event ไปยัง WebSocket"""
#     channel_layer = get_channel_layer()
#     async_to_sync(channel_layer.group_send)(
#         group,
#         {
#             "type": "send_generic",  # ให้ Consumer ตัวเดียวรับทุกชนิด
#             "data": { "evt": evt, **payload }
#         }
#     )

# @shared_task
# def process_storybook_async(storybook_id: int):
#     group = f"storybook_{storybook_id}"

#     storybook = Storybook.objects.filter(id=storybook_id).first()
#     if not storybook:
#         logger.error("Storybook %s not found", storybook_id)
#         return

#     try:
#         # 1) Extract text
#         lesson_path = storybook.file.path
#         with open(lesson_path, "rb") as f:
#             raw_text = extract_text_from_pdf(f)

#         # 2) Summarize → scenes JSON
#         scenes_data = summarize_to_scenes(raw_text) or []
#         total_scenes = len(scenes_data) or 20  # fallback 20

#         # แจ้งเริ่มงาน (รวมจำนวนฉากที่จะทำ)
#         _send_ws(group, "story_status", {"phase": "START", "total_scenes": total_scenes})

#         # 3) ทำทีละฉาก
#         for idx, scene_dict in enumerate(scenes_data, start=1):
#             scene_number = int(scene_dict.get("scene", idx))
#             text = scene_dict.get("text", "").strip()
#             prompt = scene_dict.get("image_prompt", "").strip()

#             # — START —
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "START",
#                 "message": f"กำลังสร้างฉากที่ {scene_number} (เตรียมงาน)"
#             })

#             # — GEN_IMAGE —
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "GEN_IMAGE_START",
#                 "message": f"ฉาก {scene_number}: กำลังสร้างภาพ…"
#             })
#             dalle_url = generate_dalle_image(prompt)
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "GEN_IMAGE_DONE",
#                 "message": f"ฉาก {scene_number}: สร้างภาพเสร็จ"
#             })

#             # — GEN_TTS —
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "GEN_TTS_START",
#                 "message": f"ฉาก {scene_number}: กำลังสร้างเสียง…"
#             })
#             audio_bytes = generate_tts_audio(text)
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "GEN_TTS_DONE",
#                 "message": f"ฉาก {scene_number}: สร้างเสียงเสร็จ"
#             })

#             # — UPLOAD —
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "UPLOAD_START",
#                 "message": f"ฉาก {scene_number}: กำลังอัปโหลดไฟล์…"
#             })
#             supabase_image_url = upload_file_from_url(
#                 dalle_url,
#                 f"scenes/storybook_{storybook.id}_scene_{scene_number}.png"
#             )
#             supabase_audio_url = upload_file_from_bytes(
#                 audio_bytes,
#                 f"audios/storybook_{storybook.id}_scene_{scene_number}.mp3"
#             )
#             _send_ws(group, "scene_status", {
#                 "scene_number": scene_number,
#                 "stage": "UPLOAD_DONE",
#                 "message": f"ฉาก {scene_number}: อัปโหลดเสร็จ"
#             })

#             # — SAVE + NOTIFY —
#             with transaction.atomic():
#                 Scene.objects.create(
#                     storybook=storybook,
#                     scene_number=scene_number,
#                     text=text,
#                     image_prompt=prompt,
#                     image_url=supabase_image_url,
#                     audio_url=supabase_audio_url
#                 )

#             # ส่งข้อมูลฉาก “ที่พร้อมแสดงจริง” ให้ frontend
#             _send_ws(group, "scene_update", {
#                 "scene_number": scene_number,
#                 "text": text,
#                 "image_url": supabase_image_url,
#                 "audio_url": supabase_audio_url
#             })

#         # 4) Done ทั้งเรื่อง
#         storybook.is_ready = True
#         storybook.save(update_fields=["is_ready"])
#         _send_ws(group, "story_status", {"phase": "ALL_DONE", "message": "สร้างครบแล้ว ✓"})

#     except Exception as e:
#         logger.exception("Processing failed: %s", e)
#         if storybook:
#             storybook.is_failed = True
#             storybook.save(update_fields=["is_failed"])
#         # แจ้ง error ไปหน้าเว็บด้วย
#         _send_ws(group, "story_status", {"phase": "ERROR", "message": str(e)})
#         raise
