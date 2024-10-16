"""Tests for the scripture_reference module."""

import re

import hypothesis
import pytest
from hypothesis import strategies as st

from generate_show import scripture_reference


@hypothesis.given(
    chapter_num1=st.integers(min_value=1, max_value=100),
    chapter_num2=st.integers(min_value=1, max_value=100),
    verse_num1=st.integers(min_value=1, max_value=100),
    verse_num2=st.integers(min_value=1, max_value=100),
)
def test_verse_lt(chapter_num1: int, verse_num1: int, chapter_num2: int, verse_num2: int) -> None:
    """Test that a verse is less than another verse if the first verse is in an earlier chapter or verse."""
    verse1 = scripture_reference.Verse(book=scripture_reference.Book("Alma"), chapter=chapter_num1, verse=verse_num1)
    verse2 = scripture_reference.Verse(book=scripture_reference.Book("Alma"), chapter=chapter_num2, verse=verse_num2)
    assert (verse1 < verse2) == ((chapter_num1, verse_num1) < (chapter_num2, verse_num2))


@hypothesis.given(verse_ref=...)
def test_scripture_reference_with_none_equals_same_start_and_end(verse_ref: scripture_reference.Verse) -> None:
    """Test that a ScriptureReference object with the same start and end verse is equal to a ScriptureReference object
    with the same start verse and a None end verse.
    """
    scripture_ref = scripture_reference.ScriptureReference(start_verse=verse_ref, end_verse=verse_ref)
    scripture_ref_none_end = scripture_reference.ScriptureReference(start_verse=verse_ref, end_verse=None)
    assert scripture_ref == scripture_ref_none_end


@hypothesis.given(scripture_ref=...)
def test_scripture_reference_round_trip(scripture_ref: scripture_reference.ScriptureReference) -> None:
    """Test that a ScriptureReference object can be converted to a string and back."""
    ref_str = str(scripture_ref)
    new_scripture_ref = scripture_reference.ScriptureReference.from_string(ref_str)
    assert scripture_ref == new_scripture_ref
    assert ref_str == str(new_scripture_ref)


@pytest.mark.parametrize(
    "ref_str, ref_obj",
    [
        (
            "Jarom 1:1",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=1, verse=1),
                end_verse=None,
            ),
        ),
        (
            "Jarom 1:1-2",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=1, verse=1),
                end_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=1, verse=2),
            ),
        ),
        (
            "Jarom 1:1-2:3",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=1, verse=1),
                end_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=2, verse=3),
            ),
        ),
        (
            "Jarom 1:1-Jarom 2",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=1, verse=1),
                end_verse=scripture_reference.Verse(book=scripture_reference.Book("Jarom"), chapter=2, verse=None),
            ),
        ),
        (
            "1 Nephi 1:1",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("1 Nephi"), chapter=1, verse=1),
                end_verse=None,
            ),
        ),
        (
            "3 Nephi 1:1-4 Nephi 1",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("3 Nephi"), chapter=1, verse=1),
                end_verse=scripture_reference.Verse(book=scripture_reference.Book("4 Nephi"), chapter=1, verse=None),
            ),
        ),
        (
            "3 Nephi 1:1-4 Nephi 1:2",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("3 Nephi"), chapter=1, verse=1),
                end_verse=scripture_reference.Verse(book=scripture_reference.Book("4 Nephi"), chapter=1, verse=2),
            ),
        ),
        (
            "Words of Mormon 1:3",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(
                    book=scripture_reference.Book("Words of Mormon"), chapter=1, verse=3
                ),
                end_verse=None,
            ),
        ),
        (
            "3 Nephi 20–26",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(book=scripture_reference.Book("3 Nephi"), chapter=20, verse=None),
                end_verse=scripture_reference.Verse(book=scripture_reference.Book("3 Nephi"), chapter=26, verse=None),
            ),
        ),
        (
            "Joseph Smith—History 1:1-26",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(
                    book=scripture_reference.Book("Joseph Smith—History"), chapter=1, verse=1
                ),
                end_verse=scripture_reference.Verse(
                    book=scripture_reference.Book("Joseph Smith—History"), chapter=1, verse=26
                ),
            ),
        ),
        (
            "Joseph Smith-History 1:1-26",
            scripture_reference.ScriptureReference(
                start_verse=scripture_reference.Verse(
                    book=scripture_reference.Book("Joseph Smith—History"), chapter=1, verse=1
                ),
                end_verse=scripture_reference.Verse(
                    book=scripture_reference.Book("Joseph Smith—History"), chapter=1, verse=26
                ),
            ),
        ),
    ],
)
def test_parse_scripture_reference(ref_str: str, ref_obj: scripture_reference.ScriptureReference) -> None:
    """Test that a scripture reference is parsed correctly."""
    assert scripture_reference.ScriptureReference.from_string(ref_str) == ref_obj
    # Dashes and whitespace are stripped, so we need to account for that when doing our comparison
    joseph_smith_match = re.search(rf"Joseph Smith{scripture_reference.DASHES_REGEX}", ref_str)
    normalized_string = ref_str
    sentinel = "SENTINEL"
    if joseph_smith_match:
        normalized_string = re.sub(rf"Joseph Smith{scripture_reference.DASHES_REGEX}", sentinel, normalized_string)
    normalized_string = re.sub(scripture_reference.DASHES_REGEX, "-", re.sub(r"\s+", " ", normalized_string))
    if joseph_smith_match:
        normalized_string = normalized_string.replace(sentinel, "Joseph Smith—")
    assert str(ref_obj) == normalized_string
