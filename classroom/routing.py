# classroom/routing.py
from django.urls import path
from . import consumers
from .consumers_rating import RatingConsumer
# from django.urls import re_path
# from .consumers import StorybookConsumer 

websocket_urlpatterns = [
    path("ws/storybook/<int:storybook_id>/", consumers.SceneProgressConsumer.as_asgi()),
    path("ws/storybook/<int:storybook_id>/comments/", consumers.CommentConsumer.as_asgi()),  
    path("ws/storybook/<int:storybook_id>/rating/", RatingConsumer.as_asgi()),   # ใหม่
    # re_path(r"ws/storybook/(?P<storybook_id>\d+)/$", StorybookConsumer.as_asgi()),
]
