"""Generate an episode of "Come, Follow Me with Joshua Graham"."""

from __future__ import annotations

import datetime
import logging
import os
import pathlib
import re
import shutil

import fire
import simple_term_menu

import generate_show.youtube
from generate_show import files, prompt
from generate_show.curriculum import ComeFollowMeCurriculum, fetch_curriculum, get_all_curriculum_for_year
from generate_show.prompt import (
    ScriptureInsights,
    correlate_episode,
    generate_episode,
    generate_episode_outline,
    generate_video_description,
    revise_episode,
)

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def year_menu() -> int:
    """Select a Come, Follow Me year to generate an episode for with an interactive menu.

    Returns:
        The selected year.

    """
    years = [2024, 2025]
    current_year = datetime.datetime.now().year
    current_year_index = next((index for index, year in enumerate(years) if year == current_year), 0)
    year_menu = simple_term_menu.TerminalMenu(
        [str(year) for year in years], title="Select a Come, Follow Me year...", cursor_index=current_year_index
    )
    chosen_year_index = year_menu.show()
    assert isinstance(chosen_year_index, int)
    return years[chosen_year_index]


async def curriculum_menu(year: int) -> ComeFollowMeCurriculum:
    """Select a Come, Follow Me curriculum to generate an episode for with an interactive menu.

    Args:
        year: The year of the Come, Follow Me curriculum to generate an episode for.

    Returns:
        The selected curriculum.

    """
    current_year = datetime.datetime.now().year

    curricula = await get_all_curriculum_for_year(year)
    menu_options = [f"{curriculum.title} ({curriculum.scripture_reference})" for curriculum in curricula.values()]
    now = datetime.datetime.now()
    lesson_index = next(
        (index for index, week in curricula.items() if week.start_date > now and week.start_date.year == current_year),
        0,
    )
    menu = simple_term_menu.TerminalMenu(
        menu_options, cursor_index=lesson_index, title="Select a Come, Follow Me lesson..."
    )
    chosen_week_index = menu.show()
    assert isinstance(chosen_week_index, int)
    return curricula[chosen_week_index + 1]  # Off by one because the curriculum id is 1-indexed


async def main(
    year: int | None = None,
    week_number: int | None = None,
    output_dir: str | pathlib.Path = pathlib.Path("./episodes"),
    upload_to_youtube: bool = True,
) -> None:
    """Generate an episode of "Come, Follow Me with Joshua Graham".

    Args:
        year: The year of the Come, Follow Me curriculum to generate an episode for.
        week_number: The week number of the curriculum to generate an episode for.
        output_dir: The directory to save the episode to.
        upload_to_youtube: Whether to upload the episode to YouTube.

    Raises:
        ValueError: If the `ELEVEN_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_APPLICATION_CREDENTIALS` environment
            variables are not set.

    """
    if not os.getenv("ELEVEN_API_KEY"):
        raise ValueError("Please set the `ELEVEN_API_KEY` environment variable to your ElevenLabs API key.")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set the `OPENAI_API_KEY` environment variable to your OpenAI API key.")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and upload_to_youtube:
        raise ValueError(
            "Please set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to your Google Cloud credentials."
        )

    output_dir = pathlib.Path(output_dir)

    if year is None:
        year = year_menu()

    if week_number is not None:
        cfm_curriculum = await fetch_curriculum(week_number, year)
    else:
        cfm_curriculum = await curriculum_menu(year)

    input(
        'You are about to create an episode of "Come, Follow Me with Joshua Graham" for the lesson\n'
        f"\t> {cfm_curriculum.title} ({cfm_curriculum.scripture_reference}).\n\n"
        "Please press enter to continue..."
    )

    master_dir = output_dir / files.MASTER_DIRECTORY_NAME
    lesson_dir = output_dir / (re.sub(r"\s+", "_", cfm_curriculum.scripture_reference))
    # Create the output directory using the master directory as a template
    if not lesson_dir.exists():
        if not master_dir.exists():
            raise FileNotFoundError(
                f"Master directory not found at {master_dir.absolute()}. "
                "Please create a master directory to use as a template."
            )
        LOGGER.info("Copying master directory to output directory")
        shutil.copytree(master_dir, lesson_dir)

    LOGGER.info("Generating scripture insights")
    if (insights_file := lesson_dir / files.SCRIPTURE_INSIGHTS_FILENAME).exists():
        scripture_insights = ScriptureInsights.parse_raw(insights_file.read_text())
    else:
        scripture_insights = await prompt.ScriptureInsightsFactory().generate_scripture_insights(cfm_curriculum)
        insights_file.write_text(scripture_insights.model_dump_json(indent=4))
    LOGGER.info(scripture_insights.model_dump_json(indent=4))

    LOGGER.info("Generating episode outline")
    if (outline_file := lesson_dir / files.EPISODE_OUTLINE_FILENAME).exists():
        episode_outline = prompt.EpisodeOutline.parse_raw(outline_file.read_text())
    else:
        episode_outline = await generate_episode_outline(
            cfm_curriculum.scripture_reference, scripture_insights=scripture_insights
        )
        outline_file.write_text(episode_outline.model_dump_json(indent=4))
    LOGGER.info(episode_outline.model_dump_json(indent=4))

    LOGGER.info("Generating episode")
    if (script_file := lesson_dir / files.EPISODE_SCRIPT_FILENAME).exists():
        episode = prompt.Episode.parse_raw(script_file.read_text())
    else:
        episode = await generate_episode(cfm_curriculum.scripture_reference, episode_outline=episode_outline)
        LOGGER.info("Episode generated successfully. Correlating with doctrine...")
        correlation_comments = await correlate_episode(episode)
        LOGGER.info("Correlation comments:\n%s", correlation_comments)
        LOGGER.info("Revising episode...")
        episode = await revise_episode(episode, correlation_comments)
        LOGGER.info("Episode revised successfully. Writing to file...")
        script_file.write_text(episode.model_dump_json(indent=4))
    LOGGER.info(episode.model_dump_json(indent=4))

    input("\n\n⚠️⚠️Please review the episode and press enter to continue.⚠️⚠️")

    LOGGER.info("Generating audio files")
    episode.generate_audio_files(lesson_dir)

    LOGGER.info("Saving video")
    episode.save_video(lesson_dir, cfm_curriculum.scripture_reference)

    if not upload_to_youtube:
        return

    LOGGER.info("Generating video description")
    if (description_file := lesson_dir / files.VIDEO_DESCRIPTION_FILENAME).exists():
        video_description = description_file.read_text()
    else:
        video_description = await generate_video_description(episode=episode)
        description_file.write_text(video_description)

    if (timestamps := (lesson_dir / files.TIMESTAMPS_FILENAME)).exists():
        video_description += f"\n\nTimestamps:\n{timestamps.read_text()}"

    publish_date = generate_show.youtube.determine_publish_date(cfm_curriculum)

    LOGGER.info(video_description)

    episode.generate_transcript(lesson_dir)

    input(
        "\n\n⚠️⚠️Please review the video description.⚠️⚠️\n\nYou are about to upload this video to YouTube.\n\n"
        f"Publishing Date: {publish_date}\n\n"
        f"Video description:\n{video_description}\n\n"
        "Please hit enter to continue, and when prompted, authenticate with YouTube..."
    )

    LOGGER.info("Publishing episode to YouTube")
    video_url = generate_show.youtube.publish_episode_to_youtube(
        lesson_dir / files.FINAL_VIDEO_FILENAME,
        episode_title=episode.title,
        scripture_reference=cfm_curriculum.scripture_reference,
        video_description=video_description,
        publish_date=publish_date,
    )
    LOGGER.info("Video published successfully: %s", video_url)


if __name__ == "__main__":
    fire.Fire(main)
