"""Utilties for parsing scripture references.

Most of these eventually should be ported over to pyscripture, but for now they are here.
"""

import enum
import re
from typing import Any

import pydantic
from annotated_types import Gt
from typing_extensions import Annotated, Self

# TODO: Support end book and JS-H in this regex
# TODO: support commas
SCRIPTUREVERSE_REGEX = re.compile(
    r"(\d*\s*[a-zA-Z\s]+)\s*(\d+)(?::(\d+))?(\s*-\s*(\d*\s*[a-zA-Z\s]+)?\s*(\d+)(?:\s*([a-z]+)\s*(\d+))?(?::(\d+))?)?"
)


class Book(str, enum.Enum):
    """The books of scripture."""

    GENESIS = "Genesis"
    EXODUS = "Exodus"
    LEVITICUS = "Leviticus"
    NUMBERS = "Numbers"
    DEUTERONOMY = "Deuteronomy"
    JOSHUA = "Joshua"
    JUDGES = "Judges"
    RUTH = "Ruth"
    SAMUEL1 = "1 Samuel"
    SAMUEL2 = "2 Samuel"
    KINGS1 = "1 Kings"
    KINGS2 = "2 Kings"
    CHRONICLES1 = "1 Chronicles"
    CHRONICLES2 = "2 Chronicles"
    EZRA = "Ezra"
    NEHEMIAH = "Nehemiah"
    ESTHER = "Esther"
    JOB = "Job"
    PSALMS = "Psalms"
    PROVERBS = "Proverbs"
    ECCLESIASTES = "Ecclesiastes"
    SONG_OF_SOLOMON = "Song of Solomon"
    ISAIAH = "Isaiah"
    JEREMIAH = "Jeremiah"
    LAMENTATIONS = "Lamentations"
    EZEKIEL = "Ezekiel"
    DANIEL = "Daniel"
    HOSEA = "Hosea"
    JOEL = "Joel"
    AMOS = "Amos"
    OBADIAH = "Obadiah"
    JONAH = "Jonah"
    MICAH = "Micah"
    NAHUM = "Nahum"
    HABAKKUK = "Habakkuk"
    ZEPHANIAH = "Zephaniah"
    HAGGAI = "Haggai"
    ZECHARIAH = "Zechariah"
    MALACHI = "Malachi"
    MATTHEW = "Matthew"
    MARK = "Mark"
    LUKE = "Luke"
    JOHN = "John"
    ACTS = "Acts"
    ROMANS = "Romans"
    CORINTHIANS1 = "1 Corinthians"
    CORINTHIANS2 = "2 Corinthians"
    GALATIANS = "Galatians"
    EPHESIANS = "Ephesians"
    PHILIPPIANS = "Philippians"
    COLOSSIANS = "Colossians"
    THESSALONIANS1 = "1 Thessalonians"
    THESSALONIANS2 = "2 Thessalonians"
    TIMOTHY1 = "1 Timothy"
    TIMOTHY2 = "2 Timothy"
    TITUS = "Titus"
    PHILEMON = "Philemon"
    HEBREWS = "Hebrews"
    JAMES = "James"
    PETER1 = "1 Peter"
    PETER2 = "2 Peter"
    JOHN1 = "1 John"
    JOHN2 = "2 John"
    JOHN3 = "3 John"
    JUDE = "Jude"
    REVELATION = "Revelation"
    NEPHI1 = "1 Nephi"
    NEPHI2 = "2 Nephi"
    JACOB = "Jacob"
    ENOS = "Enos"
    JAROM = "Jarom"
    OMNI = "Omni"
    WORDS_OF_MORMON = "Words of Mormon"
    MOSIAH = "Mosiah"
    ALMA = "Alma"
    HELAMAN = "Helaman"
    NEPHI3 = "3 Nephi"
    NEPHI4 = "4 Nephi"
    MORMON = "Mormon"
    ETHER = "Ether"
    MORONI = "Moroni"
    DOCTRINE_AND_COVENANTS = "Doctrine and Covenants"
    MOSES = "Moses"
    ABRAHAM = "Abraham"
    AOF = "Articles of Faith"


class Verse(pydantic.BaseModel, frozen=True):
    """A verse in scripture."""

    book: Book = pydantic.Field(
        description="The name of the book of scripture.", examples=["Alma", "3 Nephi", "Helaman", "Ether", "Moroni"]
    )
    chapter: Annotated[int, Gt(0)] = pydantic.Field(description="The chapter of the verse.", examples=[1, 2, 3, 4, 5])
    verse: Annotated[int, Gt(0)] | None = pydantic.Field(description="The verse number.", examples=[1, 2, 3, 4, 5])

    @pydantic.field_validator("book", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        """Remove leading and trailing whitespace from the book name."""
        return value.strip()

    def __lt__(self, other: "Verse" | Any) -> bool:
        """Compare two verses based on their book, chapter, and verse.

        Args:
            other: The verse to compare against.

        Returns:
            True if this verse is less than the other verse, False otherwise.

        """
        if not isinstance(other, Verse):
            return NotImplemented
        if self.book != other.book:
            return NotImplemented
        return (self.chapter, self.verse) < (other.chapter, other.verse)

    def __str__(self):
        """Return the canonical string representation of the verse."""
        string = self.book
        if self.chapter is not None:
            string += f" {self.chapter}"
        if self.verse is not None:
            string += f":{self.verse}"
        return string


class ScriptureReference(pydantic.BaseModel, frozen=True):
    """A reference to a range of scripture verses."""

    start_verse: Verse = pydantic.Field(description="The starting verse of the reference.")
    end_verse: Verse | None = pydantic.Field(description="The ending verse of the reference.")

    def __str__(self) -> str:
        """Return the canonical string representation of the scripture reference."""
        string = str(self.start_verse)
        if self.end_verse is None or self.start_verse == self.end_verse:
            return string
        string += "-"
        if self.start_verse.book != self.end_verse.book or self.end_verse.verse is None:
            string += str(self.end_verse)
            return string
        if self.start_verse.chapter != self.end_verse.chapter:
            string += f"{self.end_verse.chapter}:"
        if self.start_verse.verse != self.end_verse.verse and self.end_verse.verse is not None:
            string += f"{self.end_verse.verse}"
        if string[-1] == ":":
            string = string[:-1]
        return string

    @pydantic.model_validator(mode="after")
    def verify_start_end(self):
        """Ensure that the start verse is less than or equal to the end verse."""
        if self.end_verse is None:
            return self
        if self.end_verse == self.start_verse:
            return ScriptureReference(start_verse=self.start_verse, end_verse=None)
        return self

    def __eq__(self, other: "ScriptureReference" | Any) -> bool:
        """Compare two scripture references for equality.

        Args:
            other: The scripture reference to compare against.

        Returns:
            True if the scripture references are equal, False otherwise.

        """
        if not isinstance(other, ScriptureReference):
            return False
        if self.start_verse != other.start_verse:
            return False
        if self.end_verse is None and (other.end_verse is None or other.start_verse == other.end_verse):
            return True
        if other.end_verse is None and self.start_verse == self.end_verse:
            return True
        return self.end_verse == other.end_verse

    @classmethod
    def from_string(cls, ref: str) -> Self:
        """Create a scripture reference from a string.

        Args:
            ref: The string representation of the scripture reference.

        Returns:
            A scripture reference object.

        """
        match = SCRIPTUREVERSE_REGEX.match(ref)
        if match is None:
            raise ValueError(f"Invalid scripture reference: {ref}")
        start_book = match.group(1).strip()
        start_chapter = int(match.group(2))
        start_verse = int(match.group(3)) if match.group(3) else None
        end_book = match.group(5).strip() if match.group(5) else None
        end_chapter = int(match.group(6)) if match.group(6) else None
        end_verse = int(match.group(9)) if match.group(9) else None

        # Match group 6 does double duty. It's the end chapter is there is also a verse after a second colon, or it's
        # the end verse if there is no second colon.
        if end_chapter is not None and end_verse is None and end_book is None:
            end_verse = end_chapter
            end_chapter = start_chapter

        end_book_obj = Book(end_book if end_book is not None else start_book)

        if end_chapter is None and end_verse is None:
            end_verse_obj = None
        elif end_chapter is None:
            end_verse_obj = Verse(book=end_book_obj, chapter=start_chapter, verse=end_verse)
        else:
            end_verse_obj = Verse(book=end_book_obj, chapter=end_chapter, verse=end_verse)

        # TODO: support end_book
        return cls(
            start_verse=Verse(book=Book(start_book), chapter=start_chapter, verse=start_verse),
            end_verse=end_verse_obj,
        )
