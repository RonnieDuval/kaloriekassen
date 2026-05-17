"""Fetch nutrition data from MyFitnessPal using the package's cookie handling."""
import datetime as dt
from http.cookiejar import CookieJar
from sys import exit
from typing import Any

import myfitnesspal
from requests.cookies import RequestsCookieJar

import settings


def _setting_value(name: str) -> str:
    """Return a stripped string setting value, even when it is unset/None."""
    return (getattr(settings, name, None) or "").strip()


def has_injected_mfp_cookies() -> bool:
    """Return whether Docker/env injected MyFitnessPal cookies are available."""
    return bool(_setting_value("MFP_COOKIE_B") and _setting_value("MFP_COOKIE_SESSION"))


def build_injected_mfp_cookiejar(
    mfp_b: str | None = None,
    mfp_session: str | None = None,
) -> CookieJar:
    """Build a cookie jar only when we explicitly inject cookies via env/Docker."""
    cookie_b = (mfp_b if mfp_b is not None else _setting_value("MFP_COOKIE_B")).strip()
    cookie_session = (
        mfp_session
        if mfp_session is not None
        else _setting_value("MFP_COOKIE_SESSION")
    ).strip()

    if not cookie_b or not cookie_session:
        raise ValueError(
            "Miljøvariablerne MFP_COOKIE_B og MFP_COOKIE_SESSION skal begge være sat "
            "for at injicere MyFitnessPal-cookies."
        )

    cookiejar = RequestsCookieJar()
    for domain in myfitnesspal.Client.COOKIE_DOMAINS:
        cookiejar.set("b", cookie_b, domain=domain, path="/")
        cookiejar.set("user_session", cookie_session, domain=domain, path="/")

    return cookiejar


def create_mfp_client() -> myfitnesspal.Client:
    """Create the MyFitnessPal client using package cookie handling by default.

    `myfitnesspal.Client()` already knows how to load browser cookies through the
    package/browser-cookie3 integration. In Docker/non-browser runs we can still
    provide `MFP_COOKIE_B` and `MFP_COOKIE_SESSION`; those are adapted into the
    CookieJar shape the package accepts, and the package handles the authenticated
    session from there.
    """
    if has_injected_mfp_cookies():
        return myfitnesspal.Client(cookiejar=build_injected_mfp_cookiejar())

    return myfitnesspal.Client()


def build_nutrition_payload(day: dt.date, totals: dict[str, Any]) -> dict[str, Any]:
    """Map MyFitnessPal totals to the payload used by the rest of the project."""
    return {
        "date": day.isoformat(),
        "calories": int(totals.get("calories", 0) or 0),
        "protein": int(totals.get("protein", 0) or 0),
        "carbohydrates": int(totals.get("carbohydrates", 0) or 0),
        "fat": int(totals.get("fat", 0) or 0),
    }


def hent_nutrition_data(day: dt.date | None = None) -> dict[str, Any]:
    """Fetch nutrition totals for a single day from MyFitnessPal."""
    target_day = day or dt.date.today()

    print("Forbinder til MyFitnessPal via myfitnesspal-pakkens cookie-håndtering...")
    client = create_mfp_client()
    diary = client.get_date(target_day)
    payload = build_nutrition_payload(target_day, diary.totals)

    print(f"Succes! Hentet data for {target_day}: {payload['calories']} kcal")
    return payload


if __name__ == "__main__":
    try:
        data = hent_nutrition_data()
    except Exception as e:
        print(f"Fejl under hentning af data fra MyFitnessPal: {e}")
        print(
            "Tjek om du er logget ind i MyFitnessPal i browseren, "
            "eller om MFP_COOKIE_B/MFP_COOKIE_SESSION er sat korrekt og ikke er udløbet."
        )
        exit(1)

    print("\nPayload klar til næste step i projektet:")
    print(data)
