from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Route WebSocket connections to the UpdateConsumer
    re_path(r'ws/updates/$', consumers.UpdateConsumer.as_asgi()),
]