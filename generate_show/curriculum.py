"""Curriculum utilities for generating show notes."""

import asyncio
import datetime
import hashlib
import logging
import pathlib
from typing import Callable, Coroutine

import bs4
import httpx
from typing_extensions import ParamSpec, TypeVar

from generate_show import models

CURRICULUM_LINK = "https://www.churchofjesuschrist.org/study/manual/come-follow-me-for-home-and-church-book-of-mormon-2024/{week_number}?lang=eng"
ASYNC_CLIENT = httpx.AsyncClient()

P = ParamSpec("P")
R = TypeVar("R")


class ComeFollowMeCurriculum(models.CacheModel):
    """A model for the Come, Follow Me curriculum for a week."""

    title: str
    scripture_reference: str
    text: str

    @classmethod
    def parse_from_text(cls, text: str) -> "ComeFollowMeCurriculum":
        """Parse the curriculum text from the html text (from the Church's website).

        Args:
            text: The html text of the curriculum.

        Returns:
            The parsed curriculum text.

        """
        logging.info("Parsing curriculum text")
        soup = bs4.BeautifulSoup(text, "html.parser")
        lesson_title = soup.select(".title-number")[0].get_text()
        lesson_reference = soup.select("h1")[0].get_text()
        body = soup.find("body")
        if body is None:
            raise ValueError("Could not find body tag in curriculum text")
        curriculum_text = body.get_text()
        return cls(title=lesson_title, scripture_reference=lesson_reference, text=curriculum_text)

    @property
    def start_date(self) -> datetime.datetime:
        """Get the start date of the curriculum.

        Returns:
            The start date of the curriculum.

        """
        date_str = self.title.split("–")[0].strip() + ", 2024"
        return datetime.datetime.strptime(date_str, "%B %d, %Y")


def cache_text_file(func: Callable[P, Coroutine[None, None, str]]) -> Callable[P, Coroutine[None, None, str]]:
    """Cache the output of a function to a file.

    Args:
        func: The function to cache.

    Returns:
        The cached output of the function.

    """

    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        args_hash = hashlib.sha256((str(args) + str(kwargs)).encode("utf-8")).hexdigest()[:16]
        path = pathlib.Path("../.cache") / f"{func.__name__}-{args_hash}.txt"
        if path.exists():
            logging.info("Cache hit for %s. Using cached %s", path, func.__name__)
            return path.read_text("utf-8")
        text: str = await func(*args, **kwargs)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return text

    return wrapper


@cache_text_file
async def fetch_website_text(url: str) -> str:
    """Fetch the text of a website.

    Args:
        url: The URL of the website to fetch.

    Returns:
        The text of the website.

    """
    logging.info("Fetching website text %s", url)
    response = await ASYNC_CLIENT.get(url)
    return response.text


@ComeFollowMeCurriculum.async_cache_pydantic_model
async def fetch_curriculum(week_number: int) -> ComeFollowMeCurriculum:
    """Fetch the curriculum text for a given week number.

    Args:
        week_number: The week number of the curriculum to fetch.

    Returns:
        The text of the curriculum.

    """
    logging.info("Fetching curriculum text")
    week_number_str = str(week_number).zfill(2)
    curriculum_link = CURRICULUM_LINK.format(week_number=week_number_str)
    text = await fetch_website_text(curriculum_link)
    return ComeFollowMeCurriculum.parse_from_text(text)


async def get_all_curriculum_for_year() -> dict[int, ComeFollowMeCurriculum]:
    """Get all the curriculum for the year.

    Returns:
        A dictionary of the curriculum for each week.

    """
    curriculum_tasks = await asyncio.gather(*[fetch_curriculum(week_number) for week_number in range(1, 53)])
    return {i: task for i, task in enumerate(curriculum_tasks, start=1)}
