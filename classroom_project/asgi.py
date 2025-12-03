# classroom_project/asgi.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "classroom_project.settings")
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Django สร้าง ASGI app 
django_asgi_app = get_asgi_application()
import classroom.routing # นำเข้า routing ของแอป classroom

application = ProtocolTypeRouter({ 
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(classroom.routing.websocket_urlpatterns)
    ),
})