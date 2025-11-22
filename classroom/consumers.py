# classroom/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async

from channels.generic.websocket import AsyncWebsocketConsumer

import json
from django.contrib.auth.models import AnonymousUser
from django.utils.timezone import localtime, now
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Storybook, Comment, Scene # ตรวจสอบให้แน่ใจว่า import Comment ที่มี parent_comment แล้ว


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


class StorybookConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.storybook_id = self.scope["url_route"]["kwargs"]["storybook_id"]
        self.group_name = f"storybook_{self.storybook_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # PROGRESS 
    async def send_progress(self, event):
        await self.send(text_data=json.dumps({
            "evt": "progress",
            **{k: v for k, v in event.items() if k != "type"}
        }))

    # SCENE UPDATE
    async def send_scene_update(self, event):
        await self.send(text_data=json.dumps({
            "evt": "scene_update",
            **event["data"]
        }))

    # GENERIC (fallback)
    async def send_generic(self, event):
        await self.send(text_data=json.dumps(event.get("data", {})))



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

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        t = content.get("type")
        user = self.scope.get("user")
        if isinstance(user, AnonymousUser):
            return

        if t == "create":
            text = (content.get("message") or "").strip()
            # เพิ่ม รับ parent_comment_id
            parent_id = content.get("parent_comment_id")
            
            if not text:
                return
            
            # ส่ง parent_id ไปด้วย
            data = await self._create_and_serialize(user.id, self.storybook_id, text, parent_id)
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
                # data จะมี is_deleted: True ทำให้ฝั่ง JS ลบ DOM
                await self.channel_layer.group_send(self.group_name, {"type": "comment.deleted", **data})
            return

    # ---- group handlers (เหมือนเดิม) ----
    async def comment_created(self, event):
        await self.send_json({"event": "comment", "data": event})

    async def comment_updated(self, event):
        await self.send_json({"event": "updated", "data": event})

    async def comment_deleted(self, event):
        await self.send_json({"event": "deleted", "data": event})

    # ---- helpers ----
    @sync_to_async
    # เพิ่ม parent_comment_id=None
    def _create_and_serialize(self, user_id, storybook_id, message, parent_comment_id=None):
        user = User.objects.get(pk=user_id)
        sb = Storybook.objects.get(pk=storybook_id)
        parent = None
        if parent_comment_id:
             # ตรวจสอบคอมเมนต์แม่: ต้องอยู่ใน Storybook เดียวกันและยังไม่ถูกลบ
            try:
                parent = Comment.objects.get(
                    pk=parent_comment_id, storybook=sb, is_deleted=False
                )
            except Comment.DoesNotExist:
                parent_comment_id = None # ถ้าหาไม่เจอหรือถูกลบแล้ว ก็สร้างเป็นคอมเมนต์หลัก
        
        c = Comment.objects.create(
            storybook=sb, 
            author=user, 
            message=message,
            parent_comment=parent # กำหนดคอมเมนต์แม่
        )
        return self._serialize_comment(c)

    @sync_to_async
    def _update_and_serialize(self, user_id, comment_id, message):
        try:
            # ใช้ select_related เพื่อดึง author และ storybook มาพร้อมกัน
            c = Comment.objects.select_related("author", "storybook").get(pk=comment_id, is_deleted=False)
        except Comment.DoesNotExist:
            return None
        
        u = User.objects.get(pk=user_id)
        if not self._can_edit(u, c):
            return None
            
        c.message = message
        c.edited_at = now()
        c.save(update_fields=["message", "edited_at"])
        return self._serialize_comment(c)

    @sync_to_async
    def _delete_and_serialize(self, user_id, comment_id):
        try:
            # ใช้ select_related เพื่อดึง author และ storybook มาพร้อมกัน
            c = Comment.objects.select_related("author", "storybook").get(pk=comment_id, is_deleted=False)
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
        
        # ลบคอมเมนต์ลูกทั้งหมดด้วย (Optional: หากต้องการให้การลบหลักลบลูกด้วย)
        # Comment.objects.filter(parent_comment=c).update(
        #     is_deleted=True, 
        #     deleted_at=now(), 
        #     deleted_by=u
        # )
        
        # ส่งข้อมูลกลับไป โดยมี is_deleted: True 
        return self._serialize_comment(c)

    @sync_to_async
    def _get_recent(self, storybook_id, limit=200): # เพิ่ม limit ให้เยอะขึ้นตาม frontend
        # ดึงเฉพาะคอมเมนต์หลักที่ยังไม่ถูกลบ (และคอมเมนต์ลูกที่ยังไม่ถูกลบ)
        qs = (Comment.objects
              .filter(
                  Q(storybook_id=storybook_id) & (Q(parent_comment__isnull=True) | Q(parent_comment__is_deleted=False)),
                  is_deleted=False
              )
              .select_related("author", "parent_comment")
              .order_by("-created_at")[:limit])
        
        # ต้องดึงคอมเมนต์หลักและลูกแยกกันเพื่อให้การเรียงลำดับใน JS ถูกต้อง
        top_level_comments = [c for c in qs if c.parent_comment is None]
        
        out = []
        
        # ดึง replies ทั้งหมดของ top_level comments ที่ดึงมา (ถ้าไม่ใช้ prefetch_related ใน view)
        # ใน Consumer เราจะพยายามส่งแค่ top-level ที่ไม่ถูกลบ หรือ replies ที่ไม่ถูกลบ
        # การดึง qs ทั้งหมดแล้วกรองเอาเฉพาะที่ไม่ถูกลบจะง่ายกว่า
        
        all_active_comments = [self._serialize_comment(c) for c in qs]
        
        # เราส่งทั้งหมดกลับไป โดยฝั่ง JS จะจัดเรียงเองตาม parent_comment_id
        return list(reversed(all_active_comments)) 

    def _serialize_comment(self, c: Comment):
        u = c.author
        # เพิ่ม parent_comment_id
        parent_id = c.parent_comment_id if c.parent_comment_id and not c.parent_comment.is_deleted else None

        return {
            "id": c.id,
            "author_id": u.id,
            "author": u.get_full_name() or getattr(u, "email", "ผู้ใช้"),
            "avatar_url": _best_avatar_url(u),
            "message": c.message,
            # ใช้ strftime ที่ตรงกับ JS
            "created_at": localtime(c.created_at).strftime("%H:%M น. %j %B %Y"), 
            "edited": bool(c.edited_at),
            "is_deleted": bool(c.is_deleted),
            "parent_comment_id": parent_id, # เพิ่ม parent_comment_id
        }

    def _can_edit(self, user, c: Comment):
        # คนเขียน, เจ้าของ storybook, staff/superuser
        return (c.author_id == user.id) or (c.storybook.user_id == user.id) or user.is_staff or user.is_superuser

    def _can_delete(self, user, c: Comment):
        # ลบได้เหมือน edit
        return self._can_edit(user, c)
