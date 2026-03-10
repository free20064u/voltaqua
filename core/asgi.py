import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import water.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# This router will route traffic to either the standard Django HTTP application
# or our WebSocket consumer.
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            water.routing.websocket_urlpatterns
        )
    ),
})