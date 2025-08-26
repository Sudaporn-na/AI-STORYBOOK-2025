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
