import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
import datetime as dt

from playwright.sync_api import sync_playwright


if sys.platform == "win32":
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        CHROME_DIR = Path(local_app_data) / "Google/Chrome/User Data"
    else:
        CHROME_DIR = Path.home() / "AppData/Local/Google/Chrome/User Data"
elif sys.platform == "darwin":
    CHROME_DIR = Path.home() / "Library/Application Support/Google/Chrome"
else:
    CHROME_DIR = Path.home() / ".config/google-chrome"

PROFILE_DIR = Path.cwd() / "temp_chrome_profile"


def robust_copytree(src: Path, dst: Path, ignore_patterns=None):
    if not src.exists():
        print(f"Advarsel: Kilde-mappe {src} findes ikke.")
        return

    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if ignore_patterns and any(item.match(pat) for pat in ignore_patterns):
            continue

        if "lock" in item.name.lower() or item.name in {
            "SingletonCookie",
            "SingletonSocket",
            "SingletonLock",
        }:
            continue

        target = dst / item.name
        if item.is_dir():
            try:
                robust_copytree(item, target, ignore_patterns)
            except Exception as e:
                print(f"Kunne ikke kopiere mappe {item}: {e}")
        else:
            try:
                shutil.copy2(item, target)
            except (PermissionError, OSError) as e:
                print(f"Kunne ikke kopiere fil {item} (sandsynligvis låst): {e}")
            except Exception as e:
                print(f"Kunne ikke kopiere fil {item}: {e}")


def er_temp_profil_logget_ind():
    cookies_path = PROFILE_DIR / "Default" / "Network" / "Cookies"
    if not cookies_path.exists():
        cookies_path = PROFILE_DIR / "Default" / "Cookies"
        
    if not cookies_path.exists():
        return False
        
    try:
        conn = sqlite3.connect(str(cookies_path))
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM cookies WHERE host_key LIKE '%myfitnesspal%' AND name = 'user_session' LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def kopier_profil_hvis_mangler():
    if PROFILE_DIR.exists() and er_temp_profil_logget_ind():
        # Hvis den midlertidige profil allerede har en aktiv login-session, overskriver vi den ikke!
        return

    source_default = CHROME_DIR / "Default"
    target_default = PROFILE_DIR / "Default"

    skal_kopiere = False
    if not PROFILE_DIR.exists():
        skal_kopiere = True
    elif source_default.exists() and not target_default.exists():
        skal_kopiere = True
    elif not source_default.exists() and not any(PROFILE_DIR.iterdir()):
        skal_kopiere = True
    else:
        # Hvis profilen allerede findes, tjekker vi om kilde-cookies er blevet opdateret (f.eks. ved manuelt login i Chrome)
        source_cookies = CHROME_DIR / "Default" / "Network" / "Cookies"
        if not source_cookies.exists():
            source_cookies = CHROME_DIR / "Default" / "Cookies"

        target_cookies = PROFILE_DIR / "Default" / "Network" / "Cookies"
        if not target_cookies.exists():
            target_cookies = PROFILE_DIR / "Default" / "Cookies"

        if source_cookies.exists() and target_cookies.exists():
            try:
                if source_cookies.stat().st_mtime > target_cookies.stat().st_mtime:
                    print("Detekterede nyere cookies i din primære Chrome-browser. Genkopierer profil...")
                    skal_kopiere = True
            except Exception:
                pass

    if not skal_kopiere:
        return

    print("Kopierer Chrome profil...")

    ignore_patterns = ["Cache*", "Code Cache", "GPUCache", "ShaderCache"]

    if source_default.exists():
        robust_copytree(source_default, target_default, ignore_patterns)
        # Kopier også Local State (vigtigt på Windows for at kunne dekryptere cookies)
        source_local_state = CHROME_DIR / "Local State"
        target_local_state = PROFILE_DIR / "Local State"
        if source_local_state.exists():
            try:
                shutil.copy2(source_local_state, target_local_state)
            except Exception as e:
                print(f"Kunne ikke kopiere Local State: {e}")
    else:
        robust_copytree(CHROME_DIR, PROFILE_DIR, ignore_patterns)


def ryd_laasfiler():
    for path in PROFILE_DIR.rglob("*"):
        if path.is_file() and (
            "lock" in path.name.lower() or path.name == "SingletonCookie"
        ):
            try:
                path.unlink()
            except OSError:
                pass


def rens_tal(tekst):
    match = re.search(r"(-?\d+)", tekst.replace(",", ""))
    return int(match.group(1)) if match else 0


def parse_food_rows(page, dato_streng):
    meals = {}
    current_meal = None

    rows = page.locator("table.table0 tbody tr")
    antal_rows = rows.count()

    for i in range(antal_rows):
        row = rows.nth(i)
        row_class = row.get_attribute("class") or ""

        cells = [cell.strip() for cell in row.locator("td").all_inner_texts()]

        if "meal_header" in row_class:
            if cells:
                current_meal = cells[0]
                meals.setdefault(current_meal, [])
            continue

        if not current_meal:
            continue

        if "bottom" in row_class:
            continue

        if "total" in row_class:
            continue

        if "spacer" in row_class:
            continue

        # Food rows har typisk navn + calories, carbs, fat, protein, sodium, sugar
        if len(cells) < 5:
            continue

        food_name = cells[0].strip()

        # Spring tomme rækker, Add Food, Quick Tools osv. over
        if not food_name:
            continue

        if food_name.lower() in {"add food", "quick tools"}:
            continue

        # Kræv at kaloriefeltet ligner et tal
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

    return {
        "date": dato_streng,
        "meals": meals,
    }


def parse_totals(page, dato_streng):
    total_rows = page.locator("tr.total")
    total_rows.first.wait_for(state="visible", timeout=15_000)

    for i in range(total_rows.count()):
        cells = total_rows.nth(i).locator("td").all_inner_texts()
        cells = [cell.strip() for cell in cells]

        if len(cells) > 4 and re.search(r"\d+", cells[1]):
            return {
                "date": dato_streng,
                "calories": rens_tal(cells[1]),
                "carbohydrates": rens_tal(cells[2]),
                "fat": rens_tal(cells[3]),
                "protein": rens_tal(cells[4]),
                "sodium": rens_tal(cells[5]) if len(cells) > 5 else 0,
                "sugar": rens_tal(cells[6]) if len(cells) > 6 else 0,
            }

    return {
        "date": dato_streng,
        "calories": 0,
        "carbohydrates": 0,
        "fat": 0,
        "protein": 0,
        "sodium": 0,
        "sugar": 0,
    }


def hent_mfp_dag(dato_streng="2026-05-13", visible=False):
    kopier_profil_hvis_mangler()
    ryd_laasfiler()

    url = f"https://www.myfitnesspal.com/food/diary?date={dato_streng}"

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=not visible,
            channel="chrome",
            viewport={"width": 1280, "height": 1024},
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        try:
            page = context.new_page()
            page.goto(url, wait_until="load", timeout=30_000)

            if "login" in page.url and visible:
                print("\n=========================================================================")
                print("LOG IND MANUELT: Log ind i det åbnede browser-vindue.")
                print("VIGTIGT: Lad være med at lukke browser-vinduet selv!")
                print("Tryk i stedet Enter her i denne terminal, når du er færdig med at logge ind...")
                print("=========================================================================\n")
                input()
                page.goto(url, wait_until="load", timeout=30_000)

            page.locator("table.table0").wait_for(state="visible", timeout=15_000)
            page.wait_for_timeout(1_000)

            return {
                "date": dato_streng,
                "meals": parse_food_rows(page, dato_streng)["meals"],
            }

        except Exception as e:
            try:
                screenshot_path = Path.cwd() / "mfp_error_screenshot.png"
                page.screenshot(path=str(screenshot_path))
                print(f"[FEJL] Gemte fejl-screenshot til {screenshot_path}. Sidens aktuelle URL var: {page.url}")
            except Exception as se:
                print(f"[FEJL] Kunne ikke gemme fejl-screenshot: {se}")
            print(f"[FEJL] Fejl under hentning: {e}")
            return None

        finally:
            context.close()


def dato_interval(start_dato: dt.date, slut_dato: dt.date):
    dato = start_dato

    while dato <= slut_dato:
        yield dato
        dato += dt.timedelta(days=1)


def hent_mfp_interval(start_dato: str, slut_dato: str | None = None, visible=False):
    start = dt.date.fromisoformat(start_dato)
    slut = dt.date.fromisoformat(slut_dato) if slut_dato else dt.date.today()

    resultater = []

    for dato in dato_interval(start, slut):
        dato_streng = dato.isoformat()
        print(f"Henter MFP for {dato_streng}")

        data = hent_mfp_dag(dato_streng, visible=visible)

        if data is not None:
            resultater.append(data)

    return resultater


def hent_mfp_seneste_dage(antal_dage=7, visible=False):
    slut = dt.date.today()
    start = slut - dt.timedelta(days=antal_dage - 1)

    return hent_mfp_interval(
        start.isoformat(),
        slut.isoformat(),
        visible=visible,
    )

if __name__ == "__main__":
    visible = "--visible" in sys.argv

    if "--last-week" in sys.argv:
        data = hent_mfp_seneste_dage(7, visible=visible)

    elif "--from" in sys.argv:
        start_index = sys.argv.index("--from") + 1
        start_dato = sys.argv[start_index]
        data = hent_mfp_interval(start_dato, visible=visible)

    else:
        datoer = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
        dato = datoer[0] if datoer else dt.date.today().isoformat()
        data = hent_mfp_dag(dato, visible=visible)

    print("\nResultat:")
    print(data)