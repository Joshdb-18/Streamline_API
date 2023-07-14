import os
from google_auth_oauthlib.flow import InstalledAppFlow
from django.http import JsonResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from rest_framework.permissions import IsAuthenticated
from .models import OAuthState

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "streamline.json")


def youtube_auth(request):
    # Define the OAuth 2.0 scopes required for YouTube API
    scopes = ["https://www.googleapis.com/auth/youtube.readonly"]

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
    OAuthState.objects.create(user=request.user, state=state)
    # request.session['oauth_state'] = state

    # Send the authorization url as a response to the frontend
    return JsonResponse({"url": authorization_url})


def youtube_callback(request):
    # Retrieve the state from the query parameters
    state = request.GET.get("state")

    # Retrieve the corresponding OAuthState object from the database
    try:
        oauth_state = OAuthState.objects.get(user=request.user, state=state)
    except OAuthState.DoesNotExist:
        return JsonResponse({"error": "Invalid state"})

    # Create the flow from the client secrets file
    flow = InstalledAppFlow.from_client_secrets_file(
        json_path,
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        state=state,
    )

    # Exchange the authorization code for an access token
    flow.fetch_token(
        authorization_response=request.build_absolute_uri(),
    )

    # Store the credentials in the user's database
    oauth_state = OAuthState.objects.get(user=request.user)
    credentials = flow.credentials
    oauth_state.credentials = credentials.to_json()
    oauth_state.save()
    # request.session['youtube_credentials'] = credentials.to_json()

    return JsonResponse({"success": True})


@permission_classes([IsAuthenticated])
def get_uploaded_videos(request):
    # Retrieve the OAuthState object for the current user
    oauth_state = OAuthState.objects.get(user=request.user)

    # Retrieve the stored credentials from the OAuthState object
    credentials_json = oauth_state.credentials
    credentials = Credentials.from_json(credentials_json)

    # Create the YouTube Data API client
    youtube = build("youtube", "v3", credentials=credentials)

    # Perform the API request to get the user's uploaded videos
    response = youtube.videos().list(part="snippet", mine=True).execute()

    # Extract the relevant data from the response
    videos = response["items"]

    return JsonResponse({"videos": videos})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_video(request):
    # Retrieve the stored credentials from the user database
    oauth_state = OAuthState.objects.get(user=request.user)

    # Retrieve the stored credentials from the OAuthState object
    credentials_json = oauth_state.credentials
    credentials = Credentials.from_json(credentials_json)

    # Create the YouTube Data API client
    youtube = build("youtube", "v3", credentials=credentials)

    # Get the video details from the request
    title = request.data.get("title")
    description = request.data.get("description")
    video_data = request.FILES.get("video")
    privacy_status = request.data.get("privacy_status")

    # Create a video resource
    video = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": privacy_status},
    }

    # Upload the video
    media_body = MediaIoBaseUpload(
        io.BytesIO(video_data.read()), chunksize=-1, resumable=True
    )
    insert_request = youtube.videos().insert(
        part="snippet,status", body=video, media_body=media_body
    )
    response = insert_request.execute()

    # Return the uploaded video details
    video_id = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    video_details = {"video_id": video_id, "video_url": video_url}

    return JsonResponse(video_details)
