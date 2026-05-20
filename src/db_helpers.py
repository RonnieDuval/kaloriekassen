"""Database helper utilities for aggregating and transforming data."""
from typing import Dict, Any


def aggregate_meals_to_totals(meals_detail: Dict[str, list]) -> Dict[str, Any]:
    """
    Aggregate meals_detail JSONB structure to daily totals.
    
    Input format:
    {
        "Breakfast": [
            {"name": "...", "calories": X, "protein": Y, "carbs": Z, "fat": W, "sodium": S, "sugar": G},
            ...
        ],
        "Lunch": [...],
        "Dinner": [...],
        "Snacks": [...]
    }
    
    Returns dict with aggregated totals:
    {
        "calories_in": int,
        "protein": float,
        "carbs": float,
        "fat": float,
        "sodium": int,
        "sugar": float
    }
    """
    if not meals_detail or not isinstance(meals_detail, dict):
        return {
            "calories_in": 0,
            "protein": 0.0,
            "carbs": 0.0,
            "fat": 0.0,
            "sodium": 0,
            "sugar": 0.0,
        }

    totals = {
        "calories_in": 0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "sodium": 0,
        "sugar": 0.0,
    }

    # Iterate through all meal types
    for meal_type, foods in meals_detail.items():
        if not isinstance(foods, list):
            continue

        # Sum metrics from each food in the meal
        for food in foods:
            if not isinstance(food, dict):
                continue

            totals["calories_in"] += int(food.get("calories", 0) or 0)
            totals["protein"] += float(food.get("protein", 0) or 0)
            totals["carbs"] += float(food.get("carbohydrates", 0) or 0)  # Note: key is "carbohydrates"
            totals["fat"] += float(food.get("fat", 0) or 0)
            totals["sodium"] += int(food.get("sodium", 0) or 0)
            totals["sugar"] += float(food.get("sugar", 0) or 0)

    return totals
