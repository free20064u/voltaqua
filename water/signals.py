from django.db.models.signals import post_save
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Bill, Payment, Apartment, Site, Meter


def get_models_to_watch():
    """Returns a list of models that should trigger a page refresh on save."""
    return [Bill, Payment, Apartment, Site, Meter]


def broadcast_data_update(sender, instance, **kwargs):
    """
    Sends a message to the 'data_updates' group when a watched model is saved.
    """
    channel_layer = get_channel_layer()
    model_name = sender._meta.verbose_name.title()

    async_to_sync(channel_layer.group_send)(
        'data_updates',
        {
            'type': 'data.update',  # This corresponds to the data_update method in the consumer
            'message': f'{model_name} data has been updated.'
        }
    )

def connect_signals():
    """Connects the post_save signal for all watched models."""
    for model in get_models_to_watch():
        post_save.connect(broadcast_data_update, sender=model, dispatch_uid=f"broadcast_update_{model.__name__}")