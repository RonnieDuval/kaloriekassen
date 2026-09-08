"""Transform MyFitnessPal diary data into database-ready food entries."""
import hashlib
from typing import Any


def normalize_meal_type(source_meal_name: str) -> str:
    """Return a small, analysis-friendly meal category."""
    normalized = source_meal_name.strip().casefold()
    if normalized in {"breakfast", "morgenmad"}:
        return "breakfast"
    if normalized in {"lunch", "frokost"}:
        return "lunch"
    if normalized in {"dinner", "aftensmad"}:
        return "dinner"
    if "snack" in normalized or normalized == "mellemmåltid":
        return "snack"
    return "other"


def meals_to_nutrition_entries(date: str, meals_detail: dict[str, list]) -> list[dict[str, Any]]:
    """Flatten a MyFitnessPal diary day to one row per recorded food."""
    if not isinstance(meals_detail, dict):
        return []

    entries: list[dict[str, Any]] = []
    for source_meal_name, foods in meals_detail.items():
        if not isinstance(foods, list):
            continue
        for position, food in enumerate(foods):
            if not isinstance(food, dict):
                continue
            source_key = f"{date}\x1f{source_meal_name}\x1f{position}"
            entries.append(
                {
                    "entry_id": hashlib.sha256(source_key.encode()).hexdigest()[:32],
                    "date": date,
                    "meal_type": normalize_meal_type(source_meal_name),
                    "source_meal_name": source_meal_name,
                    "position": position,
                    "food_name": str(food.get("name", "")),
                    "consumed_at": None,
                    "time_is_estimated": False,
                    "calories": float(food.get("calories", 0) or 0),
                    "protein_g": float(food.get("protein", 0) or 0),
                    "carbs_g": float(food.get("carbohydrates", 0) or 0),
                    "fat_g": float(food.get("fat", 0) or 0),
                    "sodium_mg": float(food.get("sodium", 0) or 0),
                    "sugar_g": float(food.get("sugar", 0) or 0),
                }
            )
    return entries
