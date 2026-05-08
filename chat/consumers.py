import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Message, Reaction, RoomMember

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'chat_{self.room_code}'
        
        # Get user info from session (set by Django views)
        self.user_name = self.scope['session'].get('user_name', 'Anonymous')
        self.user_avatar = self.scope['session'].get('user_avatar', '👤')
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Add user as room member
        await self.add_room_member()
        
        # Notify others that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'name': self.user_name,
                'avatar': self.user_avatar
            }
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')
        
        if message_type == 'message':
            await self.handle_message(data)
        elif message_type == 'reaction':
            await self.handle_reaction(data)
        elif message_type == 'typing':
            await self.handle_typing(data)
    
    async def handle_message(self, data):
        message_data = data['message']
        text = message_data.get('text', '')
        timestamp = message_data.get('timestamp')
        
        if not text.strip():
            return
        
        # Save message to database
        message_obj = await self.save_message(text, timestamp)
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'text': text,
                    'timestamp': timestamp,
                    'sender_name': self.user_name,
                    'message_id': message_obj.id
                }
            }
        )
    
    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        
        # Send typing indicator to room group (excluding sender)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'is_typing': is_typing,
                'name': self.user_name
            }
        )
    
    async def handle_reaction(self, data):
        emoji = data['emoji']
        message_id = data['message_id']
        
        # Save reaction to database
        reaction = await self.save_reaction(message_id, emoji)
        
        if reaction:
            # Send reaction to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_reaction',
                    'emoji': emoji,
                    'user_name': self.user_name,
                    'message_id': message_id,
                    'reaction_id': reaction.id
                }
            )
    
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def chat_reaction(self, event):
        # Send reaction to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'emoji': event['emoji'],
            'user_name': event['user_name'],
            'message_id': event['message_id'],
            'reaction_id': event['reaction_id']
        }))
    
    async def typing_indicator(self, event):
        # Send typing indicator to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'is_typing': event['is_typing'],
            'name': event['name']
        }))
    
    async def user_joined(self, event):
        # Send user joined notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'partner_info',
            'name': event['name'],
            'avatar': event['avatar']
        }))
    
    @database_sync_to_async
    def add_room_member(self):
        try:
            room = Room.objects.get(code=self.room_code)
            RoomMember.objects.get_or_create(
                room=room,
                name=self.user_name,
                defaults={'avatar': self.user_avatar}
            )
        except Room.DoesNotExist:
            pass
    
    @database_sync_to_async
    def save_message(self, text, timestamp):
        try:
            room = Room.objects.get(code=self.room_code)
            return Message.objects.create(
                room=room,
                sender_name=self.user_name,
                content=text,
                timestamp=timestamp
            )
        except Room.DoesNotExist:
            return None
    
    @database_sync_to_async
    def save_reaction(self, message_id, emoji):
        try:
            message = Message.objects.get(id=message_id)
            reaction, created = Reaction.objects.get_or_create(
                message=message,
                user_name=self.user_name,
                emoji=emoji
            )
            if not created:
                # Remove reaction if it already exists
                reaction.delete()
                return None
            return reaction
        except Message.DoesNotExist:
            return None
