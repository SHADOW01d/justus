from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import Room, Message, Reaction, RoomMember, TypingIndicator, MessageRead, MessageAttachment
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
import mimetypes

def splash(request):
    return render(request, 'chat/splash.html')

def room_choice(request):
    # Get user info from session
    user_name = request.session.get('user_name', '')
    user_avatar = request.session.get('user_avatar', '🌹')
    
    return render(request, 'chat/room.html', {
        'user_name': user_name,
        'user_avatar': user_avatar
    })

@csrf_exempt
def create_room(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        avatar = data.get('avatar', '🌹')
        expiration_hours = data.get('expiration_hours', 24)
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        
        # Store user info in session
        request.session['user_name'] = name
        request.session['user_avatar'] = avatar
        request.session.save()
        
        # Create room with expiration
        room = Room.objects.create(
            code=Room.generate_code(),
            expiration_hours=expiration_hours
        )
        
        # Add user as room member
        RoomMember.objects.create(room=room, name=name, avatar=avatar)
        
        return JsonResponse({
            'success': True,
            'room_code': room.code,
            'expires_at': room.expires_at.isoformat() if room.expires_at else None
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def join_room(request):
    try:
        data = json.loads(request.body)
        room_code = data.get('room_code', '').strip().upper()
        name = data.get('name', '').strip()
        avatar = data.get('avatar', '🌹')
        
        if not room_code or not name:
            return JsonResponse({'success': False, 'error': 'Room code and name are required'})
        
        # Store user info in session
        request.session['user_name'] = name
        request.session['user_avatar'] = avatar
        request.session.save()
        
        # Check if room exists and is available
        try:
            room = Room.objects.get(code=room_code)
        except Room.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid room code'})
        
        # Check if room is expired
        if not room.is_available():
            if room.is_expired():
                return JsonResponse({'success': False, 'error': 'Room has expired'})
            else:
                return JsonResponse({'success': False, 'error': 'Room is not available'})
        
        # Check if user is already a member (allow re-entry)
        existing_member = RoomMember.objects.filter(room=room, name=name).first()
        
        if existing_member:
            # User is returning - update avatar if different and allow entry
            if existing_member.avatar != avatar:
                existing_member.avatar = avatar
                existing_member.save()
            return JsonResponse({'success': True})
        
        # Check room capacity for new users
        current_members = RoomMember.objects.filter(room=room).count()
        if current_members >= room.max_members:
            return JsonResponse({'success': False, 'error': f'Room is full (max {room.max_members} people)'})
        
        # Add new user as room member
        RoomMember.objects.create(
            room=room,
            name=name,
            avatar=avatar
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def chat_screen(request, room_code):
    # Get user info from session
    user_name = request.session.get('user_name')
    user_avatar = request.session.get('user_avatar', '👤')
    
    if not user_name:
        return redirect('splash')
    
    try:
        room = Room.objects.get(code=room_code)
        
        # Add user as room member if not already
        member, created = RoomMember.objects.get_or_create(
            room=room,
            name=user_name,
            defaults={'avatar': user_avatar}
        )
        
        # If user just joined, create a system message
        if created:
            # Get existing members to notify them
            existing_members = RoomMember.objects.filter(room=room).exclude(name=user_name)
            if existing_members.exists():
                Message.objects.create(
                    room=room,
                    sender_name='System',
                    content=f'{user_name} joined the chat',
                    message_type='system'
                )
        
        return render(request, 'chat/chat_screen.html', {
            'room_code': room_code,
            'user_name': user_name,
            'user_avatar': user_avatar
        })
    except Room.DoesNotExist:
        return redirect('room_choice')

def save_session(request):
    try:
        name = request.GET.get('name', '').strip()
        avatar = request.GET.get('avatar', '🌹')
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        
        # Store user info in session
        request.session['user_name'] = name
        request.session['user_avatar'] = avatar
        request.session.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def send_message(request, room_code):
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        timestamp = data.get('timestamp')
        
        # Get user info from session
        user_name = request.session.get('user_name')
        user_avatar = request.session.get('user_avatar', '👤')
        
        if not user_name:
            return JsonResponse({'success': False, 'error': 'Not authenticated'})
        
        if not text:
            return JsonResponse({'success': False, 'error': 'Message text is required'})
        
        try:
            room = Room.objects.get(code=room_code)
            
            # Create message
            message = Message.objects.create(
                room=room,
                sender_name=user_name,
                content=text,
                timestamp=timestamp
            )
            
            return JsonResponse({'success': True, 'message_id': message.id})
            
        except Room.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Room not found'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def typing_indicator(request, room_code):
    try:
        data = json.loads(request.body)
        is_typing = data.get('is_typing', False)
        
        # Get user info from session
        user_name = request.session.get('user_name')
        
        if not user_name:
            return JsonResponse({'success': False, 'error': 'Not authenticated'})
        
        try:
            room = Room.objects.get(code=room_code)
            
            if is_typing:
                # Create or update typing indicator
                typing_obj, created = TypingIndicator.objects.update_or_create(
                    room=room,
                    user_name=user_name,
                    defaults={'is_typing': True}
                )
            else:
                # Remove typing indicator
                TypingIndicator.objects.filter(room=room, user_name=user_name).delete()
            
            return JsonResponse({'success': True})
            
        except Room.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Room not found'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def mark_read(request, room_code):
    try:
        data = json.loads(request.body)
        message_id = data.get('message_id')
        
        # Get user info from session
        user_name = request.session.get('user_name')
        
        if not user_name:
            return JsonResponse({'success': False, 'error': 'Not authenticated'})
        
        if not message_id:
            return JsonResponse({'success': False, 'error': 'Message ID is required'})
        
        try:
            room = Room.objects.get(code=room_code)
            message = Message.objects.get(id=message_id, room=room)
            
            # Don't mark own messages as read
            if message.sender_name == user_name:
                return JsonResponse({'success': True})
            
            # Create read receipt
            MessageRead.objects.get_or_create(
                message=message,
                user_name=user_name
            )
            
            return JsonResponse({'success': True})
            
        except (Room.DoesNotExist, Message.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Message not found'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def get_messages(request, room_code):
    # Get user info from session
    user_name = request.session.get('user_name')
    
    if not user_name:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        room = Room.objects.get(code=room_code)
        messages = Message.objects.filter(room=room).order_by('timestamp')
        
        # Get partner info
        members = RoomMember.objects.filter(room=room).exclude(name=user_name).first()
        partner_name = members.name if members else 'Anonymous'
        partner_avatar = members.avatar if members else '👤'
        
        # Get typing indicators
        typing_users = TypingIndicator.objects.filter(room=room, is_typing=True).exclude(user_name=user_name)
        typing_names = [typing.user_name for typing in typing_users]
        
        message_data = []
        for message in messages:
            # Get read receipts for this message
            read_by = MessageRead.objects.filter(message=message).values_list('user_name', flat=True)
            
            # Get attachments for this message
            attachments = []
            for attachment in message.attachments.all():
                attachments.append({
                    'id': attachment.id,
                    'filename': attachment.original_filename,
                    'file_type': attachment.file_type,
                    'file_size': attachment.file_size_display,
                    'is_image': attachment.is_image,
                    'file_url': attachment.file.url
                })
            
            message_data.append({
                'id': message.id,
                'text': message.content,
                'sender_name': message.sender_name,
                'timestamp': message.timestamp.isoformat(),
                'is_own': message.sender_name == user_name,
                'read_by': list(read_by),
                'formatted_time': message.timestamp.strftime('%I:%M %p').lstrip('0'),
                'attachments': attachments
            })
        
        return JsonResponse({
            'success': True,
            'messages': message_data,
            'partner_name': partner_name,
            'partner_avatar': partner_avatar,
            'typing_users': typing_names
        })
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'})

@csrf_exempt
def upload_file(request, room_code):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method allowed'})
    
    # Get user info from session
    user_name = request.session.get('user_name')
    
    if not user_name:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        room = Room.objects.get(code=room_code)
        
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file provided'})
        
        uploaded_file = request.FILES['file']
        
        # Validate file size
        if uploaded_file.size > getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024):
            return JsonResponse({'success': False, 'error': 'File too large'})
        
        # Validate file extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        allowed_extensions = getattr(settings, 'ALLOWED_UPLOAD_EXTENSIONS', [])
        
        if file_extension not in allowed_extensions:
            return JsonResponse({'success': False, 'error': 'File type not allowed'})
        
        # Create message with file attachment
        message = Message.objects.create(
            room=room,
            sender_name=user_name,
            content=f"Shared a file: {uploaded_file.name}",
            message_type='user'
        )
        
        # Create file attachment
        attachment = MessageAttachment.objects.create(
            message=message,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            file_type=file_extension,
            content_type=uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]
        )
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'attachment_id': attachment.id,
            'filename': attachment.original_filename,
            'file_type': attachment.file_type,
            'file_size': attachment.file_size_display,
            'is_image': attachment.is_image,
            'file_url': attachment.file.url
        })
        
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
