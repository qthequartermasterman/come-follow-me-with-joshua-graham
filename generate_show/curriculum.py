"""Curriculum utilities for generating show notes."""

import logging
import pathlib
import hashlib
from typing_extensions import ParamSpec, TypeVar
from typing import Callable
import datetime

import bs4
import httpx
from generate_show import models

CURRICULUM_LINK = "https://www.churchofjesuschrist.org/study/manual/come-follow-me-for-home-and-church-book-of-mormon-2024/{week_number}?lang=eng"

P = ParamSpec("P")
R = TypeVar("R")

class ComeFollowMeCurriculum(models.CacheModel):
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
        curriculum_text = soup.find("body").get_text()
        return cls(title=lesson_title, scripture_reference=lesson_reference, text=curriculum_text)

    @property
    def start_date(self) -> datetime.datetime:
        """Get the start date of the curriculum.

        Returns:
            The start date of the curriculum.
        """
        date_str = self.title.split("–")[0].strip() + ", 2024"
        return datetime.datetime.strptime(date_str, "%B %d, %Y")

def cache_text_file(func: Callable[P, R]) -> Callable[P, R]:
    """Cache the output of a function to a file.

    Args:
        func: The function to cache.

    Returns:
        The cached output of the function.

    """
    def wrapper(*args:P.args, **kwargs:P.kwargs) -> R:
        args_hash = hashlib.sha256((str(args) + str(kwargs)).encode("utf-8")).hexdigest()[:16]
        path = pathlib.Path("../.cache") / f"{func.__name__}-{args_hash}.txt"
        if path.exists():
            logging.info("Cache hit for %s. Using cached %s", path, func.__name__)
            return path.read_text('utf-8')
        text: R = func(*args, **kwargs)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return text

    return wrapper

@cache_text_file
def fetch_website_text(url: str) -> str:
    """Fetch the text of a website.

    Args:
        url: The URL of the website to fetch.

    Returns:
        The text of the website.

    """
    logging.info("Fetching website text %s", url)
    response = httpx.get(url)
    return response.text


@ComeFollowMeCurriculum.cache_pydantic_model
def fetch_curriculum(week_number: int) -> ComeFollowMeCurriculum:
    """Fetch the curriculum text for a given week number.

    Args:
        week_number: The week number of the curriculum to fetch.

    Returns:
        The text of the curriculum.

    """
    logging.info("Fetching curriculum text")
    week_number_str = str(week_number).zfill(2)
    curriculum_link = CURRICULUM_LINK.format(week_number=week_number_str)
    text = fetch_website_text(curriculum_link)

    return ComeFollowMeCurriculum.parse_from_text(text)
