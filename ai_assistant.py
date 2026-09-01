import os
import logging
import asyncio
from google import genai

from database import get_user_profile, get_todays_meals


def generate_ai_response(telegram_id: int, user_query: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum diatur di .env.")

    client = genai.Client(api_key=api_key)

    profile = get_user_profile(telegram_id)
    meals = get_todays_meals(telegram_id)

    total_calories = sum(m["calories"] for m in meals)
    total_protein = sum(m["protein"] for m in meals)
    total_carbs = sum(m["carbohydrates"] for m in meals)
    total_fat = sum(m["fat"] for m in meals)
    total_fiber = sum(m["fiber"] for m in meals)

    meal_names = [f"- {m['food_name']} ({m['portion_grams']:.0f}g, {m['calories']:.0f} kcal)" for m in meals]
    meal_summary = "\n".join(meal_names) if meal_names else "Belum ada makanan yang dicatat hari ini."

    if profile:
        profile_summary = (
            f"Target Kalori: {profile['target_calories']:.0f} kcal\n"
            f"Target Protein: {profile['target_protein']:.1f} g\n"
            f"Target Karbohidrat: {profile['target_carbs']:.1f} g\n"
            f"Target Lemak: {profile['target_fat']:.1f} g\n"
            f"Target Serat: {profile['target_fiber']:.1f} g\n"
            f"Goal: {profile['goal']}\n"
        )
    else:
        profile_summary = "Profil pengguna belum diatur."

    prompt = f"""
Anda adalah NutriLens AI Assistant, asisten nutrisi pribadi yang ramah, informatif, dan membantu.

DATA PENGGUNA HARI INI:
---
PROFIL & TARGET:
{profile_summary}

KONSUMSI NUTRISI HARI INI:
- Kalori: {total_calories:.0f} kcal
- Protein: {total_protein:.1f} g
- Karbohidrat: {total_carbs:.1f} g
- Lemak: {total_fat:.1f} g
- Serat: {total_fiber:.1f} g

DAFTAR MAKANAN HARI INI:
{meal_summary}
---

PERTANYAAN PENGGUNA:
"{user_query}"

PETUNJUK RESPONS:
1. Jawab pertanyaan pengguna berdasarkan data konsumsi dan target harian di atas.
2. Berikan saran yang praktis, suportif, dan mudah dipahami.
3. Jangan memberikan klaim medis atau diagnosis medis.
4. Gunakan Bahasa Indonesia yang ramah dan gunakan emoji secukupnya.
5. Jawab secara ringkas dan padat.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
    )

    if not response.text:
        return "Maaf, AI belum bisa menjawab saat ini. Coba tanyakan lagi nanti."

    return response.text
