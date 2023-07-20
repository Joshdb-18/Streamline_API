from django.urls import path
from . import views

app_name = "youtube"

urlpatterns = [
    path('api/v1/youtube/auth/', views.youtube_auth, name='youtube_auth'),
    path('api/v1/youtube/callback', views.youtube_callback, name='youtube_callback'),
    path('api/v1/youtube/uploaded-videos/', views.get_uploaded_videos, name='get_uploaded_videos'),
    path('api/v1/youtube/liked-videos/', views.get_liked_videos, name="liked_videos"),
    path('api/v1/youtube/upload/', views.upload_video, name="credentials"),
]
