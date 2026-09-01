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

def calculate_targets(
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal: str,
) -> dict:
    if sex.lower() in ["male", "pria", "laki-laki"]:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    tdee = bmr * activity_multipliers.get(activity_level.lower(), 1.2)

    if goal.lower() == "lose":
        target_calories = tdee - 500
    elif goal.lower() == "gain":
        target_calories = tdee + 300
    else:
        target_calories = tdee

    target_protein = (target_calories * 0.30) / 4
    target_carbs = (target_calories * 0.45) / 4
    target_fat = (target_calories * 0.25) / 9
    target_fiber = 30.0

    return {
        "calories": round(target_calories),
        "protein": round(target_protein, 1),
        "carbs": round(target_carbs, 1),
        "fat": round(target_fat, 1),
        "fiber": target_fiber,
    }


def save_user_profile(
    telegram_id: int,
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal: str,
) -> dict:
    ensure_user_exists(telegram_id)
    targets = calculate_targets(age, sex, height_cm, weight_kg, activity_level, goal)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users SET
                    age = %s,
                    sex = %s,
                    height_cm = %s,
                    weight_kg = %s,
                    activity_level = %s,
                    goal = %s,
                    target_calories = %s,
                    target_protein = %s,
                    target_carbs = %s,
                    target_fat = %s,
                    target_fiber = %s
                WHERE telegram_id = %s;
                """,
                (
                    age,
                    sex,
                    height_cm,
                    weight_kg,
                    activity_level,
                    goal,
                    targets["calories"],
                    targets["protein"],
                    targets["carbs"],
                    targets["fat"],
                    targets["fiber"],
                    telegram_id,
                ),
            )
        conn.commit()

    return targets


def get_user_profile(telegram_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    age, sex, height_cm, weight_kg, activity_level, goal,
                    target_calories, target_protein, target_carbs, target_fat, target_fiber
                FROM users
                WHERE telegram_id = %s;
                """,
                (telegram_id,),
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                return None

            return {
                "age": row[0],
                "sex": row[1],
                "height_cm": float(row[2]),
                "weight_kg": float(row[3]),
                "activity_level": row[4],
                "goal": row[5],
                "target_calories": float(row[6]),
                "target_protein": float(row[7]),
                "target_carbs": float(row[8]),
                "target_fat": float(row[9]),
                "target_fiber": float(row[10]),
            }

