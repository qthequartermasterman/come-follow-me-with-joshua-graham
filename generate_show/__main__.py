"""Generate an episode of "Come, Follow Me with Joshua Graham"."""

import logging
import os
import pathlib
import shutil

import generate_show.youtube
from generate_show import files
from generate_show.curriculum import fetch_curriculum
from generate_show.prompt import (
    generate_episode,
    generate_episode_outline,
    generate_video_description,
)

logging.basicConfig(level=logging.INFO)


def main(week_number: int, output_dir: pathlib.Path) -> None:
    """Generate an episode of "Come, Follow Me with Joshua Graham".

    Args:
        week_number: The week number of the curriculum to generate an episode for.
        output_dir: The directory to save the episode to.

    Raises:
        ValueError: If the `ELEVEN_API_KEY` or `OPENAI_API_KEY` environment variables are not set.

    """
    if not os.getenv("ELEVEN_API_KEY"):
        raise ValueError("Please set the `ELEVEN_API_KEY` environment variable to your ElevenLabs API key.")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set the `OPENAI_API_KEY` environment variable to your OpenAI API key.")

    lesson_title, lesson_reference, curriculum_text = fetch_curriculum(week_number)

    input(
        'You are about to create an episode of "Come, Follow Me with Joshua Graham" for the lesson\n'
        f"\t> {lesson_title} ({lesson_reference}).\n\n"
        "Please press enter to continue..."
    )

    output_dir = output_dir / (lesson_reference.replace(" ", ""))
    master_dir = output_dir / "master"
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

    publish_date = generate_show.youtube.determine_publish_date(lesson_title)
    logging.info("Publishing episode to YouTube")
    video_url = generate_show.youtube.publish_episode_to_youtube(
        output_dir / files.FINAL_VIDEO_FILENAME,
        episode_title=episode.title,
        scripture_reference=lesson_reference,
        video_description=video_description,
        publish_date=publish_date,
    )
    logging.info("Video published successfully: %s", video_url)


if __name__ == "__main__":
    # Make sure to set the `ELEVEN_API_KEY` environment variable to your ElevenLabs API key
    # and the `OPENAI_API_KEY` environment variable to your OpenAI API key.
    # Once you have set these environment variables, you can run this script to generate a podcast episode, after
    # setting `WEEK_NUMBER` to the week number of the curriculum you want to generate an episode for.
    WEEK_NUMBER = 42
    OUTPUT_DIR = pathlib.Path("../episodes")

    main(WEEK_NUMBER, OUTPUT_DIR)
