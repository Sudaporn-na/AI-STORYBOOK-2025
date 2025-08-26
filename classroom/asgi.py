# asgi.py
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
import classroom.routing  #routing ของ Channels

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'classroom_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            classroom.routing.websocket_urlpatterns
        )
    ),
})
