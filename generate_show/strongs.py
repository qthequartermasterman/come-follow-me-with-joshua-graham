"""Strong's Hebrew dictionary utilities."""

import functools

import httpx
import pydantic


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


class Strong(pydantic.BaseModel, frozen=True):
    """The Strong's Hebrew dictionary."""

    dictionary: dict[str, Hebrew]
    mapping: dict[str, str]

    def find_relevant_strongs_entries(self, query: str) -> dict[str, Hebrew]:
        """Find relevant Strong's Hebrew entries based on a query.

        Args:
            query: The query to search for in the Strong's Hebrew dictionary.

        Returns:
            A dictionary of relevant Strong's Hebrew entries.

        """

        # TODO: Find a faster way to search for relevant strongs entries. Some kind of database/index.
        #  This seems to be fast enough, though.
        def filter_query(h: Hebrew) -> bool:
            words = query.split()
            # TODO: find a better filtering heuristic
            words = {word for word in words if len(word) > 3}  # Ignore short words
            return any(word in h.source or word in h.meaning or word in h.usage for word in words)

        return {k: v for k, v in self.dictionary.items() if filter_query(v)}


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
