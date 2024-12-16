"""Utilties for parsing scripture references.

Most of these eventually should be ported over to pyscripture, but for now they are here.
"""

import collections
import enum
import functools
import hashlib
import re
from typing import Any, Callable

import pydantic
import requests
from annotated_types import Gt
from typing_extensions import Annotated, ParamSpec, Self

P = ParamSpec("P")

# TODO: support commas
DASHES_REGEX = r"[–\-—-]"
BOOK_NAME_REGEX = rf"(?:\d*\s*[a-zA-Z\s]+|Joseph Smith{DASHES_REGEX}(?:History|Matthew))"
SCRIPTUREVERSE_REGEX = re.compile(
    rf"({BOOK_NAME_REGEX})\s*(\d+)(?::(\d+))?(\s*{DASHES_REGEX}\s*({BOOK_NAME_REGEX})?\s*(\d+)(?:\s*([a-z]+)\s*(\d+))?(?::(\d+))?)?"
)


class ScriptureReferenceError(ValueError):
    """An error in a scripture reference."""


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
    JOSEPH_SMITH_HISTORY = "Joseph Smith—History"
    JOSEPH_SMITH_MATTHEW = "Joseph Smith—Matthew"


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

    def __lt__(self, other: "Verse | Any") -> bool:
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
        if (
            self.start_verse.book == self.end_verse.book
            and self.start_verse.verse is None
            and self.end_verse.verse is None
        ):
            string += str(self.end_verse.chapter)
            return string

        if self.start_verse.book != self.end_verse.book or self.end_verse.verse is None:
            string += str(self.end_verse)
            return string
        if self.start_verse.chapter != self.end_verse.chapter or (
            self.start_verse.book == self.end_verse.book
            and self.start_verse.verse is None
            and self.end_verse.verse is not None
        ):
            string += f"{self.end_verse.chapter}"
            if self.end_verse.verse is not None:
                string += ":"
        if self.end_verse.verse is not None:
            string += f"{self.end_verse.verse}"
        return string

    @pydantic.model_validator(mode="after")
    def verify_start_end(self):
        """Ensure that the start verse is less than or equal to the end verse."""
        if self.end_verse is None:
            return self
        if self.end_verse == self.start_verse:
            return ScriptureReference(start_verse=self.start_verse, end_verse=None)
        return self

    def __eq__(self, other: "ScriptureReference | Any") -> bool:
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
            raise ScriptureReferenceError(f"Invalid scripture reference: {ref}")
        start_book = match.group(1).strip()
        start_chapter = int(match.group(2))
        start_verse = int(match.group(3)) if match.group(3) else None
        end_book = match.group(5).strip() if match.group(5) else None
        end_chapter = int(match.group(6)) if match.group(6) else None
        end_verse = int(match.group(9)) if match.group(9) else None

        # Match group 6 does double duty. It's the end chapter is there is also a verse after a second colon, or it's
        # the end verse if there is no second colon.
        if ref.count(":") == 1 and end_chapter is not None and end_verse is None and end_book is None:
            end_verse = end_chapter
            end_chapter = start_chapter

        # Replace any whitespace characters (like \xa0) with spaces
        start_book = re.sub(r"\s+", " ", start_book)
        start_book = re.sub(rf"Joseph Smith{DASHES_REGEX}", "Joseph Smith—", start_book)
        # start_book = start_book.replace("Joseph Smith-", "Joseph Smith—")
        if end_book is not None:
            end_book = re.sub(r"\s+", " ", end_book)
            # end_book = end_book.replace("Joseph Smith-", "Joseph Smith—")
            end_book = re.sub(rf"Joseph Smith{DASHES_REGEX}", "Joseph Smith—", end_book)

        end_book_obj = Book(end_book if end_book is not None else start_book)

        if end_chapter is None and end_verse is None:
            end_verse_obj = None
        elif end_chapter is None:
            end_verse_obj = Verse(book=end_book_obj, chapter=start_chapter, verse=end_verse)
        else:
            end_verse_obj = Verse(book=end_book_obj, chapter=end_chapter, verse=end_verse)

        return cls(
            start_verse=Verse(book=Book(start_book), chapter=start_chapter, verse=start_verse),
            end_verse=end_verse_obj,
        )

    def get_scripture_text(self) -> str:
        """Get the text of the scripture reference.

        Returns:
            The text of the scripture reference.

        """
        # TODO: Use a more optimized data structure for this, so I don't have to iterate the entire standard works
        #  in the worst case. Despite the poor asymptotic complexity, this still seems to be fast enough for now.
        scriptures = get_scriptures()
        if self.end_verse is None:
            if self.start_verse.verse is not None:
                verse_text = scriptures[self.start_verse.book][self.start_verse.chapter].get(self.start_verse)
                return f"{str(self.start_verse)} {verse_text}"
            else:
                return "\n".join(
                    f"{str(verse)} {text}"
                    for verse, text in scriptures[self.start_verse.book][self.start_verse.chapter].items()
                )

        started = False
        found_end = False
        verse_texts = []
        if self.start_verse.verse is None:
            starting_verse = Verse(book=self.start_verse.book, chapter=self.start_verse.chapter, verse=1)
        else:
            starting_verse = self.start_verse
        if self.end_verse.verse is None:
            # Ending verse should be the final verse in the end_verse's chapter.
            # TODO: surely there's a better way to extract the last element from a dictionary that creating a list
            #  of its keys
            ending_verse = list(scriptures[self.end_verse.book][self.end_verse.chapter].keys())[-1]
        else:
            ending_verse = self.end_verse

        book_order: dict[Book, int] = {book: idx for idx, book in enumerate(Book)}

        for book, chapters in scriptures.items():
            if book_order[book] < book_order[starting_verse.book]:
                continue
            for chapter, verses in chapters.items():
                if book == starting_verse.book and chapter < starting_verse.chapter:
                    continue
                for verse, text in verses.items():
                    if not started:
                        if verse == starting_verse:
                            started = True
                        else:
                            continue
                    if found_end:
                        break
                    verse_texts.append(f"{str(verse)} {text}")
                    if verse == ending_verse:
                        found_end = True
                if found_end:
                    break
            if found_end:
                break

        return "\n".join(verse_texts)

    def split_chapters(self) -> list["ScriptureReference"]:
        """Split a scripture reference spanning multiple chapters or books into individual chapter references.

        Returns:
            A list of ScriptureReference objects, one for each chapter in the range, handling cases where the reference
            spans multiple books.

        """
        scripture_references = []

        # If the reference is within a single book and chapter, return it as-is
        if self.end_verse is None or (
            self.start_verse.book == self.end_verse.book and self.start_verse.chapter == self.end_verse.chapter
        ):
            return [self]

        current_chapter = self.start_verse.chapter

        # Assuming this returns the entire structure of scriptures, books, chapters, and verses
        scriptures = get_scriptures()
        book_order: dict[Book, int] = {book: idx for idx, book in enumerate(Book)}  # Order books for comparison

        # Handle the first partial chapter (starting from start_verse)
        scripture_references.append(
            ScriptureReference(
                start_verse=self.start_verse,
                end_verse=Verse(
                    book=self.start_verse.book,
                    chapter=current_chapter,
                    verse=None,  # End at the last verse in the chapter
                ),
            )
        )

        # Now handle all chapters in between
        started = False
        for book, chapters in scriptures.items():
            if book_order[book] < book_order[self.start_verse.book] or (
                started and book_order[book] > book_order[self.end_verse.book]
            ):
                continue

            if book == self.start_verse.book and not started:
                current_chapter = self.start_verse.chapter + 1
                started = True
            else:
                current_chapter = 1  # Start at the first chapter of the next book

            while current_chapter <= len(chapters):
                if book == self.end_verse.book and current_chapter == self.end_verse.chapter:
                    # Handle the last partial chapter (ending at end_verse)
                    scripture_references.append(
                        ScriptureReference(
                            start_verse=Verse(book=book, chapter=current_chapter, verse=1), end_verse=self.end_verse
                        )
                    )
                    break

                # Handle full chapters
                scripture_references.append(
                    ScriptureReference(
                        start_verse=Verse(book=book, chapter=current_chapter, verse=1),
                        end_verse=Verse(book=book, chapter=current_chapter, verse=None),
                    )
                )

                current_chapter += 1

        return scripture_references


def expected_hash(expected_sha256_hash: str) -> Callable[[Callable[P, str]], Callable[P, str]]:
    """Decorate a function to check that it returns a string with a specific hash.

    Args:
        expected_sha256_hash: The expected sha256 hash of the string returned from the decorated function.

    Raises:
        ValueError: If the hash of the returned string does not match the expected hash.

    Returns:
        A decorator that checks that the returned string has the expected hash.

    """

    def decorator(func: Callable[P, str]) -> Callable[P, str]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            downloaded_text = func(*args, **kwargs)
            actual_sha256_hash = hashlib.sha256(downloaded_text.encode()).hexdigest()
            if actual_sha256_hash != expected_sha256_hash:
                raise ValueError(
                    f"When calling {func}, Expected hash {expected_sha256_hash}, but got {actual_sha256_hash}"
                )
            return downloaded_text

        return wrapper

    return decorator


@functools.lru_cache(maxsize=1)
@expected_hash(
    expected_sha256_hash="ccbd4765243daafcf5e8536d421a93cc7037e86d6a067bfaa4c55d8f0de5ea6e"  # pragma: allowlist secret
)
def download_text() -> str:
    """Download text of all scripture from GitHub.

    Returns:
        All scripture text as a single string.

    """
    req = requests.get("http://raw.githubusercontent.com/beandog/lds-scriptures/master/text/lds-scriptures.txt")
    return req.text


@functools.lru_cache(maxsize=1)
def get_scriptures() -> dict[Book, dict[int, dict[Verse, str]]]:
    """Get the full text of the scriptures.

    The data structure is nested dicts
    {Book: {Chapter: {Verse: Text}}}

    Returns:
        The full text of the scriptures.

    """
    text = download_text()
    lines = text.splitlines()
    parsed: dict[str, str] = dict([tuple(t.split("     ", maxsplit=1)) for t in lines])  # type: ignore
    # The REGEX doesn't currently support JS-Mathew or JS-History.
    parsed = {k.strip(): v.strip() for k, v in parsed.items() if "Joseph Smith" not in k}
    scriptures: dict[Book, dict[int, dict[Verse, str]]] = collections.defaultdict(lambda: collections.defaultdict(dict))
    for ref, text in parsed.items():
        ref = ScriptureReference.from_string(ref)
        scriptures[ref.start_verse.book][ref.start_verse.chapter][ref.start_verse] = text
    return scriptures
