# classroom_project/asgi.py
import os

# 1) ตั้งค่า settings ก่อน import อะไรที่แตะ Django models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "classroom_project.settings")

# 2) ค่อย import Django/Channels
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 3) ให้ Django สร้าง ASGI app (ตรงนี้จะ setup apps ให้เรียบร้อย)
django_asgi_app = get_asgi_application()

# 4) ตอนนี้ค่อย import routing ที่จะลากไปหา consumers/models ได้อย่างปลอดภัย
import classroom.routing

# 5) ประกอบ application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(classroom.routing.websocket_urlpatterns)
    ),
})
