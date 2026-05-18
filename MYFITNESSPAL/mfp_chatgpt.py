import re
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


CHROME_DIR = Path.home() / ".config/google-chrome"
PROFILE_DIR = Path.cwd() / "temp_chrome_profile"


def kopier_profil_hvis_mangler():
    if PROFILE_DIR.exists():
        return

    print("Kopierer Chrome profil første gang...")

    source_default = CHROME_DIR / "Default"
    target_default = PROFILE_DIR / "Default"

    PROFILE_DIR.mkdir(exist_ok=True)

    if source_default.exists():
        shutil.copytree(
            source_default,
            target_default,
            ignore=shutil.ignore_patterns(
                "Cache*",
                "Code Cache",
                "GPUCache",
                "ShaderCache",
            ),
        )
    else:
        shutil.copytree(
            CHROME_DIR,
            PROFILE_DIR,
            ignore=shutil.ignore_patterns(
                "Cache*",
                "Code Cache",
                "GPUCache",
                "ShaderCache",
            ),
            dirs_exist_ok=True,
        )


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
        )

        try:
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)

            if "login" in page.url and visible:
                print("Log ind manuelt i browseren og tryk Enter her bagefter...")
                input()
                page.goto(url, wait_until="networkidle", timeout=30_000)

            page.locator("table.table0").wait_for(state="visible", timeout=15_000)
            page.wait_for_timeout(1_000)

            return {
                "date": dato_streng,
                "meals": parse_food_rows(page, dato_streng)["meals"],
            }

        except Exception as e:
            print(f"[FEJL] Fejl under hentning: {e}")
            return None

        finally:
            context.close()


if __name__ == "__main__":
    visible = "--visible" in sys.argv
    datoer = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    dato = datoer[0] if datoer else "2026-05-13"

    data = hent_mfp_dag(dato, visible=visible)

    print("\nResultat:")
    print(data)