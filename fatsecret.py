import os
import logging
import httpx

FATSECRET_TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
FATSECRET_SEARCH_URL = "https://platform.fatsecret.com/rest/server.api"

_access_token: str | None = None


async def get_fatsecret_token() -> str:
    global _access_token
    if _access_token:
        return _access_token

    client_id = os.getenv("FATSECRET_CLIENT_ID")
    client_secret = os.getenv("FATSECRET_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError("FATSECRET_CLIENT_ID atau FATSECRET_CLIENT_SECRET belum diatur di .env.")

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            FATSECRET_TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": "basic"},
            auth=(client_id, client_secret),
        )
        response.raise_for_status()
        data = response.json()
        _access_token = data.get("access_token")
        if not _access_token:
            raise RuntimeError("Gagal memperoleh access token FatSecret.")
        return _access_token


async def search_fatsecret_food(food_name: str, portion_grams: float) -> dict | None:
    try:
        token = await get_fatsecret_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "method": "foods.search",
            "search_expression": food_name,
            "format": "json",
            "max_results": 5,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(FATSECRET_SEARCH_URL, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()

        foods_container = data.get("foods", {})
        food_list = foods_container.get("food", [])

        if isinstance(food_list, dict):
            food_list = [food_list]

        if not food_list:
            return None

        first_food = food_list[0]
        description = first_food.get("food_description", "")
        # Format deskripsi FatSecret: "Per 100g - Calories: 150kcal | Fat: 5.00g | Carbs: 20.00g | Protein: 3.00g"

        calories = 0.0
        fat = 0.0
        carbs = 0.0
        protein = 0.0

        for part in description.split("|"):
            part = part.strip()
            if "Calories:" in part:
                calories = float(part.replace("Calories:", "").replace("kcal", "").strip())
            elif "Fat:" in part:
                fat = float(part.replace("Fat:", "").replace("g", "").strip())
            elif "Carbs:" in part:
                carbs = float(part.replace("Carbs:", "").replace("g", "").strip())
            elif "Protein:" in part:
                protein = float(part.replace("Protein:", "").replace("g", "").strip())

        multiplier = portion_grams / 100.0

        return {
            "requested_name": food_name,
            "usda_name": f"FatSecret: {first_food.get('food_name')}",
            "portion_grams": portion_grams,
            "calories": calories * multiplier,
            "protein": protein * multiplier,
            "carbohydrates": carbs * multiplier,
            "fat": fat * multiplier,
            "fiber": 0.0,
        }
    except Exception:
        logging.exception(f"Pencarian FatSecret gagal untuk {food_name}")
        return None
