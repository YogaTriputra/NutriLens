import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


def get_nutrient(
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


async def search_food(food_name: str, portion_grams: float) -> None:
    api_key = os.getenv("USDA_API_KEY")

    if not api_key:
        raise RuntimeError("USDA_API_KEY belum diatur di file .env.")

    parameters = {
        "api_key": api_key,
        "query": food_name,
        "pageSize": 10,
        "dataType": ["Foundation", "SR Legacy"],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            USDA_SEARCH_URL,
            params=parameters,
        )
        response.raise_for_status()

    data = response.json()
    foods = data.get("foods", [])

    if not foods:
        print("Makanan tidak ditemukan.")
        return

    food = foods[0]
    nutrients = food.get("foodNutrients", [])

    calories = get_nutrient(nutrients, "Energy", "KCAL")
    protein = get_nutrient(nutrients, "Protein")
    carbohydrates = get_nutrient(
        nutrients,
        "Carbohydrate, by difference",
    )
    fat = get_nutrient(nutrients, "Total lipid (fat)")
    fiber = get_nutrient(
        nutrients,
        "Fiber, total dietary",
    )

    portion_multiplier = portion_grams / 100

    print(f"\nMakanan USDA: {food.get('description')}")
    print(f"Porsi: {portion_grams:.0f} gram")
    print("\nEstimasi nutrisi:")
    print(f"Kalori: {calories * portion_multiplier:.1f} kcal")
    print(f"Protein: {protein * portion_multiplier:.1f} g")
    print(
        f"Karbohidrat: "
        f"{carbohydrates * portion_multiplier:.1f} g"
    )
    print(f"Lemak: {fat * portion_multiplier:.1f} g")
    print(f"Serat: {fiber * portion_multiplier:.1f} g")
    print("\nHasil nutrisi dan porsi merupakan estimasi.")


async def main() -> None:
    food_name = input(
        "Masukkan nama makanan dalam bahasa Inggris: "
    )
    portion_grams = float(
        input("Masukkan estimasi porsi dalam gram: ")
    )

    await search_food(food_name, portion_grams)


if __name__ == "__main__":
    asyncio.run(main())