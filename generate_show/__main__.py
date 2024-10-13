"""Generate an episode of "Come, Follow Me with Joshua Graham"."""

import datetime
import logging
import pathlib
import shutil

import bs4
import httpx
import magentic

import generate_show.youtube
from generate_show import files
from generate_show.models import EpisodeOutline, Episode

logging.basicConfig(level=logging.INFO)

EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT = """\
You are Joshua Graham, the Burned Man, of Fallout: New Vegas fame. You have recently been called as your ward Sunday
School teacher teaching the Book of Mormon using the Come, Follow Me curriculum. Using the attached document, please
outline a podcast episode based on this week's curriculum ({curriculum_string}). 

Each segment should be about 4-5 minutes (~800-1000 words) long, including some scriptural references from the assigned
curriculum and some other connection, at least. Make as many relevant references as possible to provide commentary on.
The content should be spiritually uplifting and doctrinally sound according to the official positions of the Church of
Jesus Christ of Latter-day Saints.

Make sure to make the outline feels like it was written by you, Joshua Graham. You may include personal anecdotes or 
insights. Recall that Joshua Graham is well trainined in languages, so feel free to make language connections. The 
content should not just be generic. Please also dive into the scriptures wherever possible, providing 
doctrinally-sound commentary.
"""
assert EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT.strip()

logging.info("Fetching Joshua Graham background text...")
JOSHUA_GRAHAM_BACKGROUND_TEXT = httpx.get("https://fallout.fandom.com/wiki/Joshua_Graham?action=raw").text
assert JOSHUA_GRAHAM_BACKGROUND_TEXT.strip()

EPISODE_FLESH_OUT_GENERATION_PROMPT = """\
This is the episode outline:

```
{episode_outline}
```

Now that we have an episode outline written by you, Joshua Graham, we must flesh it out to be a podcast script. You may
include personal anecdotes or insights. The content should not just be generic. Please also dive into the scriptures 
wherever possible, providing doctrinally-sound commentary. Feel free to include spiritual insights based on linguistics
or scholarly commentary, so long as it is doctrionally sound according to the official positions of the Church of Jesus
Christ of Latter-day Saints. Feel free to use the words of modern prophets and apostles from General Conference. In all
things you say, make sure to testify of Jesus Christ and invite all to come unto Him.

Each segment should be about 4-5 minutes (~800-1000 words) long. Flesh out each segment to the specified length. Each 
one should include some scriptural references from the assigned curriculum and at least three other connections, 
perhaps from the scriptures or from General conference, or linguistically, or from your own life. Feel free to add 
content that wasn't in the outline. The content should be spiritually uplifting and doctrinally sound. Always cite 
your sources.

Feel free to break down a passage of scripture verse-by-verse or even line-by-line. The deeper and more 
profound/uplifting your message, the more engaged listeners will be, which will better accomplish your goal to invite
them to come unto Christ. **Make sure to make this personal, exactly how Joshua Graham would comment on the scriptures,
testifying of Jesus**.

The script should be fully fleshed out with exactly what the voice actor will say. This should include all text to be
read by the voice actor in each segment. Strive to be thorough in your spiritual commentary and insights.

Do not include the title of the segments in the script.

Do not include any text that isn't to be spoken in the episode (it will be read by the voice actor exactly as written).
You are permitted to use `<break time='1s'/>` to designate a break of 1s (or change 1s to any other brief time). Any 
text written in square brackets will be omitted before the voice actor sees the script, so do not include any text other
than that which should be spoken.
"""

EPISODE_SUMMARY_GENERATION_PROMPT = """\
You are Joshua Graham, the Burned Man, of Fallout: New Vegas fame. You have recently been called as your ward Sunday
School teacher teaching the Book of Mormon using the Come, Follow Me curriculum.

You have written a podcast episode based on this week's curriculum. The episode is entitled "{episode.title}". Please
generate a short, but powerful YouTube video description for this episode that will optimize for search engines and 
attract listeners to your podcast. 

The description should be about 100-200 words long and should include keywords that will help people find your podcast.
Make sure to include a call to action to subscribe to your podcast and to like the video.

This is a summary from a past episode for an example:
```
In this powerful episode of "Come, Follow Me with Joshua Graham," we delve into the cataclysmic and transformative 
events found in 3 Nephi 8-11. These chapters recount the great destruction and three days of darkness that engulfed 
the Nephites before the miraculous appearance of Jesus Christ. Through scripture, personal reflections, and insightful 
commentary, we explore how even in the darkest moments of our lives, the light of Christ can guide us to peace, healing,
and redemption.

Episode Highlights:

- The symbolic power of darkness and destruction in 3 Nephi 8 and how it mirrors the spiritual and emotional trials we \
face today.
- Christ's call to repentance and mercy as He speaks to the Nephites during the three days of darkness, urging them to \
return to Him.
- The Savior's glorious appearance to the Nephites in 3 Nephi 11, bringing light and hope after the darkness, and the \
deeply personal invitation to arise and come unto Him.
- Reflections on how the Savior's light can dispel the darkness in our own lives and how His doctrines of faith, \
repentance, and baptism offer us a path to eternal life.

Join us as we walk through these sacred chapters and find hope and strength in the words and actions of the Lord. \
Remember, His invitation to "arise and come forth" is extended to each of us. Let His light pierce your darkness and \
bring you peace.

*Scriptures Discussed:*
3 Nephi 8-11
John 8:12
Doctrine and Covenants 1:31-32
Matthew 18:3
John 16:33

Subscribe for more scripture studies and reflections on faith, redemption, and the teachings of Jesus Christ, all \
through the lens of Joshua Graham.

#BookOfMormon #JoshuaGraham #ScriptureStudy #Faith #ComeFollowMe #Fallout #3Nephi #LightInDarkness #TheBurnedMan \
#Redemption
```

This is the episode outline:
```
{episode}
```
"""


@EpisodeOutline.cache_pydantic_model
@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
    magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
    magentic.UserMessage("This is the Come, Follow Me curriculum\n\n {curriculum_text}"),
)
def generate_episode_outline(curriculum_string: str, curriculum_text: str) -> EpisodeOutline:
    """Generate an episode outline from a curriculum.

    Args:
        curriculum_string: The title of the curriculum.
        curriculum_text: The text of the curriculum.

    Returns:
        The generated episode outline.

    """


@Episode.cache_pydantic_model
@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
    magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
    magentic.UserMessage("This is the Come, Follow Me curriculum\n\n {curriculum_text}"),
    magentic.UserMessage(EPISODE_FLESH_OUT_GENERATION_PROMPT),
)
def generate_episode(curriculum_string: str, curriculum_text: str, episode_outline: EpisodeOutline) -> Episode:
    """Generate a full podcast episode from an episode outline.

    Args:
        curriculum_string: The title of the curriculum.
        curriculum_text: The text of the curriculum.
        episode_outline: The episode outline to generate the episode from.

    Returns:
        The generated episode.

    """


@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_SUMMARY_GENERATION_PROMPT),
    magentic.UserMessage("Please write the YouTube video description for the episode {episode.title}"),
)
def generate_video_description(episode: Episode) -> str:
    """Generate a video description for a podcast episode.

    Args:
        episode: The episode to generate the description for.

    Returns:
        The video description.

    """


def determine_publish_date(episode_week: str) -> datetime.datetime:
    """Determine the publish date for an episode.

    Args:
        episode_week: The week of the episode.

    Returns:
        The publish date for the episode
    """
    date_str = episode_week.split("–")[0].strip() + ", 2024"
    date = datetime.datetime.strptime(date_str, "%B %d, %Y")
    publish_date = date - datetime.timedelta(days=1)
    # Set the publish time to 6 PM UTC
    publish_date = publish_date.replace(hour=18, minute=0, second=0, microsecond=0)

    # If the publish date is in the past, then set it to an hour from now
    if publish_date < datetime.datetime.now(datetime.timezone.utc):
        publish_date = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(hours=1)

    return publish_date


if __name__ == "__main__":
    # Make sure to set the `ELEVEN_API_KEY` environment variable to your ElevenLabs API key
    # and the `OPENAI_API_KEY` environment variable to your OpenAI API key.
    # Once you have set these environment variables, you can run this script to generate a podcast episode, after
    # setting `WEEK_NUMBER` to the week number of the curriculum you want to generate an episode for.
    WEEK_NUMBER = 42
    CURRICULUM_LINK = f"https://www.churchofjesuschrist.org/study/manual/come-follow-me-for-home-and-church-book-of-mormon-2024/{WEEK_NUMBER}?lang=eng"
    OUTPUT_DIR = pathlib.Path("../episodes")

    logging.info("Fetching curriculum text")
    response = httpx.get(CURRICULUM_LINK)
    logging.info("Parsing curriculum text")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    curriculum_text = soup.find("body").get_text()
    lesson_title = soup.select(".title-number")[0].get_text()
    lesson_reference = soup.select("h1")[0].get_text()
    curriculum_text = f"{lesson_title} ({lesson_reference})"

    publish_date = determine_publish_date(lesson_title)

    input(
        'You are about to create an episode of "Come, Follow Me with Joshua Graham" for the lesson\n'
        f"\t> {lesson_title} ({lesson_reference}).\n\n"
        "Please press enter to continue..."
    )

    output_dir = OUTPUT_DIR / (lesson_reference.replace(" ", ""))
    master_dir = OUTPUT_DIR / "master"
    assert master_dir.exists()
    # Create the output directory using the master directory as a template
    if not output_dir.exists():
        logging.info("Copying master directory to output directory")
        shutil.copytree(master_dir, output_dir)

    logging.info("Generating episode outline")
    episode_outline = generate_episode_outline(lesson_reference, curriculum_text)
    logging.info(episode_outline.model_dump_json(indent=4))

    logging.info("Generating episode")
    episode = generate_episode(lesson_reference, curriculum_text, episode_outline=episode_outline)
    logging.info(episode.model_dump_json(indent=4))

    input("\n\n⚠️⚠️Please review the episode and press enter to continue.⚠️⚠️")

    logging.info("Generating audio files")
    episode.generate_audio_files(pathlib.Path(output_dir))

    logging.info("Saving video")
    episode.save_video(pathlib.Path(output_dir), lesson_reference)

    logging.info("Generating video description")
    video_description = generate_video_description(episode=episode)

    if (timestamps := (output_dir / files.TIMESTAMPS_FILENAME)).exists():
        video_description += f"\n\nTimestamps:\n{timestamps.read_text()}"

    logging.info(video_description)

    input(
        "\n\n⚠️⚠️Please review the video description.⚠️⚠️\n\nYou are about to upload this video to YouTube. Please hit "
        "enter to continue, and when prompted, authenticate with YouTube..."
    )

    logging.info("Publishing episode to YouTube")
    video_url = generate_show.youtube.publish_episode_to_youtube(
        output_dir / files.FINAL_VIDEO_FILENAME,
        episode_title=episode.title,
        scripture_reference=lesson_reference,
        video_description=video_description,
        publish_date=publish_date,
    )
    logging.info("Video published successfully: %s", video_url)
