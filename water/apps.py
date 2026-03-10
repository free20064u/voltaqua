from django.apps import AppConfig


class WaterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'water'

    def ready(self):
        # Import and connect signals when the app is ready
        from . import signals
        signals.connect_signals()