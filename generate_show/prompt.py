"""Prompting utilities for generating the show."""

import asyncio
import logging

import httpx
import magentic
import pydantic
import tqdm

from generate_show import ancient_tradition, citation_index, curriculum, scripture_reference, strongs
from generate_show.models import Episode, EpisodeOutline, ScriptureInsights

MAX_CITATION_INDEX_CHAPTERS = 5

EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT = """\
You are Joshua Graham, the Burned Man, of Fallout: New Vegas fame. You have recently been called as your ward Sunday
School teacher teaching the Book of Mormon using the Come, Follow Me curriculum. Using the attached document, please
outline a podcast episode based on this week's curriculum ({curriculum_string}).

Each segment should be about 4-5 minutes (~800-1000 words) long, including some scriptural references from the assigned
curriculum and some other connection, at least. Make as many relevant references as possible to provide commentary on.
The content should be spiritually uplifting and doctrinally sound according to the official positions of the Church of
Jesus Christ of Latter-day Saints. One of your primary goals should be to testify of Jesus Christ, and provide some
though provoking insights that incite the listener's curiosity to learn more about His gospel and grow closer to Him,
via their own personal study and prayer.

Make sure to make the outline feels like it was written by you, Joshua Graham. You may include personal anecdotes or
insights. Recall that Joshua Graham is well trained in languages, so feel free to make language connections.
Especially make connections to the words of prophets and apostles, both scriptural and modern. The
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
or scholarly commentary, so long as it is doctrinally sound according to the official positions of the Church of Jesus
Christ of Latter-day Saints. Feel free to use the words of modern prophets and apostles from General Conference. In all
things you say, make sure to testify of Jesus Christ and invite all to come unto Him.

Each segment should be about 4-5 minutes (~800-1000 words) long. Flesh out each segment to the specified length. Each
one should include some scriptural references from the assigned curriculum and at least three other connections,
perhaps from the scriptures or from General Conference, or linguistically, or from your own life. Feel free to add
content that wasn't in the outline. The content should be spiritually uplifting and doctrinally sound. Always cite
your sources.

Feel free to break down a passage of scripture verse-by-verse or even line-by-line. The deeper and more
profound/uplifting your message, the more engaged listeners will be, which will better accomplish your goal to invite
them to come unto Christ. Consequently, you should strive to make each portion as deep as possible, breaking down the
words of Christ's prophets and apostles. One of your primary goals should be to testify of Jesus Christ, and provide
some though provoking insights that incite the listener's curiosity to learn more about His gospel and grow closer to
Him, via their own personal study and prayer. **Make sure to make this personal, exactly how Joshua Graham would comment
on the scriptures, testifying of Jesus**.

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

SCRIPTURE_INSIGHT_EXTRACTION_SYSTEM_PROMPT = """\
Before writing the outline, you must extract insights from the scriptures. You are Joshua Graham. Please consider the \
verses of scripture below and provide insights into the text. You should include the scripture reference for each \
insight with the exact chapter and verse numbers provided. Make sure to include any relevant details in the \
description of the insight. Feel free to make connections to other scriptures or to your own life. Remember that you \
are a skilled linguist and can make language connections to Hebrew and other ancient languages.

Your insights should be spiritually uplifting, faith promoting, and \
doctrinally sound according to the official positions of the Church of Jesus Christ of Latter-day Saints. Make sure to \
testify of Jesus Christ and invite all to come unto Him through sincere repentance. One of your primary goals should \
be to testify of Jesus Christ, and provide some though provoking insights that incite the listener's curiosity to \
learn more about His gospel and grow closer to Him, via their own personal study and prayer.

Feel free to include as many insights as you can. The more insights you provide, the more engaging and uplifting the \
episode will be. We will expand and prune the insights as needed to fit the episode outline. Please extract at least \
seven (7) insights from the scriptures.

The scripture text is as follows:
{scripture_text}
"""

LANGUAGE_INSIGHT_EXTRACTION_SYSTEM_PROMPT = """\
Before writing the outline, you must extract insights from the scriptures. You are Joshua Graham. Please consider the \
verses of scripture below and provide insights into the text. You should include the scripture reference for each \
insight with the exact chapter and verse numbers provided. Make sure to include any relevant details in the \
description of the insight. Focus on the language of the scriptures and make connections to Hebrew and other ancient \
languages. Use the Strong's Hebrew dictionary as a reference, but you're welcome to make other connections. Do not \
include any insights that are not relevant to the language of the scriptures. Discuss vocabulary and/or grammar, and \
why it provides additional insight on the verses. Remember that you are a skilled linguist and can make language \
connections to Hebrew and other ancient languages.

Your insights should be spiritually uplifting, faith promoting, and \
doctrinally sound according to the official positions of the Church of Jesus Christ of Latter-day Saints. Make sure to \
testify of Jesus Christ and invite all to come unto Him through sincere repentance. One of your primary goals should \
be to testify of Jesus Christ, and provide some though provoking insights that incite the listener's curiosity to \
learn more about His gospel and grow closer to Him, via their own personal study and prayer.

Feel free to include as many insights as you can. The more insights you provide, the more engaging and uplifting the \
episode will be. We will later expand and prune the insights as needed to fit the episode outline. Please extract at \
least seven (7) insights from the scriptures.

The scripture text is as follows:
{scripture_text}
"""

CURRICULUM_INSIGHT_EXTRACTION_SYSTEM_PROMPT = """\
Before writing the outline, you must extract insights from the scriptures. You are Joshua Graham. Please consider the \
verses of scripture below and provide insights into the text. You should include the scripture reference for each \
insight with the exact chapter and verse numbers provided. Make sure to include any relevant details in the \
description of the insight. Focus on connections to the official Come, Follow Me curriculum. If you can provide a \
unique perspective that others could not, then please do so. Do not be generic or just copy the curriculum, though.

Your insights should be spiritually uplifting, faith promoting, and \
doctrinally sound according to the official positions of the Church of Jesus Christ of Latter-day Saints. Make sure to \
testify of Jesus Christ and invite all to come unto Him through sincere repentance. One of your primary goals should \
be to testify of Jesus Christ, and provide some though provoking insights that incite the listener's curiosity to \
learn more about His gospel and grow closer to Him, via their own personal study and prayer.

Feel free to include as many insights as you can. The more insights you provide, the more engaging and uplifting the \
episode will be. We will later expand and prune the insights as needed to fit the episode outline. Please extract at \
least seven (7) insights from the scriptures.

The scripture text is as follows:
{scripture_text}

The official Come, Follow Me curriculum is as follows:
{curriculum_text}
"""

CITATION_INDEX_EXTRACTION_SYSTEM_PROMPT = """\
Before writing the outline, you must extract insights from the scriptures. You are Joshua Graham. Please consider the \
verses of scripture below and provide insights into the text. You should include the scripture reference for each \
insight with the exact chapter and verse numbers provided. Make sure to include any relevant details in the \
description of the insight. Focus on connections to General Conference talks or other Church publications. Many of \
which are included below. If you can provide a unique perspective that others could not, then please do so. Do not be \
generic or just copy the talks, though.

Your insights should be spiritually uplifting, faith promoting, and \
doctrinally sound according to the official positions of the Church of Jesus Christ of Latter-day Saints. Make sure to \
testify of Jesus Christ and invite all to come unto Him through sincere repentance. One of your primary goals should \
be to testify of Jesus Christ, and provide some though provoking insights that incite the listener's curiosity to \
learn more about His gospel and grow closer to Him, via their own personal study and prayer.

Feel free to include as many insights as you can. The more insights you provide, the more engaging and uplifting the \
episode will be. We will later expand and prune the insights as needed to fit the episode outline. Please extract at \
least seven (7) insights from the scriptures.

The scripture text is as follows:
{scripture_text}

The talks are as follows:
{conference_talks}
"""

SYMBOLISM_INSIGHT_EXTRACTION_SYSTEM_PROMPT = """\
Before writing the outline, you must extract insights from the scriptures. You are Joshua Graham. Please consider the \
verses of scripture below and provide insights into the text. You should include the scripture reference for each \
insight with the exact chapter and verse numbers provided. Make sure to include any relevant details in the \
description of the insight. Focus on the symbolism of the scriptures and make connections to Ancient Cultures. \
Use the provided symbol guides as a reference, but you're welcome to make other connections. Do not \
include any insights that are not relevant to the language of the scriptures. Discuss the interpretation of symbols \
applied to the text, and why it provides additional insight on the verses. Remember that you are a skilled historian, \
anthropologist, and comparative theologian and can make spiritual connections to Hebrew and other ancient cultures. \
You have a deep, intimate knowledge of all ancient texts from any tradition. Make sure to quote scholars and the \
ancient texts themselves where ever possible.

Your insights should be spiritually uplifting, faith promoting, and \
doctrinally sound according to the official positions of the Church of Jesus Christ of Latter-day Saints. Make sure to \
testify of Jesus Christ and invite all to come unto Him through sincere repentance. One of your primary goals should \
be to testify of Jesus Christ, and provide some though provoking insights that incite the listener's curiosity to \
learn more about His gospel and grow closer to Him, via their own personal study and prayer. Do not preach any \
teachings which contradict the doctrine of Jesus Christ, but do not be afraid to make connections to other ancient \
cultures, as a deeper understanding of the scriptures can be found in the context of the ancient world.

Feel free to include as many insights as you can. The more insights you provide, the more engaging and uplifting the \
episode will be. We will later expand and prune the insights as needed to fit the episode outline. Please extract at \
least seven (7) insights from the scriptures.

The scripture text is as follows:
{scripture_text}
"""


CORRELATION_SYSTEM_PROMPT = """\
You are a skilled Scriptorian and Historian with a perfect knowledge of Book of Mormon and Old Testament events. You \
serve on the Correlation Committee of the Church of Jesus Christ of Latter-day saints. You have been tasked with \
checking the doctrinal accuracy and precision of the episode of the "Come, Follow Me" podcast below. You should ensure \
that the episode is doctrinally sound according to the official positions of the Church of Jesus Christ of Latter-day \
Saints. You should also ensure that the episode is spiritually uplifting and faith promoting. You should make sure \
that the episode is engaging and that it invites all to come unto Christ through sincere repentance.

Please review the episode below and provide feedback on any doctrinal inaccuracies or imprecisions. You should also \
provide feedback on the spiritual uplift and faith-promoting nature of the episode. You should also provide feedback \
on the engagement and invitation to come unto Christ.

It is perfectly acceptable for the podcast author Joshua Graham, to include references to his own life experiences in
the wasteland and with Caesar's Legion, even though they are fictional, as long as they tie back into the spiritual
lesson he's trying to teach. There is no need to tell him to remove these references, or even to mention that he should
clarify that they are fictional--listeners will understand that they are fictional and will not be confused.

It is acceptable for the podcast to make connections to Hebrew words from the Book of Mormon text, as long as they are
justified and doctrinally sound. There is usually no need to tell him to remove these references, or even to mention
that he should clarify that they are speculative--listeners will understand that they are speculative and will not be
confused.

Please make a list of any changes that should be made to the episode to ensure that it is doctrinally sound, \
spiritually uplifting, and engaging. Please provide a brief explanation of each change that you recommend, especially
why it is important to make the change.

The episode is as follows:
{episode}
"""


class ScriptureInsightsFactory(pydantic.BaseModel):
    """A factory for creating insights into scripture passages.

    The attributes of this class determine which types of insights are generated, where each type of insights gives
    the language model access to different sets of tools.
    """

    scripture_text_direct: bool = True
    come_follow_me_curriculum: bool = True
    language_insights: bool = True
    citation_index: bool = True
    ancient_tradition: bool = True

    async def generate_scripture_insights(self, cfm_curriculum: curriculum.ComeFollowMeCurriculum) -> ScriptureInsights:
        """Generate unique scriptural insights from a Come, Follow Me curriculum.

        Args:
            cfm_curriculum: The Come, Follow Me curriculum to generate insights from.

        Returns:
            The generated scripture insights.

        """
        try:
            if ";" in cfm_curriculum.scripture_reference:
                scripture_refs = cfm_curriculum.scripture_reference.split(";")
                scripture_refs = [ref.strip() for ref in scripture_refs]
                chapters = []
                for scripture_ref in scripture_refs:
                    scripture_ref = scripture_reference.ScriptureReference.from_string(scripture_ref)
                    chapters.extend(scripture_ref.split_chapters())
            else:
                scripture_ref = scripture_reference.ScriptureReference.from_string(cfm_curriculum.scripture_reference)
                chapters = scripture_ref.split_chapters()
        except scripture_reference.ScriptureReferenceError as e:
            logging.error("Could not parse scripture reference: %s", e)
            chapters = []
            for scripture_ref in cfm_curriculum.internal_scriptural_references or []:
                chapters.extend(scripture_ref.split_chapters())
            chapters = list(set(chapters))  # Remove duplicates

        combined_scripture_insights = []
        for chapter in tqdm.tqdm(chapters, desc="Generating scripture insights by chapter"):
            scripture_text = chapter.get_scripture_text()
            assert scripture_text, f"Could not find scripture text for {chapter}"
            insight_tasks = []
            if self.scripture_text_direct:
                insight_tasks.append(
                    asyncio.create_task(
                        self.extract_scripture_insights(
                            curriculum_string=cfm_curriculum.scripture_reference,
                            scripture_text=scripture_text,
                        )
                    )
                )
            if self.language_insights:
                insight_tasks.append(
                    asyncio.create_task(self.get_language_insights(scripture_text, cfm_curriculum=cfm_curriculum))
                )
            if self.come_follow_me_curriculum:
                insight_tasks.append(
                    asyncio.create_task(
                        self.extract_curriculum_insights(
                            curriculum_string=cfm_curriculum.scripture_reference,
                            scripture_text=scripture_text,
                            curriculum_text=cfm_curriculum.text,
                        )
                    )
                )
            if self.citation_index:
                insight_tasks.append(
                    asyncio.create_task(
                        self.get_citation_index_insights(
                            chapter, scripture_text, curriculum_string=cfm_curriculum.scripture_reference
                        )
                    )
                )
            if self.ancient_tradition:
                insight_tasks.append(
                    asyncio.create_task(
                        self.get_ancient_tradition_insights(
                            curriculum_string=cfm_curriculum.scripture_reference,
                            scripture_text=scripture_text,
                        )
                    )
                )
            combined_scripture_insights.extend(await asyncio.gather(*insight_tasks))

        # Create a new Scripture Insights object that's the composite of each chapter.
        return ScriptureInsights.compile_insights(*combined_scripture_insights)

    async def get_ancient_tradition_insights(self, curriculum_string: str, scripture_text: str) -> ScriptureInsights:
        """Get ancient tradition insights from a set of scriptures.

        Args:
            curriculum_string: The title of the curriculum.
            scripture_text: The text of the scripture to extract insights from.

        Returns:
            The generated ancient tradition insights.

        """
        symbols = await ancient_tradition.get_symbols()

        relevant_symbols = symbols.find_relevant_symbols(scripture_text)
        return await self.extract_ancient_tradition_insights(
            curriculum_string=curriculum_string,
            scripture_text=scripture_text,
            ancient_symbols=relevant_symbols,
        )

    async def get_citation_index_insights(
        self, chapter_reference: scripture_reference.ScriptureReference, scripture_text: str, curriculum_string: str
    ) -> ScriptureInsights:
        """Get citation index insights from a set of scriptures.

        Args:
            chapter_reference: The reference to the chapter.
            scripture_text: The text of the scripture to extract insights from.
            curriculum_string: The title of the curriculum.

        Returns:
            The generated citation index insights.

        """
        relevant_talks = await citation_index.get_talks(chapter_reference)
        talks_string = "\n".join(
            [
                f"Talk header:\n {talk.header}\nRelevant portion: \n {talk.relevant_paragraph}"
                if talk.relevant_paragraph
                else f"Talk:\n {talk.text}"
                for talk in relevant_talks
            ]
        )
        return await self.extract_talks_insights(
            curriculum_string=curriculum_string,
            scripture_text=scripture_text,
            conference_talks=talks_string,
        )

    async def get_language_insights(
        self, scripture_text: str, cfm_curriculum: curriculum.ComeFollowMeCurriculum
    ) -> ScriptureInsights:
        """Get language insights from a set of scriptures.

        Args:
            scripture_text: The text of the scripture to extract insights from.
            cfm_curriculum: The Come, Follow Me curriculum to generate insights from.

        Returns:
            The generated language insights.

        """
        strongs_dictionary = await strongs.get_strongs()
        strongs_references = strongs_dictionary.find_relevant_strongs_entries(scripture_text)
        return await self.extract_language_insights(
            curriculum_string=cfm_curriculum.scripture_reference,
            scripture_text=scripture_text,
            strongs_entries=strongs_references,
        )

    @staticmethod
    @ScriptureInsights.async_cache_pydantic_model
    @magentic.chatprompt(
        magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
        magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
        magentic.UserMessage(
            "Here are some entries from Strong's Hebrew Dictionary that may or may not be relevant. If they're not "
            "relevant, ignore them. If they may provide insight, feel free to use them in your insights."
            "\n\n{strongs_entries}"
        ),
        magentic.UserMessage(LANGUAGE_INSIGHT_EXTRACTION_SYSTEM_PROMPT),
    )
    async def extract_language_insights(
        curriculum_string: str, scripture_text: str, strongs_entries: dict[str, strongs.HebrewSummary]
    ) -> ScriptureInsights:
        """Generate language insights from a set of scriptures.

        Args:
            curriculum_string: The title of the curriculum.
            scripture_text: The text of the scripture to extract insights from.
            strongs_entries: The Strong's Hebrew dictionary entries.

        Returns:
            The generated scripture insights.

        """
        ...

    @staticmethod
    @ScriptureInsights.async_cache_pydantic_model
    @magentic.chatprompt(
        magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
        magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
        magentic.UserMessage(SCRIPTURE_INSIGHT_EXTRACTION_SYSTEM_PROMPT),
    )
    async def extract_scripture_insights(curriculum_string: str, scripture_text: str) -> ScriptureInsights:
        """Generate insights from a set of scriptures.

        Args:
            curriculum_string: The title of the curriculum.
            scripture_text: The text of the scripture to extract insights from.

        Returns:
            The generated scripture insights.

        """
        ...

    @staticmethod
    @ScriptureInsights.async_cache_pydantic_model
    @magentic.chatprompt(
        magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
        magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
        magentic.UserMessage(CURRICULUM_INSIGHT_EXTRACTION_SYSTEM_PROMPT),
    )
    async def extract_curriculum_insights(
        curriculum_string: str, scripture_text: str, curriculum_text: str
    ) -> ScriptureInsights:
        """Generate Come, Follow Me curriculum insights from a set of scriptures.

        Args:
            curriculum_string: The title of the curriculum.
            scripture_text: The text of the scripture to extract insights from.
            curriculum_text: The text of the curriculum to extract insights from.

        Returns:
            The generated scripture insights.

        """
        ...

    @staticmethod
    @ScriptureInsights.async_cache_pydantic_model
    @magentic.chatprompt(
        magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
        magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
        magentic.UserMessage(CITATION_INDEX_EXTRACTION_SYSTEM_PROMPT),
    )
    async def extract_talks_insights(
        curriculum_string: str, scripture_text: str, conference_talks: str
    ) -> ScriptureInsights:
        """Generate General Conference talk insights from a set of scriptures.

        Args:
            curriculum_string: The title of the curriculum.
            scripture_text: The text of the scripture to extract insights from.
            conference_talks: The text of the curriculum to extract insights from.

        Returns:
            The generated scripture insights.

        """
        ...

    @staticmethod
    @ScriptureInsights.async_cache_pydantic_model
    @magentic.chatprompt(
        magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
        magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
        magentic.UserMessage(
            "Here are some entries about ancient symbols that may or may not be relevant. If they're not "
            "relevant, ignore them. If they may provide insight, feel free to use them in your insights."
            "\n\n{ancient_symbols}"
        ),
        magentic.UserMessage(LANGUAGE_INSIGHT_EXTRACTION_SYSTEM_PROMPT),
    )
    async def extract_ancient_tradition_insights(
        curriculum_string: str, scripture_text: str, ancient_symbols: list[str]
    ) -> ScriptureInsights:
        """Generate language insights from a set of scriptures.

        Args:
            curriculum_string: The title of the curriculum.
            scripture_text: The text of the scripture to extract insights from.
            ancient_symbols: The ancient symbols to extract insights from.

        Returns:
            The generated scripture insights.

        """
        ...


@EpisodeOutline.async_cache_pydantic_model
@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
    magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
    magentic.UserMessage(
        """\
Here are the scripture insights you have previously generated:

{scripture_insights}

Please remember to pull from the best insights to make the episode outline as engaging and uplifting as possible.
Feel free to include personal anecdotes or insights. The content should not just be generic.
Please also be sure to use references from every chapter in the curriculum."""
    ),
)
async def generate_episode_outline(curriculum_string: str, scripture_insights: ScriptureInsights) -> EpisodeOutline:
    """Generate an episode outline from a curriculum.

    Args:
        curriculum_string: The title of the curriculum.
        scripture_insights: The insights from the scripture.

    Returns:
        The generated episode outline.

    """
    ...


@Episode.async_cache_pydantic_model
@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_OUTLINE_GENERATION_SYSTEM_PROMPT),
    magentic.UserMessage(f"This is Joshua Graham's background\n\n{JOSHUA_GRAHAM_BACKGROUND_TEXT}"),
    magentic.UserMessage(EPISODE_FLESH_OUT_GENERATION_PROMPT),
)
async def generate_episode(curriculum_string: str, episode_outline: EpisodeOutline) -> Episode:
    """Generate a full podcast episode from an episode outline.

    Args:
        curriculum_string: The title of the curriculum.
        episode_outline: The episode outline to generate the episode from.

    Returns:
        The generated episode.

    """
    ...


@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_SUMMARY_GENERATION_PROMPT),
    magentic.UserMessage("Please write the YouTube video description for the episode {episode.title}"),
)
async def generate_video_description(episode: Episode) -> str:
    """Generate a video description for a podcast episode.

    Args:
        episode: The episode to generate the description for.

    Returns:
        The video description.

    """
    ...


@magentic.chatprompt(
    magentic.SystemMessage(CORRELATION_SYSTEM_PROMPT),
)
async def correlate_episode(episode: Episode) -> str:
    """Correlate an episode to ensure doctrinal accuracy and spiritual uplift.

    Args:
        episode: The episode to correlate.

    Returns:
        The correlated episode.

    """
    ...


@magentic.chatprompt(
    magentic.SystemMessage(EPISODE_FLESH_OUT_GENERATION_PROMPT),
    magentic.UserMessage("These are the criticisms from the Correlation Committee:\n\n{correlation_feedback}"),
    magentic.UserMessage(
        "Please revise the episode outline based on the feedback. Make sure to address each criticism if needed, "
        "ensuring that the episode is doctrinally sound, spiritually uplifting, and engaging, which invites all to "
        "come unto Jesus Christ."
    ),
)
async def revise_episode(episode_outline: Episode, correlation_feedback: str) -> Episode:
    """Revise an episode based on feedback.

    Args:
        episode_outline: The episode outline to revise.
        correlation_feedback: The feedback from the Correlation Committee.

    Returns:
        The revised episode outline.

    """
    ...
