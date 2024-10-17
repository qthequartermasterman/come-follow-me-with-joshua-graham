"""Narration utilities."""

import logging
import pathlib
import re
import warnings

from elevenlabs import ElevenLabs, VoiceSettings

NAMES = {
    "1 Nephi ": "first Nephi ",
    "2 Nephi ": "second Nephi ",
    "3 Nephi ": "third Nephi ",
    "4 Nephi ": "fourth Nephi ",
    "1 Samuel ": "first Samuel ",
    "2 Samuel ": "second Samuel ",
    "1 Kings ": "first Kings ",
    "2 Kings ": "second Kings ",
    "1 Chronicles ": "first Chronicles ",
    "2 Chronicles ": "second Chronicles ",
    "1 Corinthians ": "first Corinthians ",
    "2 Corinthians ": "second Corinthians ",
    "1 Thessalonians ": "first Thessalonians ",
    "2 Thessalonians ": "second Thessalonians ",
    "1 Timothy ": "first Timothy ",
    "2 Timothy ": "second Timothy ",
    "1 Peter ": "first Peter ",
    "2 Peter ": "second Peter ",
    "1 John ": "first John ",
    "2 John ": "second John ",
    "3 John ": "third John ",
}
NUM_THROUGH_NUM_REGEX = re.compile(r"(\d+)[-–](\d+)")
DOCTRINE_AND_COVENANTS_SECTION_VERSE_REGEX = re.compile(
    r"(Doctrine and Covenants|Doctrine & Covenants|D&C) (\d+):(\d+)"
)
CHAPTER_VERSE_REGEX = re.compile(r"(\d+):(\d+)")
VOICE_SETTINGS = VoiceSettings(
    stability=0.34,
    similarity_boost=0.8,
    style=0.2,
)
ELEVENLABS_CLIENT = ElevenLabs()


def generate_audio_file_from_text(text: str, path: pathlib.Path) -> None:
    """Generate an audio file from text using the ElevenLabs API.

    Will not generate the audio file if it already exists.

    Args:
        text: The text to convert to speech.
        path: The path to save the audio file to.

    Raises:
        ValueError: If the path does not have a .mp3 extension.

    """
    if path.suffix != ".mp3":
        raise ValueError(f"Audio file must be in mp3 format. Got {path}")

    if path.exists():
        logging.info("Audio file %s already exists. Skipping creation.", str(path))
        return

    audio_response = ELEVENLABS_CLIENT.text_to_speech.convert(
        voice_id="nBwyHk4MbE8FJ1GEsatX",  # Custom Joshua Graham voice
        model_id="eleven_turbo_v2",  # This model is cheap and supports phoneme tags
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=text,
        voice_settings=VOICE_SETTINGS,
    )

    # Writing the audio to a file
    with open(path, "wb") as f:
        for chunk in audio_response:
            if chunk:
                f.write(chunk)


def add_pronunciation_helpers(text: str) -> str:
    """Modify text generated from the LLM to make it readable by ElevenLabs.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text.

    """
    for punctuation in (" ", ".", ",", "'", ":", "!", "?", "’s", "'s"):
        for name, phoneme in NAMES.items():
            text = text.replace(name[:-1] + punctuation, phoneme[:-1] + punctuation)
    text = re.sub(NUM_THROUGH_NUM_REGEX, r"\1 through \2", text)
    text = re.sub(
        DOCTRINE_AND_COVENANTS_SECTION_VERSE_REGEX,
        r"Doctrine and Covenants Section \2 Verse \3",
        text,
    )
    text = re.sub(CHAPTER_VERSE_REGEX, r"Chapter \1 Verse \2", text)
    text = text.replace("[Pause]", "<break time='1s'/>")
    text = text.replace("[Pause for reflection]", "<break time='2s'/>")
    text = text.replace("[Scripture quote:]", "<break time='1s'/>")
    text = text.replace("[Scripture connection:]", "<break time='1s'/>")
    text = text.replace("[Final Scripture:]", "<break time='1s'/>")
    if "[" in text or "]" in text:
        warnings.warn(
            f"Text contains unspeakable items: {text}",
            category=UserWarning,
            stacklevel=2,
        )
        text = re.sub(r"\[.*\]", "------", text)
    return text
