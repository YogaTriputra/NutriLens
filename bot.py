import asyncio
import logging
import os
from pathlib import Path
import json


from usda import get_food_nutrition
from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

PHOTO_DIR = Path("downloads")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Halo! Selamat datang di NutriLens.\n"
            "Silakan kirim foto makanan untuk dianalisis."
        )


def analyze_food(photo_path: Path) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum diatur di file .env.")

    client = genai.Client(api_key=api_key)
    image_bytes = photo_path.read_bytes()

    prompt = """
Analisis foto makanan ini.

Identifikasi setiap makanan atau minuman yang terlihat dan perkirakan
berat porsinya dalam gram.

Untuk makanan campuran, gunakan nama hidangan yang paling sesuai.
Gunakan nama makanan dalam bahasa Inggris pada food_name agar dapat
dicari melalui USDA FoodData Central.

Jangan menghitung kalori atau nutrisi.
Jangan masukkan hiasan yang tidak dimakan.
Semua berat merupakan estimasi dari foto.

Kembalikan hanya JSON dengan struktur berikut:
{
    "foods": [
    {
    "food_name": "cooked white rice",
    "display_name": "Nasi putih",
    "portion_grams": 200,
    "confidence": "high"
    }
]
}

confidence hanya boleh berisi "high", "medium", atau "low".
portion_grams harus berupa angka.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini tidak menghasilkan jawaban.")

    data = json.loads(response.text)
    foods = data.get("foods", [])

    if not foods:
        raise ValueError("Tidak ada makanan yang teridentifikasi.")

    return foods


async def receive_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message or not update.message.photo:
        return

    await update.message.reply_text(
        "Foto berhasil diterima. Sedang menganalisis makanan..."
    )

    PHOTO_DIR.mkdir(exist_ok=True)

    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    photo_path = PHOTO_DIR / f"{photo.file_unique_id}.jpg"

    await photo_file.download_to_drive(custom_path=photo_path)

    try:
        foods = await asyncio.to_thread(analyze_food, photo_path)

        nutrition_results = []

        for food in foods:
            food_name = food["food_name"]
            portion_grams = float(food["portion_grams"])

            nutrition = await get_food_nutrition(
                food_name,
                portion_grams,
            )

            nutrition["display_name"] = food.get(
                "display_name",
                food_name,
            )
            nutrition["confidence"] = food.get(
                "confidence",
                "low",
            )

            nutrition_results.append(nutrition)

        total_calories = sum(
            item["calories"] for item in nutrition_results
        )
        total_protein = sum(
            item["protein"] for item in nutrition_results
        )
        total_carbohydrates = sum(
            item["carbohydrates"] for item in nutrition_results
        )
        total_fat = sum(
            item["fat"] for item in nutrition_results
        )
        total_fiber = sum(
            item["fiber"] for item in nutrition_results
        )

        food_lines = []

        for item in nutrition_results:
            food_lines.append(
                f"- {item['display_name']} — "
                f"{item['portion_grams']:.0f} g\n"
                f"  Referensi USDA: {item['usda_name']}"
            )

        message = (
            "HASIL ANALISIS MAKANAN\n\n"
            + "\n".join(food_lines)
            + "\n\nESTIMASI NUTRISI\n"
            + f"Kalori: {total_calories:.0f} kcal\n"
            + f"Protein: {total_protein:.1f} g\n"
            + f"Karbohidrat: {total_carbohydrates:.1f} g\n"
            + f"Lemak: {total_fat:.1f} g\n"
            + f"Serat: {total_fiber:.1f} g\n\n"
            + "Hasil identifikasi, porsi, dan nutrisi merupakan "
            + "estimasi. Metode memasak dapat memengaruhi hasil."
        )

        context.user_data["pending_meal"] = nutrition_results

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Add Meal",
                        callback_data="add_meal",
                    ),
                    InlineKeyboardButton(
                        "Edit",
                        callback_data="edit_meal",
                    ),
                ]
            ]
        )

        await update.message.reply_text(
            message,
            reply_markup=keyboard,
        )

    except Exception:
        logging.exception("Analisis makanan atau nutrisi gagal")
        await update.message.reply_text(
            "Maaf, analisis belum berhasil. "
            "Silakan periksa terminal atau coba foto lain."
        )


async def handle_meal_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query

    if not query:
        return

    await query.answer()

    pending_meal = context.user_data.get("pending_meal")

    if not pending_meal:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Data meal sementara tidak ditemukan. "
            "Silakan kirim foto kembali."
        )
        return

    if query.data == "add_meal":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Meal berhasil dikonfirmasi.\n"
            "Meal belum disimpan karena database belum tersedia."
        )
        context.user_data.pop("pending_meal", None)

    elif query.data == "edit_meal":
        await query.message.reply_text(
            "Fitur edit akan dibuat pada langkah berikutnya.\n\n"
            "Nantinya Anda dapat mengoreksi nama makanan dan "
            "porsi sebelum meal disimpan."
        )


def main() -> None:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diatur di file .env.")

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY belum diatur di file .env.")

    application = Application.builder().token(telegram_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.PHOTO, receive_photo)
    )
    application.add_handler(
        CallbackQueryHandler(
            handle_meal_action,
            pattern="^(add_meal|edit_meal)$",
        )
    )

    logging.info("NutriLens bot sedang berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()