import os

import httpx

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


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
        "pageSize": 5,
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

    food = foods[0]
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