from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from django.db.models import Avg, Count
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from .models import Storybook, StorybookRating

User = get_user_model()

class RatingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.storybook_id = int(self.scope['url_route']['kwargs']['storybook_id'])
        self.group_name = f"rating_{self.storybook_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # ส่งค่าเริ่มต้น: ค่าเฉลี่ย/จำนวน และคะแนนของผู้ใช้คนนี้
        data = await self._get_init(self.storybook_id, self.scope.get("user"))
        await self.send_json({"event": "rating_init", "data": data})

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") != "rate":
            return
        user = self.scope.get("user")
        if isinstance(user, AnonymousUser):
            return
        try:
            value = int(content.get("value"))
        except (TypeError, ValueError):
            return
        data = await self._set_rating(user.id, self.storybook_id, value)
        await self.channel_layer.group_send(self.group_name, {"type": "rating.broadcast", **data})

    async def rating_broadcast(self, event):
        await self.send_json({"event": "rating", "data": event})

    @sync_to_async
    def _get_init(self, storybook_id, user):
        sb = Storybook.objects.get(pk=storybook_id)
        agg = sb.ratings.aggregate(avg=Avg("value"), count=Count("id"))
        user_value = 0
        if user and not isinstance(user, AnonymousUser):
            user_value = (StorybookRating.objects
                          .filter(storybook=sb, user=user)
                          .values_list("value", flat=True).first() or 0)
        return {"avg": round(agg["avg"] or 0, 2), "count": agg["count"] or 0, "user_value": user_value}

    @sync_to_async
    def _set_rating(self, user_id, storybook_id, value):
        v = max(1, min(5, int(value)))
        sb = Storybook.objects.get(pk=storybook_id)
        obj, _ = StorybookRating.objects.update_or_create(
            storybook=sb, user_id=user_id, defaults={"value": v}
        )
        agg = sb.ratings.aggregate(avg=Avg("value"), count=Count("id"))
        return {"user_id": user_id, "value": obj.value,
                "avg": round(agg["avg"] or 0, 2), "count": agg["count"] or 0}
