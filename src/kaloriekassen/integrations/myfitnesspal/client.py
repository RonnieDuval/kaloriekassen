"""Fetch MyFitnessPal diary pages using a session created in a normal browser.

MyFitnessPal rejects login attempts made in an automated browser.  Authentication
is therefore deliberately kept out of this module: log in in ordinary Chrome,
then provide the resulting Cookie request header through ``MFP_COOKIE_HEADER``.
"""

import datetime as dt
import os
import re

import requests
from lxml import html


DIARY_URL = "https://www.myfitnesspal.com/food/diary?date={date}"
COOKIE_HEADER_ENV_VAR = "MFP_COOKIE_HEADER"
REQUEST_TIMEOUT_SECONDS = 30


class MyFitnessPalAuthenticationError(RuntimeError):
    """Raised when the manually-created MyFitnessPal session is unavailable."""


def rens_tal(tekst: str) -> int:
    match = re.search(r"(-?\d+)", tekst.replace(",", ""))
    return int(match.group(1)) if match else 0


def parse_food_rows(page_html: str, dato_streng: str) -> dict:
    """Parse the food rows from an authenticated diary HTML response."""
    document = html.fromstring(page_html)
    meals: dict[str, list[dict[str, int | str]]] = {}
    current_meal: str | None = None

    for row in document.xpath('//table[contains(@class, "table0")]//tbody/tr'):
        row_classes = set((row.get("class") or "").split())
        cells = [" ".join(cell.itertext()).strip() for cell in row.xpath("./td")]

        if "meal_header" in row_classes:
            if cells:
                current_meal = cells[0]
                meals.setdefault(current_meal, [])
            continue

        if not current_meal or row_classes.intersection({"bottom", "total", "spacer"}):
            continue
        if len(cells) < 5:
            continue

        food_name = cells[0]
        if not food_name or food_name.lower() in {"add food", "quick tools"}:
            continue
        if not re.search(r"\d+", cells[1]):
            continue

        meals[current_meal].append(
            {
                "name": food_name,
                "calories": rens_tal(cells[1]),
                "carbohydrates": rens_tal(cells[2]),
                "fat": rens_tal(cells[3]),
                "protein": rens_tal(cells[4]),
                "sodium": rens_tal(cells[5]) if len(cells) > 5 else 0,
                "sugar": rens_tal(cells[6]) if len(cells) > 6 else 0,
            }
        )

    return {"date": dato_streng, "meals": meals}


def _cookie_header() -> str:
    cookie_header = os.environ.get(COOKIE_HEADER_ENV_VAR, "").strip()
    if not cookie_header:
        raise MyFitnessPalAuthenticationError(
            "MFP_COOKIE_HEADER mangler. Log ind manuelt i en almindelig browser, "
            "kopiér Cookie-headeren fra en diary-request i DevTools, og gem den i .env."
        )
    # DevTools copies request headers as ``Cookie: name=value``. Accept that
    # convenient form as well as the header value alone.
    header_name, separator, header_value = cookie_header.partition(":")
    if separator and header_name.strip().lower() == "cookie":
        return header_value.strip()
    return cookie_header


def _cookie_names(cookie_header: str) -> list[str]:
    """Return cookie names only; never include secret cookie values in errors."""
    return [
        name.strip()
        for part in cookie_header.split(";")
        if (name := part.partition("=")[0]).strip()
    ]


def _is_login_page(response: requests.Response) -> bool:
    """Return whether a response is a login page, without flagging site scripts."""
    if "/login" in response.url.lower():
        return True

    document = html.fromstring(response.text)
    return bool(document.xpath('//input[@type="password"]'))


def hent_mfp_dag(dato_streng: str) -> dict:
    """Fetch one diary date without attempting an automated MyFitnessPal login."""
    cookie_header = _cookie_header()
    response = requests.get(
        DIARY_URL.format(date=dato_streng),
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
            "Cookie": cookie_header,
            "Referer": "https://www.myfitnesspal.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    if _is_login_page(response):
        cookie_names = ", ".join(_cookie_names(cookie_header)) or "ingen"
        raise MyFitnessPalAuthenticationError(
            "MyFitnessPal-sessionen er udløbet eller blev afvist. Log ind manuelt "
            "i din almindelige browser og opdatér MFP_COOKIE_HEADER. "
            f"Svar-URL: {response.url}. Send kun cookie-navnene ved fejlsøgning: {cookie_names}."
        )

    return parse_food_rows(response.text, dato_streng)


def dato_interval(start_dato: dt.date, slut_dato: dt.date):
    dato = start_dato
    while dato <= slut_dato:
        yield dato
        dato += dt.timedelta(days=1)


def hent_mfp_interval(start_dato: str, slut_dato: str | None = None) -> list[dict]:
    start = dt.date.fromisoformat(start_dato)
    slut = dt.date.fromisoformat(slut_dato) if slut_dato else dt.date.today()
    resultater = []

    for dato in dato_interval(start, slut):
        dato_streng = dato.isoformat()
        print(f"Henter MFP for {dato_streng}")
        resultater.append(hent_mfp_dag(dato_streng))

    return resultater


def hent_mfp_seneste_dage(antal_dage: int = 7) -> list[dict]:
    slut = dt.date.today()
    start = slut - dt.timedelta(days=antal_dage - 1)
    return hent_mfp_interval(start.isoformat(), slut.isoformat())
