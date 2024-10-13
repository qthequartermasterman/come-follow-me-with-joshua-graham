"""Curriculum utilities for generating show notes."""

import logging

import bs4
import httpx

CURRICULUM_LINK = "https://www.churchofjesuschrist.org/study/manual/come-follow-me-for-home-and-church-book-of-mormon-2024/{week_number}?lang=eng"



def fetch_curriculum(week_number: int):
    """Fetch the curriculum text for a given week number.

    Args:
        week_number: The week number of the curriculum to fetch.

    Returns:
        The text of the curriculum.

    """
    logging.info("Fetching curriculum text")
    week_number_str = str(week_number).zfill(2)
    curriculum_link = CURRICULUM_LINK.format(week_number=week_number_str)
    response = httpx.get(curriculum_link)

    logging.info("Parsing curriculum text")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    lesson_title = soup.select(".title-number")[0].get_text()
    lesson_reference = soup.select("h1")[0].get_text()
    curriculum_text = soup.find("body").get_text()
    return lesson_title, lesson_reference, curriculum_text
