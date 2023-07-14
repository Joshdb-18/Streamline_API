from django.urls import path
from .views import youtube_auth, youtube_callback, get_uploaded_videos

app_name = "youtube"

urlpatterns = [
    path('api/v1/youtube/auth/', youtube_auth, name='youtube_auth'),
    path('api/v1/youtube/callback', youtube_callback, name='youtube_callback'),
    path('api/v1/youtube/uploaded-videos/', get_uploaded_videos, name='get_uploaded_videos'),
]
