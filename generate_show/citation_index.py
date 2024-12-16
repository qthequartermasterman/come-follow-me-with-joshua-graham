"""Functions to get talks from the BYU Scripture Citation Index that reference a scripture."""

import asyncio
import re
from typing import cast

import bm25s
import bs4
import httpx

from generate_show import models, scripture_reference

GET_VERSES_URL = "https://scriptures.byu.edu/citation_index/citation_ajax/Any/1830/2024/all/s/f/{book_number}/{chapter_number}?verses="
GET_TALKS_REFERENCES_URL = GET_VERSES_URL + "{verse_reference}"
GET_TALK_URL = "https://scriptures.byu.edu/content/talks_ajax/{talk_number}/"

GET_VERSE_REFERENCES_REGEX = re.compile(r"getSci\('\d+', '\d+', '([\d\-,]+)', '\d*'\)")
GET_TALK_REFERENCE_REGEX = re.compile(r"getTalk\('(\d+)', '(\d+)'")


timeouts = httpx.Timeout(30.0, pool=None)
limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
ASYNC_CLIENT = httpx.AsyncClient(timeout=timeouts, limits=limits)


CITATION_INDEX_BOOK_NUMBERS = {
    scripture_reference.Book.GENESIS: 101,
    scripture_reference.Book.EXODUS: 102,
    scripture_reference.Book.LEVITICUS: 103,
    scripture_reference.Book.NUMBERS: 104,
    scripture_reference.Book.DEUTERONOMY: 105,
    scripture_reference.Book.JOSHUA: 106,
    scripture_reference.Book.JUDGES: 107,
    scripture_reference.Book.RUTH: 108,
    scripture_reference.Book.SAMUEL1: 109,
    scripture_reference.Book.SAMUEL2: 110,
    scripture_reference.Book.KINGS1: 111,
    scripture_reference.Book.KINGS2: 112,
    scripture_reference.Book.CHRONICLES1: 113,
    scripture_reference.Book.CHRONICLES2: 114,
    scripture_reference.Book.EZRA: 115,
    scripture_reference.Book.NEHEMIAH: 116,
    scripture_reference.Book.ESTHER: 117,
    scripture_reference.Book.JOB: 118,
    scripture_reference.Book.PSALMS: 119,
    scripture_reference.Book.PROVERBS: 120,
    scripture_reference.Book.ECCLESIASTES: 121,
    scripture_reference.Book.SONG_OF_SOLOMON: 122,
    scripture_reference.Book.ISAIAH: 123,
    scripture_reference.Book.JEREMIAH: 124,
    scripture_reference.Book.LAMENTATIONS: 125,
    scripture_reference.Book.EZEKIEL: 126,
    scripture_reference.Book.DANIEL: 127,
    scripture_reference.Book.HOSEA: 128,
    scripture_reference.Book.JOEL: 129,
    scripture_reference.Book.AMOS: 130,
    scripture_reference.Book.OBADIAH: 131,
    scripture_reference.Book.JONAH: 132,
    scripture_reference.Book.MICAH: 133,
    scripture_reference.Book.NAHUM: 134,
    scripture_reference.Book.HABAKKUK: 135,
    scripture_reference.Book.ZEPHANIAH: 136,
    scripture_reference.Book.HAGGAI: 137,
    scripture_reference.Book.ZECHARIAH: 138,
    scripture_reference.Book.MALACHI: 139,
    scripture_reference.Book.MATTHEW: 140,
    scripture_reference.Book.MARK: 141,
    scripture_reference.Book.LUKE: 142,
    scripture_reference.Book.JOHN: 143,
    scripture_reference.Book.ACTS: 144,
    scripture_reference.Book.ROMANS: 145,
    scripture_reference.Book.CORINTHIANS1: 146,
    scripture_reference.Book.CORINTHIANS2: 147,
    scripture_reference.Book.GALATIANS: 148,
    scripture_reference.Book.EPHESIANS: 149,
    scripture_reference.Book.PHILIPPIANS: 150,
    scripture_reference.Book.COLOSSIANS: 151,
    scripture_reference.Book.THESSALONIANS1: 152,
    scripture_reference.Book.THESSALONIANS2: 153,
    scripture_reference.Book.TIMOTHY1: 154,
    scripture_reference.Book.TIMOTHY2: 155,
    scripture_reference.Book.TITUS: 156,
    scripture_reference.Book.PHILEMON: 157,
    scripture_reference.Book.HEBREWS: 158,
    scripture_reference.Book.JAMES: 159,
    scripture_reference.Book.PETER1: 160,
    scripture_reference.Book.PETER2: 161,
    scripture_reference.Book.JOHN1: 162,
    scripture_reference.Book.JOHN2: 163,
    scripture_reference.Book.JOHN3: 164,
    scripture_reference.Book.JUDE: 165,
    scripture_reference.Book.REVELATION: 166,
    scripture_reference.Book.NEPHI1: 205,
    scripture_reference.Book.NEPHI2: 206,
    scripture_reference.Book.JACOB: 207,
    scripture_reference.Book.ENOS: 208,
    scripture_reference.Book.JAROM: 209,
    scripture_reference.Book.OMNI: 210,
    scripture_reference.Book.WORDS_OF_MORMON: 211,
    scripture_reference.Book.MOSIAH: 212,
    scripture_reference.Book.ALMA: 213,
    scripture_reference.Book.HELAMAN: 214,
    scripture_reference.Book.NEPHI3: 215,
    scripture_reference.Book.NEPHI4: 216,
    scripture_reference.Book.MORMON: 217,
    scripture_reference.Book.ETHER: 218,
    scripture_reference.Book.MORONI: 219,
    scripture_reference.Book.DOCTRINE_AND_COVENANTS: 302,
    scripture_reference.Book.MOSES: 401,
    scripture_reference.Book.ABRAHAM: 402,
    scripture_reference.Book.AOF: 406,
    scripture_reference.Book.JOSEPH_SMITH_HISTORY: 405,
    scripture_reference.Book.JOSEPH_SMITH_MATTHEW: 404,
}
"""BYU Scripture Citation Index gives each book of scripture a unique ID number. This dictionary maps the book in our
internal representation to the ID number.
"""


class Talk(models.CacheModel):
    """A talk from the BYU Scripture Citation Index."""

    text: str
    relevant_paragraph: str | None

    @property
    def header(self) -> str:
        """The header of a talk, almost always the year, the author, and the title."""
        return self.text.splitlines()[0]


async def get_verse_references(book_number: int, chapter_number: int) -> list[str]:
    """Get verse references for a chapter.

    Args:
        book_number: The book number of the scripture reference (BYU Scripture Citation Index format).
        chapter_number: The chapter number of the scripture reference.

    Returns:
        A list of verse references in BYU Scripture Citation Index format.

    """
    url = GET_VERSES_URL.format(book_number=book_number, chapter_number=chapter_number)
    response = await ASYNC_CLIENT.get(url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")

    # We want to extract the 3rd string inside of `getSci` from all `a` tags that are descended of
    # `ul.referencesblock` tags.
    references = soup.select("ul.referencesblock a")
    verse_references = []
    for reference in references:
        onclick_reference: str = cast(str, reference["onclick"])
        match = GET_VERSE_REFERENCES_REGEX.search(onclick_reference)
        if match is None:
            continue
        verse_reference = match.group(1)
        verse_references.append(verse_reference)
    return verse_references


@Talk.async_cache_pydantic_model
async def get_talk(talk_number: int, paragraph_id: int) -> Talk:
    """Get a talk.

    Args:
        talk_number: The talk number to get in BYU Scripture Citation Index format.
        paragraph_id: The paragraph id of the talk to get in BYU Scripture Citation Index format.

    Returns:
        The talk.

    """
    talk_url = GET_TALK_URL.format(talk_number=talk_number)
    talk_html = (await ASYNC_CLIENT.get(talk_url)).text
    talk_soup = bs4.BeautifulSoup(talk_html, "html.parser")
    # The full text is the text of `div#bottom-gradient`
    talk_text = talk_soup.text
    # The specific paragraph is the `p` element that has a descendant `span.citation#{paragraph_id}`
    # We want the text of the p element, not the span element.
    citation_tag = talk_soup.select_one(f"span.citation[id='{paragraph_id}']")
    relevant_paragraph = None
    if citation_tag is not None:
        paragraph_tag = citation_tag.find_parent("p")
        if paragraph_tag is not None:
            before_paragraph = paragraph_tag.find_previous_sibling("p")
            after_paragraph = paragraph_tag.find_next_sibling("p")
            before_paragraph_text = before_paragraph.text if before_paragraph else ""
            after_paragraph_text = after_paragraph.text if after_paragraph else ""
            relevant_paragraph = f"{before_paragraph_text}\n{paragraph_tag}\n{after_paragraph_text}"

    return Talk(text=talk_text, relevant_paragraph=relevant_paragraph)


async def get_talk_reference(book_number: int, chapter_number: int, verse_reference: str) -> list[Talk]:
    """Get talks that reference a verse reference (in BYU Scripture Citation Index format).

    Args:
        book_number: The book number of the scripture reference (BYU Scripture Citation Index format).
        chapter_number: The chapter number of the scripture reference.
        verse_reference: The verse reference of the scripture reference (BYU Scripture Citation Index format).

    Returns:
        A list of talks that reference the verse reference

    """
    url = GET_TALKS_REFERENCES_URL.format(
        book_number=book_number, chapter_number=chapter_number, verse_reference=verse_reference
    )

    # We want the getTalk function arguments of each `a` tag descended from `ul.referencesblock`
    response = await ASYNC_CLIENT.get(url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    talks = soup.select("ul.referencesblock a")
    talk_references = []
    for talk in talks:
        onclick_reference: str = cast(str, talk["onclick"])
        match = GET_TALK_REFERENCE_REGEX.search(onclick_reference)
        if match is None:
            continue
        talk_number, paragraph_id = match.groups()
        talk_references.append(asyncio.create_task(get_talk(int(talk_number), int(paragraph_id))))
    return await asyncio.gather(*talk_references)


async def get_talks(
    scripture_ref: scripture_reference.ScriptureReference, maximum_number_of_talks: int = 7
) -> list[Talk]:
    """Get talks that reference a scripture reference.

    The most relevant talks (determined by BM25s) are included.

    Args:
        scripture_ref: The scripture reference to get talks for.
        maximum_number_of_talks: The maximum number of talks to return.

    Returns:
        A list of talks that reference the scripture reference.

    """
    if scripture_ref.end_verse is not None and (
        scripture_ref.start_verse.book != scripture_ref.end_verse.book
        or scripture_ref.start_verse.chapter != scripture_ref.end_verse.chapter
    ):
        raise ValueError("Cannot get talks from multiple chapters.")
    verse_references = await get_verse_references(
        CITATION_INDEX_BOOK_NUMBERS[scripture_ref.start_verse.book], scripture_ref.start_verse.chapter
    )
    tasks = [
        asyncio.create_task(
            get_talk_reference(
                CITATION_INDEX_BOOK_NUMBERS[scripture_ref.start_verse.book],
                scripture_ref.start_verse.chapter,
                verse_reference,
            )
        )
        for verse_reference in verse_references
    ]
    talks: list[Talk] = []
    for task in await asyncio.gather(*tasks):
        talks.extend(task)

    corpus = [f"{i}: {talk.relevant_paragraph}" for i, talk in enumerate(talks)]
    retriever = bm25s.BM25(corpus=corpus)
    retriever.index(bm25s.tokenize(corpus))

    query = scripture_ref.get_scripture_text()

    results, _ = retriever.retrieve(bm25s.tokenize(query), k=min(maximum_number_of_talks, len(talks)))
    return_list = []
    for result in results[0]:
        key, _ = result.split(":", maxsplit=1)
        return_list.append(talks[int(key)])

    return return_list
