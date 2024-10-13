"""Prompting utilities for generating the show."""

import logging

import httpx
import magentic

from generate_show.models import Episode, EpisodeOutline

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
    ...


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
    ...


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
    ...
