"""Pydantic models for the podcast episode outline and episode."""

import functools
import hashlib
import logging
import multiprocessing
import pathlib
from typing import Callable, Type

import pydantic
import tqdm
from moviepy import editor as mpy
from typing_extensions import ParamSpec, TypeVar

import generate_show.narration
from generate_show import files
from generate_show.audio import composite_audio_files, create_intro_clip_with_fades, create_outro_clip_with_fades

P = ParamSpec("P")
Model = TypeVar("Model", bound=pydantic.BaseModel)


class CacheModel(pydantic.BaseModel):
    """A pydantic model that can cache its output to a file."""

    @classmethod
    def cache_pydantic_model(cls: Type[Model], func: Callable[P, Model]) -> Callable[P, Model]:
        """Cache the output of a function that returns a pydantic model.

        The cached model will be saved to a file in the .cache directory with the name of the class and a hash of the
        arguments.

        Args:
            func: The function to cache the output of.

        Returns:
            The wrapped function that caches the output.

        """

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Model:
            """Wrap the function to cache the output.

            Args:
                *args: The arguments to the function.
                **kwargs: The keyword arguments to the function.

            """
            args_hash = hashlib.sha256((cls.__name__ + str(args) + str(kwargs)).encode("utf-8")).hexdigest()[:16]
            path: pathlib.Path = pathlib.Path("../.cache") / f"{cls.__name__}-{args_hash}.json"
            if path.exists():
                logging.info("Cache hit for %s. Using cached %s", path, cls.__name__)
                return cls.model_validate_json(path.read_text())
            model = func(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(model.model_dump_json(indent=4))
            return model

        return wrapper


class ScriptureInsight(pydantic.BaseModel):
    """An insight into a scripture passage."""

    reference: str = pydantic.Field(
        description=(
            "The reference to the scripture that the insight is based on. This should be a valid scripture reference"
            " in the format 'Book Chapter:Verse', or if it's a range of verses, 'Book Chapter:Verse-Chapter:Verse'."
        )
    )
    insight: str = pydantic.Field(
        description=(
            "The insight into the scripture passage. This should be doctrinally sound according to the official"
            " positions of the Church of Jesus Christ of Latter-day Saints. The insight should be spiritually uplifting"
            " and testify of Jesus Christ."
        )
    )


class ScriptureInsights(CacheModel):
    """A collection of insights into scripture passages."""

    insights: list[ScriptureInsight] = pydantic.Field(
        description=(
            "A list of insights into scripture passages. Each insight should be based on a specific scripture"
            " reference and should be doctrinally sound according to the official positions of the Church of Jesus"
            " Christ of Latter-day Saints. Each insight should be spiritually uplifting and testify of Jesus Christ."
        )
    )

    @classmethod
    def compile_insights(cls, *insights: "ScriptureInsights") -> "ScriptureInsights":
        """Compile the insights into a single text string."""
        insights_combined = [insight for insight_set in insights for insight in insight_set.insights]
        insights_combined = list(sorted(insights_combined, key=lambda insight: insight.reference))
        return cls(insights=insights_combined)


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


class EpisodeOutline(CacheModel):
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


class Episode(EpisodeOutline):
    """A full podcast episode."""

    _normalize_introduction = pydantic.field_validator("introduction")(
        generate_show.narration.add_pronunciation_helpers
    )
    _normalize_closing = pydantic.field_validator("closing")(generate_show.narration.add_pronunciation_helpers)

    @property
    def segment_files(self) -> list[tuple[str, str]]:
        """Get the title of each segment along with the filename to save the audio to."""
        return [(segment.title, files.SEGMENT_FILENAME_TEMPLATE.format(i=i)) for i, segment in enumerate(self.segments)]

    @property
    def segment_text_files(self) -> list[tuple[str, str]]:
        """Get the text of each segment along with the filename to save the audio to."""
        return [(segment.text, files.SEGMENT_FILENAME_TEMPLATE.format(i=i)) for i, segment in enumerate(self.segments)]

    def generate_audio_files(self, output_dir: pathlib.Path) -> None:
        """Generate the audio files for the episode.

        Will not generate the audio files if they already exist.

        Args:
            output_dir: The directory to save the audio files to.

        """
        logging.info("Generating audio files")
        output_dir.mkdir(exist_ok=True)

        text_files = (
            [(self.introduction, files.INTRODUCTION_FILENAME)]
            + self.segment_text_files
            + [(self.closing, files.CLOSING_FILENAME)]
        )
        for text, file_name in tqdm.tqdm(text_files, desc="Generating audio files from text"):
            generate_show.narration.generate_audio_file_from_text(text, output_dir / file_name)

        create_intro_clip_with_fades(output_dir)
        create_outro_clip_with_fades(output_dir)
        composite_audio_files(output_dir, segment_files=self.segment_files)

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
        final_video = output_dir / files.FINAL_VIDEO_FILENAME
        if final_video.exists():
            logging.info("Video already exists. Skipping creation.")
            return

        composite_audio = output_dir / files.COMPOSITE_FILENAME
        if not composite_audio.exists():
            raise ValueError("Cannot create video without composite audio")

        audio = mpy.AudioFileClip(str(composite_audio))

        text = f"{self.title}\n({lesson_reference})"
        text_clip = mpy.TextClip(text, font="Amiri-Bold", fontsize=60, color="white")

        background_file = output_dir / files.VIDEO_BACKGROUND_FILENAME
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

        logging.info("Video created at %s", final_video)
