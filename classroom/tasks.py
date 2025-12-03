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
        channel_layer = get_channel_layer()

        # สร้าง prompt สำหรับสรุปฉาก
        async_to_sync(channel_layer.group_send)(
            f"storybook_{storybook.id}",
            {
                "type": "send_progress",
                "status": "creating_prompt"
            }
        )

        # ดึงข้อความจาก PDF และสรุปเป็นฉาก
        # ❗ แก้: ต้อง open file ก่อนส่งเข้า extract_text_from_pdf
        with open(lesson_path, "rb") as f:
            raw_text = extract_text_from_pdf(f)

        scenes_data = summarize_to_scenes(raw_text) # ได้รายการ dict
        total = len(scenes_data) # จำนวนฉากทั้งหมด คือบังคับให้สรา้งเเค่ 20 ฉาก ใน utils.py เเล้ว len = 20

        # สร้างแต่ละฉาก
        for idx, scene_dict in enumerate(scenes_data, start=1): 

            async_to_sync(channel_layer.group_send)(  # แจ้งความคืบหน้า
                f"storybook_{storybook.id}",
                {
                    "type": "send_progress",
                    "status": "creating_scene",
                    "current": idx,
                    "total": total
                }
            )

            scene_number = scene_dict["scene"]
            text = scene_dict["text"]
            prompt = scene_dict["image_prompt"]

            # รูปภาพ (ตอนนี้ generate_dalle_image คืน Supabase URL ตรง ๆ)
            supabase_image_url = generate_dalle_image(prompt)

            # เสียง TTS
            audio_bytes = generate_tts_audio(text)
            supabase_audio_url = upload_file_from_bytes(
                audio_bytes,
                f"audios/storybook_{storybook.id}_scene_{scene_number}.mp3"
            )

            # บันทึกลงฐานข้อมูล
            Scene.objects.create(
                storybook=storybook,
                scene_number=scene_number,
                text=text,
                image_prompt=prompt,
                image_url=supabase_image_url,
                audio_url=supabase_audio_url
            )

            # ส่งข้อมูลแบบเรียลไทม์ไปยังผู้ใช้
            async_to_sync(channel_layer.group_send)(
                f"storybook_{storybook.id}",
                {
                    "type": "send_scene_update",
                    "data": {
                        "scene_number": scene_number,
                        "text": text,
                        "image_url": supabase_image_url,
                        "audio_url": supabase_audio_url
                    }
                }
            )

        # เสร็จสิ้น
        async_to_sync(channel_layer.group_send)(
            f"storybook_{storybook.id}",
            {
                "type": "send_progress",
                "status": "finished"
            }
        )

        storybook.is_ready = True
        storybook.save() # อัปเดตสถานะเป็นพร้อมใช้งาน

    except Exception as e:
        storybook = Storybook.objects.filter(id=storybook_id).first()
        if storybook:
            storybook.is_failed = True
            storybook.save()

        async_to_sync(channel_layer.group_send)(
            f"storybook_{storybook_id}",
            {
                "type": "send_progress",
                "status": "failed",
                "error": str(e)
            }
        )
        raise e