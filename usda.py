import os
import re

import httpx

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

def normalize_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def select_best_food(
    foods: list[dict],
    food_name: str,
) -> dict:
    query_words = normalize_words(food_name)

    if not query_words:
        return foods[0]

    def calculate_score(food: dict) -> float:
        description = food.get("description", "")
        description_words = normalize_words(description)

        matching_words = query_words & description_words
        missing_words = query_words - description_words

        score = len(matching_words) * 3
        score -= len(missing_words) * 2

        if food_name.lower() in description.lower():
            score += 5

        return score

    return max(foods, key=calculate_score)

def find_nutrient(
    nutrients: list[dict],
    nutrient_name: str,
    unit_name: str | None = None,
) -> float:
    for nutrient in nutrients:
        name = nutrient.get("nutrientName", "").lower()
        unit = nutrient.get("unitName", "").upper()

        if name == nutrient_name.lower():
            if unit_name is None or unit == unit_name.upper():
                return float(nutrient.get("value", 0))

    return 0.0


async def get_food_nutrition(
    food_name: str,
    portion_grams: float,
) -> dict:
    api_key = os.getenv("USDA_API_KEY")

    if not api_key:
        raise RuntimeError("USDA_API_KEY belum diatur di file .env.")

    parameters = {
        "api_key": api_key,
        "query": food_name,
        "pageSize": 20,
        "dataType": ["Foundation", "SR Legacy"],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            USDA_SEARCH_URL,
            params=parameters,
        )
        response.raise_for_status()

    foods = response.json().get("foods", [])

    if not foods:
        raise ValueError(
            f"Data nutrisi untuk '{food_name}' tidak ditemukan."
        )

    food = select_best_food(foods, food_name)
    nutrients = food.get("foodNutrients", [])
    multiplier = portion_grams / 100

    calories = find_nutrient(
        nutrients,
        "Energy",
        "KCAL",
    )
    protein = find_nutrient(
        nutrients,
        "Protein",
    )
    carbohydrates = find_nutrient(
        nutrients,
        "Carbohydrate, by difference",
    )
    fat = find_nutrient(
        nutrients,
        "Total lipid (fat)",
    )
    fiber = find_nutrient(
        nutrients,
        "Fiber, total dietary",
    )

    return {
        "requested_name": food_name,
        "usda_name": food.get("description", food_name),
        "portion_grams": portion_grams,
        "calories": calories * multiplier,
        "protein": protein * multiplier,
        "carbohydrates": carbohydrates * multiplier,
        "fat": fat * multiplier,
        "fiber": fiber * multiplier,
    }