from django.urls import path
from . import views

urlpatterns = [
    path('', views.splash, name='splash'),
    path('room/', views.room_choice, name='room_choice'),
    path('chat/<str:room_code>/', views.chat_screen, name='chat_screen'),
    path('create_room/', views.create_room, name='create_room'),
    path('join_room/', views.join_room, name='join_room'),
    path('get_messages/<str:room_code>/', views.get_messages, name='get_messages'),
    path('save_session/', views.save_session, name='save_session'),
    path('send_message/<str:room_code>/', views.send_message, name='send_message'),
    path('typing/<str:room_code>/', views.typing_indicator, name='typing_indicator'),
    path('mark_read/<str:room_code>/', views.mark_read, name='mark_read'),
    path('upload_file/<str:room_code>/', views.upload_file, name='upload_file'),
]
