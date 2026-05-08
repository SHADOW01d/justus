from django.contrib import admin
from .models import Room, Message, Reaction, RoomMember, TypingIndicator, MessageRead, MessageAttachment

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['code', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['code']

@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'avatar', 'room', 'joined_at']
    list_filter = ['room', 'joined_at']
    search_fields = ['name']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'room', 'content_preview', 'timestamp', 'message_type']
    list_filter = ['room', 'message_type', 'timestamp']
    search_fields = ['sender_name', 'content']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'

@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'message_preview', 'emoji', 'created_at']
    list_filter = ['emoji', 'created_at']
    search_fields = ['user_name']
    
    def message_preview(self, obj):
        return obj.message.content[:30] + '...' if len(obj.message.content) > 30 else obj.message.content
    message_preview.short_description = 'Message'

@admin.register(TypingIndicator)
class TypingIndicatorAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'room', 'is_typing', 'last_updated']
    list_filter = ['is_typing', 'last_updated']
    search_fields = ['user_name', 'room__code']

@admin.register(MessageRead)
class MessageReadAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'message_preview', 'read_at']
    list_filter = ['read_at']
    search_fields = ['user_name']
    
    def message_preview(self, obj):
        return obj.message.content[:30] + '...' if len(obj.message.content) > 30 else obj.message.content
    message_preview.short_description = 'Message'

@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'message', 'file_type', 'file_size_display', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['original_filename', 'message__content']
    readonly_fields = ['file_size_display', 'uploaded_at']
    
    def file_size_display(self, obj):
        return obj.file_size_display
    file_size_display.short_description = 'Size'
