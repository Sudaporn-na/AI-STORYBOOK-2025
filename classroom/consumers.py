from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Scene


class SceneProgressConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.storybook_id = self.scope['url_route']['kwargs']['storybook_id']
        self.room_group_name = f'storybook_{self.storybook_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # scenes กลายเป็น list ของ dict ไม่ใช่ model object
        scenes = await self.get_existing_scenes()
        for scene_dict in scenes:
            await self.send_json(scene_dict)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def send_scene_update(self, event):
        await self.send_json(event['data'])

    @sync_to_async
    def get_existing_scenes(self):
        return list(Scene.objects.filter(
            storybook_id=self.storybook_id
        ).order_by("scene_number").values(
            "scene_number", "text", "image_url", "audio_url"
        ))
