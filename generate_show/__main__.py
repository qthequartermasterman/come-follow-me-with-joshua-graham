"""Generate an episode of "Come, Follow Me with Joshua Graham"."""

import datetime
import functools
import hashlib
import logging
import multiprocessing
import pathlib
import shutil

import bs4
import httpx
import magentic
import moviepy.editor as mpy
import pydantic
import pydub
import tqdm
from typing_extensions import Callable, ParamSpec, Self, TypeVar

import generate_show.youtube
import generate_show.narration
logging.basicConfig(level=logging.INFO)

P = ParamSpec("P")
Model = TypeVar("Model", bound=pydantic.BaseModel)




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

INTRODUCTION_FILENAME = "introduction.mp3"
SEGMENT_FILENAME_TEMPLATE = "segment_{i}.mp3"
CLOSING_FILENAME = "closing.mp3"
MUSIC_FILENAME = "music.mp3"
COMPOSITE_FILENAME = "composite.mp3"
VIDEO_BACKGROUND_FILENAME = "background.png"
FINAL_VIDEO_FILENAME = "final_video.mp4"

INTRO_WITH_FADE_FILENAME = "introduction_with_fades.mp3"
OUTRO_WITH_FADE_FILENAME = "outro_with_fades.mp3"

TIMESTAMPS_FILENAME = "timestamps.txt"

INTRO_FIRST_FADE_IN_DURATION_MS = 5000
INTRO_FIRST_FADE_OUT_DURATION_MS = 3000
INTRO_FINAL_FADE_IN_START_POINT_MS = 11000
INTRO_FINAL_FADE_IN_DURATION_MS = 5000
INTRO_FINAL_FADE_OUT_DURATION_MS = 3000

OUTRO_FADE_IN_START_POINT_MS = 58000
OUTRO_FADE_IN_STARTS_BEFORE_END_MS = 2000
OUTRO_FADE_IN_DURATION_MS = 5000
OUTRO_MUSIC_STATIC_DURATION_MS = 15000
OUTRO_FADE_OUT_DURATION_MS = 5000

INTERMISSION_SILENCE_MS = 2500


def milliseconds_to_timestamps(milliseconds: int) -> str:
    """Convert milliseconds to a timestamp string.

    Args:
        milliseconds: The number of milliseconds to convert.

    Returns:
        The timestamp string in the format "mm:ss".

    """
    seconds, _ = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class Segment(pydantic.BaseModel):
    """A segment of an episode outline."""

    title: str = pydantic.Field(
        description=(
            "The title of the segment providing insight about the content of the segment. This is shown in"
            " the episode outline as a chapter heading. Do not include the scripture reference in the title. This must"
            " be less than 40 characters long."
        )
    )
    text: str = pydantic.Field(
        description=(
            "The text of the segment, focused on some passage(s) of scripture, along with commentary. The"
            " commentary may be personal insights, linguistic insights, scholarly commentary, or especially"
            " connections to General Conference addresses. The text must be doctrinally sound according to the"
            " official positions of the Church of Jesus Christ of Latter-day Saints. The text should be spiritually"
            " uplifting and testify of Jesus Christ. Each segment should be about 4-5 minutes (~800-1000 words) long."
        )
    )
    _normalize_segment = pydantic.field_validator("text")(generate_show.narration.add_pronunciation_helpers)


class EpisodeOutline(pydantic.BaseModel):
    """An outline for a podcast episode."""

    title: str = pydantic.Field(
        description=(
            "The title of the episode providing insight about the content of the episode, but is still succinct and"
            " catchy to attract listeners."
        )
    )
    introduction: str = pydantic.Field(
        description=(
            "The introduction segment of the episode which provides an insightful and spiritual opening, testifying"
            " of Jesus Christ."
        )
    )
    segments: list[Segment] = pydantic.Field(
        description=(
            "A list of the text of each content segment, each one focused on some passage(s) of scripture, along with"
            " commentary. The commentary may be personal insights, linguistic insights, scholarly commentary, or"
            " especially connections to General Conference addresses. Each segment must be doctrinally sound according"
            " to the official positions of the Church of Jesus Christ of Latter-day Saints. Each segment should be"
            " spiritually uplifting and testify of Jesus Christ. There should be between 4 to 6 segments."
        )
    )
    closing: str = pydantic.Field(
        description=(
            "The profound closing statement of the episode. It might provide a summary of the content in the episode,"
            " but it must contain major takeaways and a call to action. Encourage users to repent in some way relevant"
            " to the content of the episode and that will strengthen their relationship with Jesus Christ."
        )
    )

    @classmethod
    def cache_pydantic_model(cls: Self, func: Callable[P, Self]) -> Callable[P, Self]:
        """Cache the output of a function that returns a pydantic model.

        The cached model will be saved to a file in the .cache directory with the name of the class and a hash of the
        arguments.

        Args:
            func: The function to cache the output of.

        Returns:
            The wrapped function that caches the output.

        """

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Self:
            """Wrap the function to cache the output.

            Args:
                *args: The arguments to the function.
                **kwargs: The keyword arguments to the function.

            """
            args_hash = hashlib.sha256((str(args) + str(kwargs)).encode("utf-8")).hexdigest()[:16]
            path: pathlib.Path = pathlib.Path("../.cache") / f"{cls.__name__}-{args_hash}.json"
            if path.exists():
                logging.info("Cache hit for %s. Using cached %s", path, cls.__name__)
                return cls.model_validate_json(path.read_text())
            model = func(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(model.model_dump_json(indent=4))
            return model

        return wrapper


class Episode(EpisodeOutline):
    """A full podcast episode."""

    _normalize_introduction = pydantic.field_validator("introduction")(generate_show.narration.add_pronunciation_helpers)
    _normalize_closing = pydantic.field_validator("closing")(generate_show.narration.add_pronunciation_helpers)

    @property
    def segment_files(self) -> list[tuple[str, str]]:
        """Get the title of each segment along with the filename to save the audio to."""
        return [(segment.title, SEGMENT_FILENAME_TEMPLATE.format(i=i)) for i, segment in enumerate(self.segments)]

    @property
    def segment_text_files(self) -> list[tuple[str, str]]:
        """Get the text of each segment along with the filename to save the audio to."""
        return [(segment.text, SEGMENT_FILENAME_TEMPLATE.format(i=i)) for i, segment in enumerate(self.segments)]

    def generate_audio_files(self, output_dir: pathlib.Path) -> None:
        """Generate the audio files for the episode.

        Will not generate the audio files if they already exist.

        Args:
            output_dir: The directory to save the audio files to.

        """
        output_dir.mkdir(exist_ok=True)

        text_files = (
            [(self.introduction, INTRODUCTION_FILENAME)] + self.segment_text_files + [(self.closing, CLOSING_FILENAME)]
        )
        for text, file_name in tqdm.tqdm(text_files):
            generate_show.narration.generate_audio_file_from_text(text, output_dir / file_name)

        self.create_intro_clip_with_fades(output_dir)
        self.create_outro_clip_with_fades(output_dir)
        self.composite_audio_files(output_dir)

    def create_intro_clip_with_fades(self, output_dir: pathlib.Path) -> None:
        """Create the intro clip with fades.

        Will not create the intro clip if it already exists.

        Args:
            output_dir: The directory to save the intro clip to.

        Raises:
            ValueError: If the introduction or music clip do not exist.

        """
        final_file = output_dir / INTRO_WITH_FADE_FILENAME
        if final_file.exists():
            logging.info("Intro clip already exists. Skipping creation.")
            return

        if not (output_dir / INTRODUCTION_FILENAME).exists():
            raise ValueError("Cannot create fadein clip without an introduction")

        if not (output_dir / MUSIC_FILENAME).exists():
            raise ValueError("Cannot create fadein clip without music")

        introduction_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / INTRODUCTION_FILENAME, "mp3")
        music_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / MUSIC_FILENAME, "mp3")

        first_music_fade = (
            music_audio[: (INTRO_FIRST_FADE_IN_DURATION_MS + INTRO_FIRST_FADE_OUT_DURATION_MS)]
            .fade_in(INTRO_FIRST_FADE_IN_DURATION_MS)
            .fade_out(INTRO_FIRST_FADE_OUT_DURATION_MS)
        )
        length_of_silence = len(introduction_audio) - (INTRO_FIRST_FADE_OUT_DURATION_MS - 250)
        first_music_fade_plus_silence = first_music_fade + pydub.AudioSegment.silent(duration=length_of_silence)
        intro_start_position = len(first_music_fade_plus_silence) - len(introduction_audio)
        first_music_with_intro = first_music_fade_plus_silence.overlay(
            introduction_audio, position=intro_start_position
        )

        final_fade_in_music_clip = (
            music_audio[
                INTRO_FINAL_FADE_IN_START_POINT_MS : INTRO_FINAL_FADE_IN_START_POINT_MS
                + INTRO_FINAL_FADE_IN_DURATION_MS
                + INTRO_FINAL_FADE_OUT_DURATION_MS
            ]
            .fade_in(INTRO_FINAL_FADE_IN_DURATION_MS)
            .fade_out(INTRO_FINAL_FADE_OUT_DURATION_MS)
        )
        final_fade_clip = first_music_with_intro.append(
            final_fade_in_music_clip, crossfade=INTRO_FINAL_FADE_OUT_DURATION_MS
        )
        final_fade_clip.export(final_file, format="mp3")

    def create_outro_clip_with_fades(self, output_dir: pathlib.Path) -> None:
        """Create the outro clip with fades.

        Will not create the outro clip if it already exists.

        Args:
            output_dir: The directory to save the outro clip to.

        Raises:
            ValueError: If the closing statement or music clip do not exist.

        """
        final_file = output_dir / OUTRO_WITH_FADE_FILENAME

        if final_file.exists():
            logging.info("Outro clip already exists. Skipping creation.")
            return

        if not (output_dir / CLOSING_FILENAME).exists():
            raise ValueError("Cannot create fadeout clip without a closing statement")

        if not (output_dir / MUSIC_FILENAME).exists():
            raise ValueError("Cannot create fadeout clip without music")

        music_end_position = (
            OUTRO_FADE_IN_START_POINT_MS
            + OUTRO_FADE_IN_DURATION_MS
            + OUTRO_MUSIC_STATIC_DURATION_MS
            + OUTRO_FADE_OUT_DURATION_MS
        )

        music_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / MUSIC_FILENAME, "mp3")[
            OUTRO_FADE_IN_START_POINT_MS:music_end_position
        ]
        outro_speech_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / CLOSING_FILENAME, "mp3")

        music_audio = music_audio.fade_in(OUTRO_FADE_IN_DURATION_MS).fade_out(OUTRO_FADE_OUT_DURATION_MS)

        outro_speech_with_silence = outro_speech_audio + pydub.AudioSegment.silent(duration=len(music_audio))
        outro_audio = outro_speech_with_silence.overlay(
            music_audio,
            position=len(outro_speech_audio) - OUTRO_FADE_IN_STARTS_BEFORE_END_MS,
        )

        outro_audio.export(final_file, format="mp3")

    def composite_audio_files(self, output_dir: pathlib.Path) -> None:
        """Composite the audio files into a single audio file.

        Will use the cached composite audio file if it already exists.

        Args:
            output_dir: The directory to save the composite audio file to.

        Raises:
            ValueError: If the intro or outro clips do not exist.
            ValueError: If any of the segment clips do not exist.

        """
        logging.info("Compositing audio files")
        composite_file = output_dir / COMPOSITE_FILENAME
        if composite_file.exists():
            logging.info("Composite audio file already exists. Skipping creation.")
            return
        intro_with_fades = output_dir / INTRO_WITH_FADE_FILENAME
        outro_with_fades = output_dir / OUTRO_WITH_FADE_FILENAME
        if not intro_with_fades.exists():
            raise ValueError("Cannot composite audio files without an intro clip")
        if not outro_with_fades.exists():
            raise ValueError("Cannot composite audio files without an outro clip")
        if not all((output_dir / file_name).exists() for _, file_name in self.segment_files):
            raise ValueError("Cannot composite audio files without segment clips")

        intermission_silence = pydub.AudioSegment.silent(duration=INTERMISSION_SILENCE_MS)

        intro_clip = pydub.AudioSegment.from_file(intro_with_fades, "mp3")
        outro_clip = pydub.AudioSegment.from_file(outro_with_fades, "mp3")

        durations = [("Introduction", 0)]

        composite_audio = intro_clip + intermission_silence
        for segment_title, segment_file in self.segment_files:
            segment_clip = pydub.AudioSegment.from_file(output_dir / segment_file, "mp3")
            durations.append((segment_title, len(composite_audio)))
            composite_audio += segment_clip + intermission_silence
        durations.append(("Closing", len(composite_audio)))
        composite_audio += outro_clip
        composite_audio.export(composite_file, format="mp3")

        durations_string = "\n".join(
            f"{milliseconds_to_timestamps(duration)} - {segment_title}" for segment_title, duration in durations
        )
        logging.info("Segment durations: \n%s", durations_string)
        (output_dir / TIMESTAMPS_FILENAME).write_text(durations_string)

    def save_video(self, output_dir: pathlib.Path, lesson_reference: str) -> None:
        """Save the video for the episode.

        Will not create the video if it already exists.

        Args:
            output_dir: The directory to save the video to.
            lesson_reference: The reference for the lesson.

        Raises:
            ValueError: If the composite audio file does not exist.

        """
        logging.info("Creating video")
        final_video = output_dir / FINAL_VIDEO_FILENAME
        if final_video.exists():
            logging.info("Video already exists. Skipping creation.")
            return

        composite_audio = output_dir / COMPOSITE_FILENAME
        if not composite_audio.exists():
            raise ValueError("Cannot create video without composite audio")

        audio = mpy.AudioFileClip(str(composite_audio))

        text = f"{self.title}\n({lesson_reference})"
        text_clip = mpy.TextClip(text, font="Amiri-Bold", fontsize=60, color="white")

        background_file = output_dir / VIDEO_BACKGROUND_FILENAME
        background_clip = mpy.ImageClip(str(background_file))

        final_clip: mpy.CompositeVideoClip = (
            mpy.CompositeVideoClip(
                [
                    background_clip,
                    text_clip.set_position(("center", 990 - text_clip.size[1] / 2)),
                ],
                size=(1920, 1080),
                use_bgclip=True,
            )
            .set_duration(audio.duration)
            .set_audio(audio)
        )

        final_clip.write_videofile(
            str(final_video),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=multiprocessing.cpu_count(),
        )


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

    if (timestamps := (output_dir / TIMESTAMPS_FILENAME)).exists():
        video_description += f"\n\nTimestamps:\n{timestamps.read_text()}"

    logging.info(video_description)

    input(
        "\n\n⚠️⚠️Please review the video description.⚠️⚠️\n\nYou are about to upload this video to YouTube. Please hit "
        "enter to continue, and when prompted, authenticate with YouTube..."
    )

    logging.info("Publishing episode to YouTube")
    video_url = generate_show.youtube.publish_episode_to_youtube(
        output_dir / FINAL_VIDEO_FILENAME,
        episode_title=episode.title,
        scripture_reference=lesson_reference,
        video_description=video_description,
        publish_date=publish_date,
    )
    logging.info("Video published successfully: %s", video_url)
