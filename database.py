import os
import logging
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL belum diatur di file .env.")
    return psycopg.connect(DATABASE_URL)

def ensure_user_exists(telegram_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id) DO NOTHING;
                """,
                (telegram_id,),
            )
        conn.commit()

def save_meal(telegram_id: int, meal_item: dict) -> None:
    ensure_user_exists(telegram_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meals (
                    telegram_id,
                    food_name,
                    usda_name,
                    portion_grams,
                    calories,
                    protein,
                    carbohydrates,
                    fat,
                    fiber
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    telegram_id,
                    meal_item["display_name"],
                    meal_item.get("usda_name", ""),
                    meal_item["portion_grams"],
                    meal_item["calories"],
                    meal_item["protein"],
                    meal_item["carbohydrates"],
                    meal_item["fat"],
                    meal_item["fiber"],
                ),
            )
        conn.commit()


def get_todays_meals(telegram_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    food_name, 
                    portion_grams, 
                    calories, 
                    protein, 
                    carbohydrates, 
                    fat, 
                    fiber, 
                    created_at
                FROM meals
                WHERE telegram_id = %s 
                  AND created_at >= CURRENT_DATE
                ORDER BY created_at ASC;
                """,
                (telegram_id,),
            )
            rows = cur.fetchall()

            meals = []
            for row in rows:
                meals.append({
                    "food_name": row[0],
                    "portion_grams": float(row[1]),
                    "calories": float(row[2]),
                    "protein": float(row[3]),
                    "carbohydrates": float(row[4]),
                    "fat": float(row[5]),
                    "fiber": float(row[6]),
                    "created_at": row[7],
                })
            return meals
