import json
from channels.generic.websocket import AsyncWebsocketConsumer


class UpdateConsumer(AsyncWebsocketConsumer):
    """
    A WebSocket consumer that handles connections and broadcasts data update messages.
    """
    async def connect(self):
        self.group_name = 'data_updates'
        # Join the group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Join user-specific group for private notifications
        if self.scope["user"].is_authenticated:
            user_group = f"user_{self.scope['user'].id}"
            await self.channel_layer.group_add(user_group, self.channel_name)
            
            # Join admin group if applicable
            if getattr(self.scope["user"], 'role', None) in ['block_admin', 'superuser']:
                await self.channel_layer.group_add('block_admins', self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if self.scope["user"].is_authenticated:
            await self.channel_layer.group_discard(f"user_{self.scope['user'].id}", self.channel_name)
            await self.channel_layer.group_discard('block_admins', self.channel_name)

    # This method is called when we receive a message from the channel group
    async def data_update(self, event):
        message = event["message"]
        # Send the message to the connected WebSocket client
        await self.send(text_data=json.dumps({
            "type": "update",
            "message": message
        }))

    # Handler for messages sent from accounts/views.py and water/signals.py
    async def broadcast_message(self, event):
        message = event["message"]
        # Send the notification to the connected WebSocket client
        await self.send(text_data=json.dumps({
            "type": "notification",
            "message": message
        }))