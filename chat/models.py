from django.db import models
from django.contrib.auth.models import User
import random
import string
import os
import time
from datetime import datetime, timedelta
from django.core.validators import FileExtensionValidator
from django.conf import settings

class Room(models.Model):
    code = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    max_members = models.PositiveSmallIntegerField(default=2)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Room expiration time")
    expiration_hours = models.PositiveSmallIntegerField(default=24, help_text="Room lifetime in hours")
    
    def __str__(self):
        return f'Room {self.code}'
    
    @classmethod
    def generate_code(cls):
        """Generate unique 6-character room code"""
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        while True:
            code = ''.join(random.choices(chars, k=6))
            if not cls.objects.filter(code=code).exists():
                return code
    
    def save(self, *args, **kwargs):
        """Override save to set expiration time"""
        if not self.expires_at and self.expiration_hours:
            from django.utils import timezone
            self.expires_at = timezone.now() + timedelta(hours=self.expiration_hours)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if room is expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def is_available(self):
        """Check if room is available for joining"""
        return self.is_active and not self.is_expired()

class RoomMember(models.Model):
    room = models.ForeignKey(Room, related_name='members', on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    avatar = models.CharField(max_length=10, default='🌹')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['room', 'name']
    
    def __str__(self):
        return f'{self.name} in {self.room.code}'

class Message(models.Model):
    room = models.ForeignKey(Room, related_name='messages', on_delete=models.CASCADE)
    sender_name = models.CharField(max_length=20)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(max_length=10, default='user', choices=[
        ('user', 'User Message'),
        ('system', 'System Message'),
    ])
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f'{self.sender_name}: {self.content[:50]}'

class Reaction(models.Model):
    message = models.ForeignKey(Message, related_name='reactions', on_delete=models.CASCADE)
    user_name = models.CharField(max_length=20)
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['message', 'user_name', 'emoji']
    
    def __str__(self):
        return f'{self.user_name} {self.emoji}'

class TypingIndicator(models.Model):
    room = models.ForeignKey(Room, related_name='typing_users', on_delete=models.CASCADE)
    user_name = models.CharField(max_length=20)
    is_typing = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['room', 'user_name']
    
    def __str__(self):
        return f'{self.user_name} typing in {self.room.code}'

class MessageRead(models.Model):
    message = models.ForeignKey(Message, related_name='read_receipts', on_delete=models.CASCADE)
    user_name = models.CharField(max_length=20)
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['message', 'user_name']
    
    def __str__(self):
        return f'{self.user_name} read message {self.message.id}'

def upload_to(instance, filename):
    """Generate unique file path for uploads"""
    # Get file extension
    file_extension = filename.split('.')[-1].lower()
    
    # Create directory based on file type
    if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        directory = 'images'
    elif file_extension in ['pdf', 'doc', 'docx', 'txt']:
        directory = 'documents'
    elif file_extension in ['mp3', 'wav', 'ogg', 'm4a', 'aac']:
        directory = 'audio'
    else:
        directory = 'other'
    
    # Generate unique filename
    timestamp = int(time.time())
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    new_filename = f"{timestamp}_{random_string}.{file_extension}"
    
    return os.path.join('chat_files', directory, new_filename)

class MessageAttachment(models.Model):
    """Model for file attachments to messages"""
    message = models.ForeignKey(Message, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(
        upload_to=upload_to,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    # Images
                    'jpg', 'jpeg', 'png', 'gif', 'webp',
                    # Documents
                    'pdf', 'doc', 'docx', 'txt',
                    # Audio
                    'mp3', 'wav', 'ogg', 'm4a', 'aac',
                    # Video (future)
                    # 'mp4', 'avi', 'mov'
                ]
            )
        ]
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=10, help_text="File extension")
    content_type = models.CharField(max_length=100, help_text="MIME type")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Message Attachment"
        verbose_name_plural = "Message Attachments"
    
    def __str__(self):
        return f"{self.original_filename} attached to message {self.message.id}"
    
    @property
    def is_image(self):
        """Check if file is an image"""
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        return self.file_type.lower() in image_extensions
    
    @property
    def is_document(self):
        """Check if file is a document"""
        doc_extensions = ['pdf', 'doc', 'docx', 'txt']
        return self.file_type.lower() in doc_extensions
    
    @property
    def is_audio(self):
        """Check if file is an audio file"""
        audio_extensions = ['mp3', 'wav', 'ogg', 'm4a', 'aac']
        return self.file_type.lower() in audio_extensions
    
    @property
    def file_size_display(self):
        """Human readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
