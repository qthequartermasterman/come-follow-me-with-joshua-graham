"""Generate an episode of "Come, Follow Me with Joshua Graham"."""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import datetime

import fire
import simple_term_menu

import generate_show.youtube
from generate_show import files
from generate_show.curriculum import fetch_curriculum, get_all_curriculum_for_year, ComeFollowMeCurriculum
from generate_show.prompt import (
    generate_episode,
    generate_episode_outline,
    generate_video_description,
)

logging.basicConfig(level=logging.INFO)

def curriculum_menu() -> ComeFollowMeCurriculum:
    """Select a Come, Follow Me curriculum to generate an episode for with an interactive menu.

    Returns:
        The selected curriculum.
    """

    curricula = get_all_curriculum_for_year()
    menu_options = [f"{curriculum.title} ({curriculum.scripture_reference})" for curriculum in curricula.values()]
    now = datetime.datetime.now()
    lesson_index = next(
        (index for index, week in curricula.items() if week.start_date > now),
        0,
    )
    menu = simple_term_menu.TerminalMenu(menu_options, cursor_index=lesson_index, title="Select a Come, Follow Me lesson...")
    chosen_week_index = menu.show()
    return curricula[chosen_week_index]


def main(
    week_number: int | None = None, output_dir: str | pathlib.Path = pathlib.Path("../episodes"), upload_to_youtube: bool = True
) -> None:
    """Generate an episode of "Come, Follow Me with Joshua Graham".

    Args:
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

    if week_number is not None:
        cfm_curriculum = fetch_curriculum(week_number)
    else:
        cfm_curriculum = curriculum_menu()

    input(
        'You are about to create an episode of "Come, Follow Me with Joshua Graham" for the lesson\n'
        f"\t> {cfm_curriculum.title} ({cfm_curriculum.scripture_reference}).\n\n"
        "Please press enter to continue..."
    )

    master_dir = output_dir / files.MASTER_DIRECTORY_NAME
    lesson_dir = output_dir / (cfm_curriculum.scripture_reference.replace(" ", ""))
    # Create the output directory using the master directory as a template
    if not lesson_dir.exists():
        if not master_dir.exists():
            raise FileNotFoundError(
                f"Master directory not found at {master_dir}. Please create a master directory to use as a template."
            )
        logging.info("Copying master directory to output directory")
        shutil.copytree(master_dir, lesson_dir)

    logging.info("Generating episode outline")
    episode_outline = generate_episode_outline(cfm_curriculum.scripture_reference, cfm_curriculum.text)
    logging.info(episode_outline.model_dump_json(indent=4))

    logging.info("Generating episode")
    episode = generate_episode(cfm_curriculum.scripture_reference, cfm_curriculum.text, episode_outline=episode_outline)
    logging.info(episode.model_dump_json(indent=4))

    input("\n\n⚠️⚠️Please review the episode and press enter to continue.⚠️⚠️")

    logging.info("Generating audio files")
    episode.generate_audio_files(lesson_dir)

    logging.info("Saving video")
    episode.save_video(lesson_dir, cfm_curriculum.scripture_reference)

    if not upload_to_youtube:
        return

    logging.info("Generating video description")
    video_description = generate_video_description(episode=episode)

    if (timestamps := (lesson_dir / files.TIMESTAMPS_FILENAME)).exists():
        video_description += f"\n\nTimestamps:\n{timestamps.read_text()}"

    publish_date = generate_show.youtube.determine_publish_date(cfm_curriculum)

    logging.info(video_description)

    input(
        "\n\n⚠️⚠️Please review the video description.⚠️⚠️\n\nYou are about to upload this video to YouTube.\n\n"
        f"Publishing Date: {publish_date}\n\n"
        f"Video description:\n{video_description}\n\n"
        "Please hit enter to continue, and when prompted, authenticate with YouTube..."
    )

    logging.info("Publishing episode to YouTube")
    video_url = generate_show.youtube.publish_episode_to_youtube(
        lesson_dir / files.FINAL_VIDEO_FILENAME,
        episode_title=episode.title,
        scripture_reference=cfm_curriculum.scripture_reference,
        video_description=video_description,
        publish_date=publish_date,
    )
    logging.info("Video published successfully: %s", video_url)


if __name__ == "__main__":
    fire.Fire(main)
