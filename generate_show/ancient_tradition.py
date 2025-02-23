"""A module for extracting information from the Ancient Tradition podcast."""

import asyncio
import datetime
import itertools
import re

import bm25s
import httpx
import magentic
import pydantic
import tqdm
from bs4 import BeautifulSoup

from generate_show import curriculum, models
from generate_show.strongs import REMOVE_PUNCTUATION_AND_NUMBERS

limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
ASYNC_CLIENT = httpx.AsyncClient(limits=limits)
EPISODE_REGEX = re.compile(r"(\d+)-[a-z-]+")


class TranscriptSegment(pydantic.BaseModel):
    """A segment of a transcript."""

    start_time: datetime.timedelta = pydantic.Field(description="The start time of the segment.")
    text: str = pydantic.Field(description="The text of the segment.")


class Transcript(pydantic.BaseModel):
    """A transcript of an episode."""

    segments: list[TranscriptSegment] = pydantic.Field(description="The segments of the transcript.")

    @property
    def text(self) -> str:
        """Get the text of the transcript."""
        return "\n".join(segment.text for segment in self.segments)


class AncientTraditionEpisode(models.CacheModel):
    """An episode of the Ancient Tradition podcast."""

    title: str
    number: int
    transcript: Transcript
    # TODO: Capture links to podcast on spotify/youtube
    # TODO: Capture additional show-notes

    @classmethod
    def parse_from_html(cls, html: str, episode_no: int) -> "AncientTraditionEpisode":
        """Parse an episode from HTML.

        Args:
            html: The HTML of the episode.
            episode_no: The episode number.

        Returns:
            The parsed episode.

        """
        soup = BeautifulSoup(html, features="html.parser")
        title_header = soup.find("h3", class_="elementor-heading-title")
        if title_header is None:
            raise ValueError(f"Could not find title header of episode {episode_no}.")
        title = title_header.text

        transcript_section = next(
            (section for section in soup.find_all("section") if "transcript" in section.get_text(strip=True).lower()),
            None,
        )
        if transcript_section is None:
            raise ValueError("Could not find transcript section")

        paragraphs = transcript_section.find_all("p")

        transcript_segments: list[TranscriptSegment] = []
        for p1, p2 in list(itertools.pairwise(paragraphs))[::2]:
            if strong_tag := p1.find("strong"):
                current_timestamp_str = strong_tag.text  # String formatted as "(HH:)?MM:SS"
                regex = re.compile(r"((\d{1,2}):)?(\d{1,2}):(\d{1,2})")
                match = regex.match(current_timestamp_str)
                assert match is not None
                current_timestamp_delta = datetime.timedelta(
                    hours=int(match[2] or 0),
                    minutes=int(match[3]),
                    seconds=int(match[4]),
                )
            else:
                current_timestamp_delta = (
                    transcript_segments[-1].start_time if transcript_segments else datetime.timedelta(0)
                )
            current_text = p2.text
            segment = TranscriptSegment(start_time=current_timestamp_delta, text=current_text)
            transcript_segments.append(segment)

        return cls(title=title, number=episode_no, transcript=Transcript(segments=transcript_segments))

    @curriculum.cache_text_file
    async def extract_symbols(self) -> str:
        """Extract symbols from the transcript.

        Returns:
            The symbols extracted from the transcript.

        """

        @magentic.chatprompt(
            magentic.SystemMessage(
                "You are an expert in comparative religion and ancient symbols. You are well-acquainted with the "
                "symbols of the ancient world. You will be given a transcript of a podcast about the Ancient Tradition."
            ),
            magentic.UserMessage(self.transcript.text),
            magentic.UserMessage(
                "Please describe all of the ancient symbols mentioned in the transcript, including citing their "
                "origins, meanings, interpretations, and any ancient texts or artifacts that they are associated with."
                " Also please include a list of synonyms and related symbols."
            ),
        )
        async def extract_symbols_prompt() -> str: ...

        return await extract_symbols_prompt()


# The class doesn't yet exist when defining the method, so we can't use the cache_pydantic_model as a decorator.
AncientTraditionEpisode.parse_from_html = AncientTraditionEpisode.cache_pydantic_model(
    AncientTraditionEpisode.parse_from_html
)  # type: ignore


async def get_episode_urls_from_sitemap() -> dict[int, str]:
    """Get the URLs of all released episodes of the Ancient Tradition.

    Returns:
        The URLs of all released episodes of the Ancient Tradition.

    """
    xml_dict: dict[int, str] = {}

    r = await ASYNC_CLIENT.get("https://theancienttradition.com/wp-sitemap-posts-page-1.xml")
    xml = r.text

    soup = BeautifulSoup(xml, features="xml")
    sitemap_tags = soup.find_all("loc")

    for loc_tag in tqdm.tqdm(sitemap_tags, desc="Extracting episode URLs..."):
        url = loc_tag.text
        suffix = url.removeprefix("https://theancienttradition.com/")
        if match := EPISODE_REGEX.match(suffix):
            episode_number = int(match.group(1))
            xml_dict[episode_number] = url

    return dict(sorted(xml_dict.items()))


async def get_episodes_from_sitemap() -> dict[int, AncientTraditionEpisode]:
    """Get all released episodes of the Ancient Tradition.

    Returns:
        All released episodes of the Ancient Tradition.

    """
    episode_urls = await get_episode_urls_from_sitemap()
    episodes_responses = await asyncio.gather(*[ASYNC_CLIENT.get(url) for url in episode_urls.values()])
    if any(response.status_code != 200 for response in episodes_responses):
        raise ValueError("One or more episode pages returned a non-200 status code")
    episodes_htmls = [response.text for response in episodes_responses]
    return {
        episode_no: AncientTraditionEpisode.parse_from_html(html, episode_no)
        for episode_no, html in tqdm.tqdm(zip(episode_urls.keys(), episodes_htmls), desc="Parsing episodes...")
    }


async def get_symbols_from_episodes() -> dict[int, str]:
    """Get the symbols from all released episodes of the Ancient Tradition.

    Returns:
        The symbols from all released episodes of the Ancient Tradition.

    """
    episodes = await get_episodes_from_sitemap()
    return {
        episode_no: await episode.extract_symbols()
        for episode_no, episode in tqdm.tqdm(episodes.items(), desc="Extracting symbols")
    }


class Symbols(models.CacheModel):
    """A list of ancient religious symbols."""

    symbols: list[str] = pydantic.Field(
        description="A list of ancient religious symbols, with each entry providing a description of the symbol."
    )

    def find_relevant_symbols(self, query: str, num_symbols: int = 5) -> list[str]:
        """Find relevant symbols entries based on a query.

        Args:
            query: The query to search for in the symbols explanations.
            num_symbols: The maximum number of symbol explanations to return.

        Returns:
            A list of relevant symbol explanations.

        """
        words = query.split()
        # TODO: find a better filtering heuristic. This is too aggressive filtering. But if we don't filter irrelevant
        # words, we get too many irrelevant results, and exceed our API rate limit.
        words_filtered = {re.sub(REMOVE_PUNCTUATION_AND_NUMBERS, "", word) for word in words}  # Ignore short words
        words_filtered = {word for word in words if len(word) > 3}

        # TODO: Find a faster way to search for relevant strongs entries. Some kind of database/index.
        #  This seems to be fast enough, though.
        def filter_query(h: str) -> bool:
            return any(word in h for word in words_filtered)

        heurstic_filtered = [v for v in self.symbols if filter_query(v)]

        corpus = heurstic_filtered
        retriever = bm25s.BM25(corpus=corpus)
        retriever.index(bm25s.tokenize(corpus))

        results, _ = retriever.retrieve(bm25s.tokenize(query), k=min(num_symbols, len(corpus)))
        return results[0].tolist()


async def get_symbols() -> Symbols:
    """Get the symbol explanations for all released episodes of the Ancient Tradition.

    Returns:
        The symbol explanations for all released episodes of the Ancient Tradition.

    """
    symbols_per_episode = await get_symbols_from_episodes()
    return Symbols(symbols=list(symbols_per_episode.values()))


if __name__ == "__main__":
    episodes = asyncio.run(get_episodes_from_sitemap())
    print(episodes)

    symbols_str = asyncio.run(get_symbols_from_episodes())

    print(symbols_str)

    symbols = Symbols(symbols=list(symbols_str.values()))

    print("================================\n\n\nRelevant symbols")
    relevant_symbols = symbols.find_relevant_symbols("The rising sun over the horizon above the many waters.")
    print(relevant_symbols)
