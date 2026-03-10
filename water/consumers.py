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
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # This method is called when we receive a message from the channel group
    async def data_update(self, event):
        message = event["message"]
        # Send the message to the connected WebSocket client
        await self.send(text_data=json.dumps({
            "type": "update",
            "message": message
        }))