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

        # 1 Creating prompt
        async_to_sync(channel_layer.group_send)(
            f"storybook_{storybook.id}",
            {
                "type": "send_progress",
                "status": "creating_prompt"
            }
        )

        # Extract & Summarize
        raw_text = extract_text_from_pdf(lesson_path)
        scenes_data = summarize_to_scenes(raw_text)
        total = len(scenes_data)

        # 2 Create scenes one by one 
        for idx, scene_dict in enumerate(scenes_data, start=1):

            async_to_sync(channel_layer.group_send)(
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

            # Image
            dalle_url = generate_dalle_image(prompt)
            supabase_image_url = upload_file_from_url(
                dalle_url,
                f"scenes/storybook_{storybook.id}_scene_{scene_number}.png"
            )

            # TTS Audio
            audio_bytes = generate_tts_audio(text)
            supabase_audio_url = upload_file_from_bytes(
                audio_bytes,
                f"audios/storybook_{storybook.id}_scene_{scene_number}.mp3"
            )

            # Save DB
            Scene.objects.create(
                storybook=storybook,
                scene_number=scene_number,
                text=text,
                image_prompt=prompt,
                image_url=supabase_image_url,
                audio_url=supabase_audio_url
            )

            # Send Scene Realtime
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

        # FINISHED 
        async_to_sync(channel_layer.group_send)(
            f"storybook_{storybook.id}",
            {
                "type": "send_progress",
                "status": "finished"
            }
        )

        storybook.is_ready = True
        storybook.save()

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
