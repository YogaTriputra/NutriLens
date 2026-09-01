import logging
import os
import json
from google import genai
from google.genai import types

from usda import get_food_nutrition
from fatsecret import search_fatsecret_food


def estimate_nutrition_gemini(display_name: str, portion_grams: float) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum diatur di .env.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
Estimasi kandungan nutrisi untuk makanan '{display_name}' dengan berat {portion_grams} gram.

Kembalikan HANYA JSON tanpa teks lain dengan struktur:
{{
  "calories": 250.0,
  "protein": 5.0,
  "carbohydrates": 45.0,
  "fat": 6.0,
  "fiber": 2.0
}}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini fallback gagal menghasilkan estimasi nutrisi.")

    data = json.loads(response.text)

    return {
        "requested_name": display_name,
        "usda_name": "Estimasi AI Gemini",
        "portion_grams": portion_grams,
        "calories": float(data.get("calories", 0.0)),
        "protein": float(data.get("protein", 0.0)),
        "carbohydrates": float(data.get("carbohydrates", 0.0)),
        "fat": float(data.get("fat", 0.0)),
        "fiber": float(data.get("fiber", 0.0)),
    }


async def fetch_nutrition_with_fallback(food_name: str, display_name: str, portion_grams: float) -> dict:
    # 1. Coba FatSecret dulu jika nama makanan lokal Indonesia (display_name tersedia)
    try:
        nutrition = await search_fatsecret_food(display_name, portion_grams)
        if nutrition:
            return nutrition
    except Exception:
        logging.info(f"FatSecret tidak menemukan '{display_name}'")

    # 2. Coba USDA jika bukan hidangan lokal yang unik
    try:
        nutrition = await get_food_nutrition(food_name, portion_grams)
        # Jika USDA mengembalikan kecocokan kata yang buruk/aneh, biarkan ke fallback
        if nutrition:
            return nutrition
    except Exception:
        logging.info(f"USDA tidak menemukan '{food_name}'")

    # 3. Fallback AI Gemini (Estimasi Paling Akurat untuk Makanan Khas)
    logging.info(f"Menggunakan Fallback Gemini AI untuk '{display_name}' ({portion_grams}g)...")
    return estimate_nutrition_gemini(display_name, portion_grams)
