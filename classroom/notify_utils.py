# classroom/notify_utils.py
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification

def notify_user(user, *, event_type, verb, description="", target_url=""):
    notif = Notification.objects.create(
        user=user,
        user_type=getattr(user, "user_type", None),
        event_type=event_type,
        verb=verb,
        description=description,
        target_url=target_url,
    )
    # ถ้าตั้งค่า Channels + Redis จะส่ง real-time ด้วย
    try:
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"user_{user.id}",
                {"type": "notify", "payload": {
                    "id": notif.id,
                    "event_type": notif.event_type,
                    "verb": notif.verb,
                    "description": notif.description,
                    "target_url": notif.target_url,
                    "is_read": notif.is_read,
                    "created_at": notif.created_at.isoformat(),
                }}
            )
    except Exception:
        pass
    return notif
