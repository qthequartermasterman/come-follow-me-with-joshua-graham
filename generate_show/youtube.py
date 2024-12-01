"""YouTube API functions for generating an episode of the show and uploading to YouTube."""

import datetime
import logging
import os
import pathlib
from typing import Any

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

from generate_show import curriculum

# OAuth 2.0 credentials file, obtained from Google Developer Console
CLIENT_SECRETS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)

# API scopes
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]

# API service name and version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

YOUTUBE_TAGS = [
    "comefollowme",
    "bookofmormon",
    "newtestament",
    "oldtestament",
    "bible",
    "Christian",
    "jesuschrist",
    "JoshuaGraham",
    "BookOfMormon",
    "FalloutNewVegas",
    "ScriptureStudy",
    "ComeFollowMe",
    "3Nephi",
    "FaithAndPerseverance",
    "SpiritualGuidance",
    "GospelInsights",
    "LDSFaith",
    "LightInDarkness",
    "TrialsAndFaith",
    "ChristianFaith",
    "BurnedMan",
    "OvercomingDoubt",
    "FaithInHardTimes",
    "SpiritualSurvival",
    "PersonalReflection",
    "SpiritualStrength",
    "ScriptureInsights",
    "JesusChrist",
    "SpiritualWarfare",
    "ReligiousReflection",
    "SpiritualEndurance",
    "PropheticSigns",
    "EndureToTheEnd",
    "ChristianLessons",
]

YOUTUBE_DESCRIPTION_DISCLAIMER = """\
Who is Joshua Graham?
Joshua Graham is a fictional character from the popular video game Fallout: New Vegas. Known as "The Burned Man," he \
is a former war chief turned repentant and deeply spiritual figure. This podcast uses the unique voice of Joshua \
Graham to offer scripture study and reflections, merging the character’s fictional narrative of redemption with \
profound spiritual insights.

Disclaimer:
The voice of Joshua Graham in this podcast is AI-generated and is used for storytelling and educational purposes. \
Joshua Graham is a fictional character from Fallout: New Vegas, and this content is not affiliated with or endorsed \
by Bethesda or Obsidian Entertainment. The views presented here do not necessarily reflect official doctrine or \
positions of the Church of Jesus Christ of Latter-day Saints.

Subscribe for more scripture studies and reflections on faith, redemption, and the teachings of Jesus Christ, all \
through the lens of Joshua Graham.
"""

PLAYLIST_ID = "PLtNHSwdyvlauyCDRBhCEGIU4ks1tlO4yh"


def get_authenticated_service_youtube() -> Any:
    """Get an authenticated YouTube service.

    Returns:
        The authenticated YouTube service.

    Raises:
        ValueError: If the GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.

    """
    logging.info("Authenticating with YouTube")
    if CLIENT_SECRETS_FILE is None:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
    credentials = flow.run_local_server(port=0)
    return googleapiclient.discovery.build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)


def publish_episode_to_youtube(
    video_path: pathlib.Path,
    episode_title: str,
    scripture_reference: str,
    video_description: str,
    publish_date: datetime.datetime,
) -> str:
    """Publish an episode to YouTube.

    Args:
        video_path: The path to the video file.
        episode_title: The title of the episode.
        scripture_reference: The scripture reference for the episode.
        video_description: The video description.
        publish_date: The publish date for the episode.

    Returns:
        The URL of the published video.

    """
    logging.info("Publishing episode to YouTube")
    youtube = get_authenticated_service_youtube()
    # Prepare video metadata
    request_body = {
        "snippet": {
            "title": f"{scripture_reference} | {episode_title}",
            "description": video_description,
            "tags": YOUTUBE_TAGS,
            "categoryId": "27",  # Education
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",  # Options: public, private, unlisted
            "publishAt": publish_date.isoformat(),  # Scheduled time in ISO format
        },
    }

    # Create a MediaFileUpload object
    media_file = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)

    # Execute the request to upload the video
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media_file)

    logging.info("Uploading video to YouTube")
    response = request.execute()

    # Insert the video into the playlist
    request = youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": PLAYLIST_ID,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": response["id"],
                },
            },
        },
    )
    request.execute()

    url = f"https://www.youtube.com/watch?v={response['id']}"

    logging.info("Video uploaded successfully: %s", url)

    return url


def determine_publish_date(cfm_curriculum: curriculum.ComeFollowMeCurriculum) -> datetime.datetime:
    """Determine the publish date for an episode.

    Set the publish date to 6 PM UTC the day before the curriculum start date. If the publish date is in the past, then
    set it to an hour from now (to give time to review the episode before publishing).

    Args:
        cfm_curriculum: The week of the episode.

    Returns:
        The publish date for the episode

    """
    publish_date = cfm_curriculum.start_date - datetime.timedelta(days=1)
    # Set the publish time to 6 PM UTC
    publish_date = publish_date.replace(hour=18, minute=0, second=0, microsecond=0)

    # If the publish date is in the past, then set it to an hour from now
    if publish_date.astimezone(datetime.timezone.utc) < datetime.datetime.now(datetime.timezone.utc):
        publish_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

    return publish_date
