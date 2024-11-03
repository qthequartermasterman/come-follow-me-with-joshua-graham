"""Audio utilities for generating the show."""

import logging
import pathlib

import pydub

from generate_show import files

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


def create_intro_clip_with_fades(output_dir: pathlib.Path) -> None:
    """Create the intro clip with fades.

    Will not create the intro clip if it already exists.

    Args:
        output_dir: The directory to save the intro clip to.

    Raises:
        ValueError: If the introduction or music clip do not exist.

    """
    final_file = output_dir / files.INTRO_WITH_FADE_FILENAME
    if final_file.exists():
        logging.info("Intro clip already exists. Skipping creation.")
        return

    if not (introduction_file := (output_dir / files.INTRODUCTION_FILENAME)).exists():
        raise ValueError("Cannot create fadein clip without an introduction")

    if not (music_file := (output_dir / files.MUSIC_FILENAME)).exists():
        raise ValueError("Cannot create fadein clip without music")

    introduction_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(introduction_file, format="mp3")
    music_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(music_file, format="mp3")
    music_clip: pydub.AudioSegment = music_audio[: INTRO_FIRST_FADE_IN_DURATION_MS + INTRO_FIRST_FADE_OUT_DURATION_MS]

    first_music_fade = music_clip.fade_in(INTRO_FIRST_FADE_IN_DURATION_MS).fade_out(INTRO_FIRST_FADE_OUT_DURATION_MS)
    length_of_silence = len(introduction_audio) - (INTRO_FIRST_FADE_OUT_DURATION_MS - 250)
    first_music_fade_plus_silence = first_music_fade + pydub.AudioSegment.silent(duration=length_of_silence)
    intro_start_position = len(first_music_fade_plus_silence) - len(introduction_audio)
    first_music_with_intro = first_music_fade_plus_silence.overlay(introduction_audio, position=intro_start_position)
    final_music_clip: pydub.AudioSegment = music_audio[
        INTRO_FINAL_FADE_IN_START_POINT_MS : INTRO_FINAL_FADE_IN_START_POINT_MS
        + INTRO_FINAL_FADE_IN_DURATION_MS
        + INTRO_FINAL_FADE_OUT_DURATION_MS
    ]

    final_fade_in_music_clip = final_music_clip.fade_in(INTRO_FINAL_FADE_IN_DURATION_MS).fade_out(
        INTRO_FINAL_FADE_OUT_DURATION_MS
    )
    length_of_silence = 2000
    final_fade_clip = (first_music_with_intro + pydub.AudioSegment.silent(duration=length_of_silence)).append(
        final_fade_in_music_clip, crossfade=INTRO_FINAL_FADE_OUT_DURATION_MS
    )
    final_fade_clip.export(final_file, format="mp3")


def composite_audio_files(output_dir: pathlib.Path, segment_files: list[tuple[str, str]]) -> None:
    """Composite the audio files into a single audio file.

    Will use the cached composite audio file if it already exists.

    Args:
        output_dir: The directory to save the composite audio file to.
        segment_files: The list of segment titles and filenames to composite.

    Raises:
        ValueError: If the intro or outro clips do not exist.
        ValueError: If any of the segment clips do not exist.

    """
    logging.info("Compositing audio files")
    composite_file = output_dir / files.COMPOSITE_FILENAME
    if composite_file.exists():
        logging.info("Composite audio file already exists. Skipping creation.")
        return
    intro_with_fades = output_dir / files.INTRO_WITH_FADE_FILENAME
    outro_with_fades = output_dir / files.OUTRO_WITH_FADE_FILENAME
    if not intro_with_fades.exists():
        raise ValueError("Cannot composite audio files without an intro clip")
    if not outro_with_fades.exists():
        raise ValueError("Cannot composite audio files without an outro clip")
    if not all((output_dir / file_name).exists() for _, file_name in segment_files):
        raise ValueError("Cannot composite audio files without segment clips")

    intermission_silence = pydub.AudioSegment.silent(duration=INTERMISSION_SILENCE_MS)

    intro_clip = pydub.AudioSegment.from_file(intro_with_fades, format="mp3")
    outro_clip = pydub.AudioSegment.from_file(outro_with_fades, format="mp3")

    durations: list[tuple[str, int]] = [("Introduction", 0)]

    composite_audio = intro_clip + intermission_silence
    for segment_title, segment_file in segment_files:
        segment_clip = pydub.AudioSegment.from_file(output_dir / segment_file, format="mp3")
        durations.append((segment_title, len(composite_audio)))
        composite_audio += segment_clip + intermission_silence
    durations.append(("Closing", len(composite_audio)))
    composite_audio += outro_clip
    composite_audio.export(composite_file, format="mp3")

    durations_string = "\n".join(
        f"{milliseconds_to_timestamps(duration)} - {segment_title}" for segment_title, duration in durations
    )
    logging.info("Segment durations: \n%s", durations_string)
    (output_dir / files.TIMESTAMPS_FILENAME).write_text(durations_string)


def create_outro_clip_with_fades(output_dir: pathlib.Path) -> None:
    """Create the outro clip with fades.

    Will not create the outro clip if it already exists.

    Args:
        output_dir: The directory to save the outro clip to.

    Raises:
        ValueError: If the closing statement or music clip do not exist.

    """
    final_file = output_dir / files.OUTRO_WITH_FADE_FILENAME

    if final_file.exists():
        logging.info("Outro clip already exists. Skipping creation.")
        return

    if not (output_dir / files.CLOSING_FILENAME).exists():
        raise ValueError("Cannot create fadeout clip without a closing statement")

    if not (output_dir / files.MUSIC_FILENAME).exists():
        raise ValueError("Cannot create fadeout clip without music")

    music_end_position = (
        OUTRO_FADE_IN_START_POINT_MS
        + OUTRO_FADE_IN_DURATION_MS
        + OUTRO_MUSIC_STATIC_DURATION_MS
        + OUTRO_FADE_OUT_DURATION_MS
    )

    music_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(output_dir / files.MUSIC_FILENAME, format="mp3")[
        OUTRO_FADE_IN_START_POINT_MS:music_end_position
    ]
    outro_speech_audio: pydub.AudioSegment = pydub.AudioSegment.from_file(
        output_dir / files.CLOSING_FILENAME, format="mp3"
    )

    music_audio = music_audio.fade_in(OUTRO_FADE_IN_DURATION_MS).fade_out(OUTRO_FADE_OUT_DURATION_MS)

    outro_speech_with_silence = outro_speech_audio + pydub.AudioSegment.silent(duration=len(music_audio))
    outro_audio = outro_speech_with_silence.overlay(
        music_audio,
        position=len(outro_speech_audio) - OUTRO_FADE_IN_STARTS_BEFORE_END_MS,
    )

    outro_audio.export(final_file, format="mp3")


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
