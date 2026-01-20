"""
YouTube Data API video uploader.
Replaces Selenium-based upload with official API.
"""

import os
import pickle
import http.client
import httplib2
import random
import time

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# OAuth 2.0 scopes required for uploading videos and thumbnails
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# Retry settings for resumable uploads
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
                        http.client.IncompleteRead, http.client.ImproperConnectionState,
                        http.client.CannotSendRequest, http.client.CannotSendHeader,
                        http.client.ResponseNotReady, http.client.BadStatusLine)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


class YouTubeUploader:
    """Uploads videos to YouTube using the Data API."""

    def __init__(self, credentials_path: str = None):
        """
        Initialize the uploader.

        Args:
            credentials_path: Path to directory containing client_secrets.json
                            and where token.pickle will be stored.
                            Defaults to project root.
        """
        if credentials_path is None:
            credentials_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        self.credentials_path = credentials_path
        self.client_secrets_file = os.path.join(credentials_path, "client_secrets.json")
        self.token_file = os.path.join(credentials_path, "token.pickle")
        self.youtube = None

    def authenticate(self) -> None:
        """
        Authenticate with YouTube API using OAuth 2.0.

        On first run, opens browser for authorization.
        Subsequent runs use saved token.
        """
        credentials = None

        # Load existing token if available
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as token:
                credentials = pickle.load(token)

        # Refresh or get new credentials if needed
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"Missing {self.client_secrets_file}\n\n"
                        "To set up YouTube API:\n"
                        "1. Go to https://console.cloud.google.com/\n"
                        "2. Create a project and enable 'YouTube Data API v3'\n"
                        "3. Go to Credentials > Create Credentials > OAuth client ID\n"
                        "4. Choose 'Desktop app' as application type\n"
                        "5. Download the JSON file and save it as 'client_secrets.json'\n"
                        f"   in: {self.credentials_path}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, SCOPES
                )
                credentials = flow.run_local_server(port=0)

            # Save credentials for future runs
            with open(self.token_file, "wb") as token:
                pickle.dump(credentials, token)

        self.youtube = build("youtube", "v3", credentials=credentials)
        print("YouTube API authenticated successfully.")

    def upload_video(
        self,
        player_name: str,
        away_team: str,
        home_team: str,
        title: str,
        game_date: str,
        build_path: str,
        description: str = None,
        tags: list = None,
        category_id: str = "17",  # Sports category
        privacy_status: str = "public",
    ) -> str:
        """
        Upload a video to YouTube.

        Args:
            player_name: Player's name (used for file path and tags).
            away_team: Away team name.
            home_team: Home team name.
            title: Video title.
            game_date: Game date string for file path.
            build_path: Base build directory path.
            description: Video description. Auto-generated if not provided.
            tags: List of tags. Auto-generated if not provided.
            category_id: YouTube category ID (17 = Sports).
            privacy_status: 'public', 'private', or 'unlisted'.

        Returns:
            Video ID of the uploaded video.
        """
        if self.youtube is None:
            self.authenticate()

        video_path = f"{build_path}/{game_date}/{player_name}/{player_name}.mp4"
        thumbnail_path = f"{build_path}/{game_date}/{player_name}/thumbnail.png"

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Generate default description if not provided
        if description is None:
            description = (
                f"{player_name} highlights from {away_team} @ {home_team}\n\n"
                f"#{player_name.replace(' ', '')} #{away_team} #{home_team} "
                f"#NBA #Basketball #Highlights"
            )

        # Generate default tags if not provided
        if tags is None:
            tags = [
                player_name,
                player_name.replace(" ", ""),
                away_team,
                home_team,
                "NBA",
                "Basketball",
                "Highlights",
                "NBA Highlights",
                f"{player_name} Highlights",
            ]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Create resumable upload
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024,  # 1MB chunks
        )

        request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        print(f"Uploading video: {title}")
        video_id = self._resumable_upload(request)

        if video_id:
            print(f"Video uploaded successfully. ID: {video_id}")

            # Upload thumbnail if it exists
            if os.path.exists(thumbnail_path):
                self._upload_thumbnail(video_id, thumbnail_path)

            print(f"Video URL: https://www.youtube.com/watch?v={video_id}")

        return video_id

    def _resumable_upload(self, request) -> str:
        """
        Execute resumable upload with retry logic.

        Args:
            request: YouTube API insert request.

        Returns:
            Video ID if successful, None otherwise.
        """
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"  Upload progress: {progress}%")
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    error = f"HTTP error {e.resp.status}: {e.content}"
                else:
                    raise
            except RETRIABLE_EXCEPTIONS as e:
                error = str(e)

            if error:
                retry += 1
                if retry > MAX_RETRIES:
                    print(f"Upload failed after {MAX_RETRIES} retries.")
                    return None

                sleep_seconds = random.random() * (2 ** retry)
                print(f"  Retry {retry}/{MAX_RETRIES} after {sleep_seconds:.1f}s: {error}")
                time.sleep(sleep_seconds)
                error = None

        return response.get("id") if response else None

    def _upload_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """
        Upload custom thumbnail for a video.

        Args:
            video_id: YouTube video ID.
            thumbnail_path: Path to thumbnail image.

        Returns:
            True if successful, False otherwise.
        """
        try:
            print(f"Uploading thumbnail...")
            media = MediaFileUpload(thumbnail_path, mimetype="image/png")
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()
            print("Thumbnail uploaded successfully.")
            return True
        except HttpError as e:
            # Custom thumbnails require channel verification
            if e.resp.status == 403:
                print("Warning: Custom thumbnails require YouTube channel verification.")
                print("  Visit: https://www.youtube.com/verify")
            else:
                print(f"Failed to upload thumbnail: {e}")
            return False


# Backwards compatibility alias
Upload_Video = YouTubeUploader
