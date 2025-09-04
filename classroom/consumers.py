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

# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class StorybookConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.storybook_id = self.scope["url_route"]["kwargs"]["storybook_id"]
        self.group_name = f"storybook_{self.storybook_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # รับทุก event มาจาก group_send ผ่าน type="send_generic"
    async def send_generic(self, event):
        data = event.get("data", {})
        # data ต้องมี key "evt" เสมอ (scene_status / scene_update / story_status)
        await self.send(text_data=json.dumps(data))


# classroom/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils.timezone import localtime, now
from django.contrib.auth import get_user_model
from .models import Storybook, Comment

User = get_user_model()

def _best_avatar_url(user):
    prof = getattr(user, "profile", None)
    if prof and getattr(prof, "profile_picture", None):
        try: return prof.profile_picture.url
        except Exception: pass
    url = getattr(prof, "avatar_url", None)
    if url: return url
    if getattr(user, "profile_picture", None):
        try: return user.profile_picture.url
        except Exception: pass
    url = getattr(user, "avatar_url", None)
    if url: return url
    return None

class CommentConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.storybook_id = self.scope["url_route"]["kwargs"]["storybook_id"]
        self.group_name = f"comments_{self.storybook_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        history = await self._get_recent(self.storybook_id)
        await self.send_json({"event": "init_comments", "data": history})

    async def receive_json(self, content, **kwargs):
        t = content.get("type")
        user = self.scope.get("user")
        if isinstance(user, AnonymousUser):
            return

        if t == "create":
            text = (content.get("message") or "").strip()
            if not text:
                return
            data = await self._create_and_serialize(user.id, self.storybook_id, text)
            await self.channel_layer.group_send(self.group_name, {"type": "comment.created", **data})
            return

        if t == "update":
            cid = content.get("id")
            text = (content.get("message") or "").strip()
            if not cid or not text:
                return
            data = await self._update_and_serialize(user.id, cid, text)
            if data:
                await self.channel_layer.group_send(self.group_name, {"type": "comment.updated", **data})
            return

        if t == "delete":
            cid = content.get("id")
            if not cid:
                return
            data = await self._delete_and_serialize(user.id, cid)
            if data:
                await self.channel_layer.group_send(self.group_name, {"type": "comment.deleted", **data})
            return

    # ---- group handlers ----
    async def comment_created(self, event):
        await self.send_json({"event": "comment", "data": event})

    async def comment_updated(self, event):
        await self.send_json({"event": "updated", "data": event})

    async def comment_deleted(self, event):
        await self.send_json({"event": "deleted", "data": event})

    # ---- helpers ----
    @sync_to_async
    def _create_and_serialize(self, user_id, storybook_id, message):
        user = User.objects.get(pk=user_id)
        sb = Storybook.objects.get(pk=storybook_id)
        c = Comment.objects.create(storybook=sb, author=user, message=message)
        return self._serialize_comment(c)

    @sync_to_async
    def _update_and_serialize(self, user_id, comment_id, message):
        try:
            c = Comment.objects.select_related("author", "storybook").get(pk=comment_id)
        except Comment.DoesNotExist:
            return None
        if not self._can_edit(User.objects.get(pk=user_id), c):
            return None
        c.message = message
        c.edited_at = now()
        c.save(update_fields=["message", "edited_at"])
        return self._serialize_comment(c)

    @sync_to_async
    def _delete_and_serialize(self, user_id, comment_id):
        try:
            c = Comment.objects.select_related("author", "storybook").get(pk=comment_id)
        except Comment.DoesNotExist:
            return None
        u = User.objects.get(pk=user_id)
        if not self._can_delete(u, c):
            return None
        # soft delete
        c.is_deleted = True
        c.deleted_at = now()
        c.deleted_by = u
        c.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])
        return self._serialize_comment(c)

    @sync_to_async
    def _get_recent(self, storybook_id, limit=100):
        qs = (Comment.objects
              .filter(storybook_id=storybook_id)
              .select_related("author")
              .order_by("-created_at")[:limit])
        out = [self._serialize_comment(c) for c in qs]
        return list(reversed(out))  # ส่งเก่า->ใหม่; ฝั่ง JS จะ prepend เพื่อให้ใหม่อยู่บน

    def _serialize_comment(self, c: Comment):
        u = c.author
        return {
            "id": c.id,
            "author_id": u.id,
            "author": u.get_full_name() or getattr(u, "email", "ผู้ใช้"),
            "avatar_url": _best_avatar_url(u),
            "message": c.message,
            "created_at": localtime(c.created_at).strftime("%H:%M น. %d %B %Y"),
            "edited": bool(c.edited_at),
            "is_deleted": bool(c.is_deleted),
        }

    def _can_edit(self, user, c: Comment):
        # คนเขียน, เจ้าของ storybook, staff/superuser
        return (c.author_id == user.id) or (c.storybook.user_id == user.id) or user.is_staff or user.is_superuser

    def _can_delete(self, user, c: Comment):
        # ลบได้เหมือน edit
        return self._can_edit(user, c)
