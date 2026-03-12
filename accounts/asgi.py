import os

from channels.routing import get_default_application
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# This is the default Django ASGI application
django_asgi_app = get_asgi_application()

# Import your channels routing here
from . import routing

# Your application is a ProtocolTypeRouter that will direct traffic to either
# the Django views (for http) or your channels consumers (for websockets)
application = routing.application