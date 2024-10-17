"""Strong's Hebrew dictionary utilities."""

import functools
import re

import bm25s
import httpx
import pydantic

REMOVE_PUNCTUATION_AND_NUMBERS = re.compile(r"[^a-zA-Z\s]")


class Word(pydantic.BaseModel, frozen=True):
    """A word in the Strong's Hebrew dictionary."""

    pos: str
    pron: str
    xlit: str
    src: str
    w: str


class Hebrew(pydantic.BaseModel, frozen=True):
    """A Hebrew entry in the Strong's Hebrew dictionary."""

    w: Word
    source: str
    meaning: str
    usage: str
    note: str

    def summary(self) -> "HebrewSummary":
        """Get a summary of the Hebrew entry."""
        return HebrewSummary(
            word=self.w.w,
            pronunciation=self.w.pron,
            source=self.source,
            meaning=self.meaning,
            usage=self.usage,
            note=self.note,
        )


class HebrewSummary(pydantic.BaseModel, frozen=True):
    """A Hebrew entry in the Strong's Hebrew dictionary."""

    word: str
    pronunciation: str
    source: str
    meaning: str
    usage: str
    note: str

    @pydantic.field_validator("source", "meaning", "usage", "note")
    @classmethod
    def strip_xml_tags(cls, value: str) -> str:
        """Strip XML tags from a string.

        The Strong's Hebrew dictionary contains XML tags that we want to remove because they provide no additional
        context beyond the structure that we enforce in the `Hebrew` class.

        Args:
            value: The value to strip XML tags from.

        Returns:
            The value with XML tags stripped.

        """
        return re.sub(r"<[^>]+>", "", value)


class Strong(pydantic.BaseModel, frozen=True):
    """The Strong's Hebrew dictionary."""

    dictionary: dict[str, Hebrew]
    mapping: dict[str, str]

    def find_relevant_strongs_entries(self, query: str, num_strong_results: int = 5) -> dict[str, HebrewSummary]:
        """Find relevant Strong's Hebrew entries based on a query.

        Args:
            query: The query to search for in the Strong's Hebrew dictionary.
            num_strong_results: The maximum number of Strong's Hebrew entries to return.

        Returns:
            A dictionary of relevant Strong's Hebrew entries.

        """
        words = query.split()
        # TODO: find a better filtering heuristic. This is too aggressive filtering. But if we don't filter irrelevant
        # words, we get too many irrelevant results, and exceed our API rate limit.
        words_filtered = {re.sub(REMOVE_PUNCTUATION_AND_NUMBERS, "", word) for word in words}  # Ignore short words
        words_filtered = {word for word in words if len(word) > 3}

        # TODO: Find a faster way to search for relevant strongs entries. Some kind of database/index.
        #  This seems to be fast enough, though.
        def filter_query(h: Hebrew) -> bool:
            return any(word in h.source or word in h.meaning or word in h.usage for word in words_filtered)

        heurstic_filtered = {k: v.summary() for k, v in self.dictionary.items() if filter_query(v)}

        corpus = [f"{k}: {str(v)}" for k, v in heurstic_filtered.items()]
        retriever = bm25s.BM25(corpus=corpus)
        retriever.index(bm25s.tokenize(corpus))

        results, _ = retriever.retrieve(bm25s.tokenize(query), k=num_strong_results)
        return_dictionary = {}
        for result in results[0]:
            key, _ = result.split(":", maxsplit=1)
            return_dictionary[key] = heurstic_filtered[key]
        return return_dictionary


@functools.lru_cache(maxsize=1)
def get_strongs() -> Strong:
    """Get the Strong's Hebrew dictionary.

    Returns:
        The Strong's Hebrew dictionary.

    """
    response = httpx.get(
        "https://raw.githubusercontent.com/openscriptures/HebrewLexicon/refs/heads/master/sinri/json/StrongHebrewDictionary.json"
    )
    json = response.json()
    json["dictionary"] = json.pop("dict")
    return Strong(**json)
