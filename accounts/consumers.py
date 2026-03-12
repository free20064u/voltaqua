import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.groups_joined = []
        user = self.scope["user"]

        # Default public group
        self.groups_joined.append('public_notifications')

        if user.is_authenticated:
            # User-specific group for private messages
            self.groups_joined.append(f'user_{user.id}')

            # Role-based groups
            if user.role == 'block_admin':
                self.groups_joined.append('block_admins')
            elif user.role == 'superuser':
                self.groups_joined.append('block_admins')

        # Join all groups
        for group in self.groups_joined:
            await self.channel_layer.group_add(
                group,
                self.channel_name
            )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave all groups
        for group in getattr(self, 'groups_joined', []):
            await self.channel_layer.group_discard(
                group,
                self.channel_name
            )

    # Receive message from WebSocket and broadcast to group
    async def broadcast_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['message']))