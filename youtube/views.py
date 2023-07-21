import logging
import os
import tempfile
import json

from google_auth_oauthlib.flow import InstalledAppFlow
from django.http import JsonResponse
from django.core.files.uploadedfile import InMemoryUploadedFile
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from .models import OAuthState

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "Sss.json")

logger = logging.getLogger(__name__)

category_mapping = {
    "Film & Animation": "1",
    "Autos & Vehicles": "2",
    "Music": "10",
    "Pets & Animals": "15",
    "Sports": "17",
    "Travel & Events": "19",
    "Gaming": "20",
    "People & Blogs": "22",
    "Comedy": "23",
    "Entertainment": "24",
    "News & Politics": "25",
    "Howto & Style": "26",
    "Education": "27",
    "Science & Technology": "28",
    "Nonprofits & Activism": "29",
}

def get_category_id(category_name):
    """
    Get the category id based on the user's selected
    category name
    """
    return category_mapping.get(category_name)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def youtube_auth(request):
    """
    Handles user authentication
    """
    # Checks if the user has already connected their YouTube account
    if OAuthState.objects.filter(user=request.user).exists():
        custom_url = "https://app.devnetwork.tech/sites/youtube"
        # User has already connected, redirect them to a different URL
        return JsonResponse({"url": custom_url})

    # Define the OAuth 2.0 scopes required for YouTube API
    scopes = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/youtube.force-ssl"]

    # Set up the OAuth 2.0 flow
    flow = InstalledAppFlow.from_client_secrets_file(
        json_path,
        scopes=scopes,
        redirect_uri="https://app.devnetwork.tech/user/youtube-callback",
    )

    # Generate the authorization URL
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )

    # Store the state in the database
    user = request.user
    OAuthState.objects.create(user=user, state=state)
    # request.session['oauth_state'] = state

    # Send the authorization url as a response to the frontend
    return JsonResponse({"url": authorization_url})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def youtube_callback(request):
    """
    Handles callback
    """
    # Retrieve the state from the query parameters
    state = request.GET.get("state")
    code = request.GET.get("code")

    # Retrieve the corresponding OAuthState object from the database
    try:
        oauth_state = OAuthState.objects.get(user=request.user, state=state)
    except OAuthState.DoesNotExist:
        return JsonResponse({"error": "Invalid state"})

    # Create the flow from the client secrets file
    flow = InstalledAppFlow.from_client_secrets_file(
        json_path,
        scopes=["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/youtube.force-ssl"],
        state=state,
        redirect_uri="https://app.devnetwork.tech/user/youtube-callback",
    )

    # Exchange the authorization code for an access token
    temp_var = request.build_absolute_uri()
    if "http:" in temp_var:
        temp_var = "https:" + temp_var[5:]
    flow.fetch_token(
        authorization_response=temp_var,
        code=code,
    )

    # Store the credentials in the user's database
    oauth_state = OAuthState.objects.filter(user=request.user).first()
    credentials = flow.credentials

    # Check if the credentials already have a refresh token
    if not credentials.refresh_token:
        # Set the refresh token from the authorization response
        new_credentials = Credentials(
            credentials.token,
            refresh_token=flow.credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=credentials.scopes,
        )
        oauth_state.credentials = new_credentials.to_json()
        oauth_state.save()
    oauth_state.credentials = credentials.to_json()
    oauth_state.save()
    # request.session['youtube_credentials'] = credentials.to_json()

    return JsonResponse({"success": True})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_uploaded_videos(request):
    """
    Return a user videos
    """
    # Retrieve the OAuthState object for the current user
    oauth_state = OAuthState.objects.filter(user=request.user).first()

    # Retrieve the stored credentials from the OAuthState object
    credentials_json = oauth_state.credentials
    credentials_data = json.loads(credentials_json)
    credentials = Credentials.from_authorized_user_info(credentials_data)

    # Create the YouTube Data API client
    youtube = build("youtube", "v3", credentials=credentials)

    # Retrieve the user's channel ID
    channels_response = youtube.channels().list(part="id", mine=True).execute()
    channel_id = channels_response["items"][0]["id"]

    # Perform the API request to get the user's uploaded videos
    videos = []
    next_page_token = None

    while True:
        response = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            type="video",
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        # Extract relevant information from the response and append to the videos list
        for item in response["items"]:
            video_id = item["id"]["videoId"]
            link = f"https://www.youtube.com/watch?v={video_id}"
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]

            # Retrieve the video statistics to get the like count, comment count, and view count
            video_response = youtube.videos().list(
                part="statistics",
                id=video_id
            ).execute()

            statistics = video_response["items"][0]["statistics"]
            like_count = int(statistics.get("likeCount", 0))
            comment_count = int(statistics.get("commentCount", 0))
            view_count = int(statistics.get("viewCount", 0))

            video_info = {
                "id": video_id,
                "link": link,
                "title": title,
                "description": description,
                "like_count": like_count,
                "comment_count": comment_count,
                "view_count": view_count
            }
            videos.append(video_info)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return JsonResponse({"videos": videos})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_liked_videos(request):
    """
    Returns a user liked videos
    """
    # Retrieve the OAuthState object for the current user
    oauth_state = OAuthState.objects.filter(user=request.user).first()

    # Retrieve the stored credentials from the OAuthState object
    credentials_json = oauth_state.credentials
    credentials_data = json.loads(credentials_json)
    credentials = Credentials.from_authorized_user_info(credentials_data)

    # Create the YouTube Data API client
    youtube = build("youtube", "v3", credentials=credentials)

    # Perform the API request to get the user's uploaded videos
    videos = []
    next_page_token = None

    while True:
        response = youtube.videos().list(
            part="snippet, statistics",
            maxResults=50,
            myRating="like",
            pageToken=next_page_token,
        ).execute()

        # Extract relevant information from the response and append to the videos list
        for item in response["items"]:
            video_id = item["id"]
            link = f"https://www.youtube.com/watch?v={video_id}"
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            likes = item["statistics"].get("likeCount", 0)
            comments = item["statistics"].get("commentCount", 0)
            views = item["statistics"].get("viewCount", 0)


            video_info = {
                "id": video_id,
                "link": link,
                "title": title,
                "description": description,
                "likes": likes,
                "comments": comments,
                "views": views,
            }
            videos.append(video_info)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return JsonResponse({"videos": videos})


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def upload_video(request):
    """
    Enables a user to upload a vidoe directly to youtube
    """
    video_title = request.data.get('title')
    video_description = request.data.get('description')
    video_visibility = request.data.get('visibility')
    video_category = request.data.get('category')
    video_location = request.FILES.get('video')
    video_made_for_kids = request.data.get('made_for_kids', False)

    category_id = get_category_id(video_category)

    # Retrieve the OAuthState object for the current user
    oauth_state = OAuthState.objects.filter(user=request.user).first()

    # Retrieve the stored credentials from the OAuthState object
    credentials_json = oauth_state.credentials
    credentials_data = json.loads(credentials_json)
    credentials = Credentials.from_authorized_user_info(credentials_data)

    # Create the YouTube Data API client
    youtube = build("youtube", "v3", credentials=credentials)
    # Create a temporary file to save the video content
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        for chunk in video_location.chunks():
            temp_file.write(chunk)
        temp_file_path = temp_file.name

    try:
        if video_location:
            media = MediaFileUpload(
                    temp_file_path,
                    chunksize=-1,
                    resumable=True
                )
            response = youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": video_title,
                        "description": video_description,
                        "categoryId": category_id,
                        "defaultLanguage": "en",
                        "defaultAudioLanguage": "en"
                    },
                    "status": {
                        "privacyStatus": video_visibility,
                        "selfDeclaredMadeForKids": video_made_for_kids
                    }
                },
                media_body=media
            ).execute()

            # Video upload successful, return True
            return Response({"success": True})
        else:
            # Video file not found in request, return error
            return Response({"error": "Video file not found in the request."}, status=400)
    except Exception as e:
        # Video upload failed, return error message or additional details
        logger.error(str(e))
        return Response({"success": False})
    finally:
        # Delete the temporary file
        os.remove(temp_file_path)
