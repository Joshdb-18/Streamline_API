import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from django.http import JsonResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from .models import OAuthState

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "streamline.json")


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def youtube_auth(request):
    # Define the OAuth 2.0 scopes required for YouTube API
    scopes = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/youtube.force-ssl"]

    # Set up the OAuth 2.0 flow
    flow = InstalledAppFlow.from_client_secrets_file(
        json_path,
        scopes=scopes,
        redirect_uri="https://www.app.devnetwork.tech/user/youtube-callback",
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
        redirect_uri="https://www.app.devnetwork.tech/user/youtube-callback",
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

            privacy_status = item.get("status", {}).get("privacyStatus", "unknown")

            video_info = {
                "id": video_id,
                "link": link,
                "title": title,
                "description": description,
                "likes": likes,
                "comments": comments,
                "views": views,
                "privacyStatus": privacy_status
            }
            videos.append(video_info)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    
    return JsonResponse({"videos": videos})

