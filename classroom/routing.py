# classroom/routing.py
from django.urls import path
from .consumers import StorybookConsumer, SceneProgressConsumer, CommentConsumer
from .consumers_rating import RatingConsumer
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    path("ws/storybook-progress/<int:storybook_id>/", StorybookConsumer.as_asgi()), # ใช้ตอนหน้าโหลดกำลังสร้างนิทาน
    path("ws/storybook/<int:storybook_id>/", SceneProgressConsumer.as_asgi()), # ใช้ตอนหน้า flipbook แสดงฉาก
    path("ws/storybook/<int:storybook_id>/comments/", CommentConsumer.as_asgi()), # comments
    path("ws/storybook/<int:storybook_id>/rating/", RatingConsumer.as_asgi()), # ratings
    re_path(r"ws/presence/$", consumers.PresenceConsumer.as_asgi()),
]

