import asyncio
import json
import logging
import os
from pathlib import Path

from database import save_meal
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
from usda import get_food_nutrition

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

        telegram_id = update.effective_user.id

        try:
            for item in pending_meal:
                await asyncio.to_thread(save_meal, telegram_id, item)

            await query.message.reply_text(
                "✅ Meal berhasil disimpan ke database!"
            )
            context.user_data.pop("pending_meal", None)
        except Exception:
            logging.exception("Gagal menyimpan meal ke database")
            await query.message.reply_text(
                "❌ Gagal menyimpan meal. Silakan periksa koneksi database."
            )

    elif query.data == "edit_meal":
        context.user_data["awaiting_portion_edit"] = True

        food_lines = [
            f"{index}. {item['display_name']} — "
            f"{item['portion_grams']:.0f} g"
            for index, item in enumerate(pending_meal, start=1)
        ]

        await query.message.reply_text(
            "Pilih makanan dan masukkan porsi baru dengan format:\n"
            "nomor gram\n\n"
            + "\n".join(food_lines)
            + "\n\nContoh: 1 250"
        )


async def edit_meal_portion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message or not update.message.text:
        return

    if not context.user_data.get("awaiting_portion_edit"):
        return

    pending_meal = context.user_data.get("pending_meal")

    if not pending_meal:
        context.user_data.pop("awaiting_portion_edit", None)
        await update.message.reply_text(
            "Data meal sementara tidak ditemukan. Silakan kirim foto kembali."
        )
        return

    parts = update.message.text.split()

    if len(parts) != 2:
        await update.message.reply_text(
            "Format belum benar. Gunakan: nomor gram\nContoh: 1 250"
        )
        return

    try:
        food_index = int(parts[0]) - 1
        portion_grams = float(parts[1])
    except ValueError:
        await update.message.reply_text(
            "Nomor dan porsi harus berupa angka. Contoh: 1 250"
        )
        return

    if food_index < 0 or food_index >= len(pending_meal):
        await update.message.reply_text("Nomor makanan tidak tersedia.")
        return

    if portion_grams <= 0 or portion_grams > 5000:
        await update.message.reply_text(
            "Porsi harus lebih dari 0 dan maksimal 5000 gram."
        )
        return

    old_item = pending_meal[food_index]

    try:
        nutrition = await get_food_nutrition(
            old_item["requested_name"],
            portion_grams,
        )
    except Exception:
        logging.exception("Perhitungan ulang nutrisi gagal")
        await update.message.reply_text(
            "Perhitungan ulang gagal. Silakan coba kembali."
        )
        return

    nutrition["display_name"] = old_item["display_name"]
    nutrition["confidence"] = old_item["confidence"]
    pending_meal[food_index] = nutrition

    context.user_data["pending_meal"] = pending_meal
    context.user_data.pop("awaiting_portion_edit", None)

    total_calories = sum(item["calories"] for item in pending_meal)
    total_protein = sum(item["protein"] for item in pending_meal)
    total_carbohydrates = sum(
        item["carbohydrates"] for item in pending_meal
    )
    total_fat = sum(item["fat"] for item in pending_meal)
    total_fiber = sum(item["fiber"] for item in pending_meal)

    food_lines = [
        f"- {item['display_name']} — {item['portion_grams']:.0f} g\n"
        f"  Referensi USDA: {item['usda_name']}"
        for item in pending_meal
    ]

    message = (
        "HASIL SETELAH EDIT PORSI\n\n"
        + "\n".join(food_lines)
        + "\n\nESTIMASI NUTRISI\n"
        + f"Kalori: {total_calories:.0f} kcal\n"
        + f"Protein: {total_protein:.1f} g\n"
        + f"Karbohidrat: {total_carbohydrates:.1f} g\n"
        + f"Lemak: {total_fat:.1f} g\n"
        + f"Serat: {total_fiber:.1f} g\n\n"
        + "Hasil porsi dan nutrisi merupakan estimasi."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Add Meal", callback_data="add_meal"),
                InlineKeyboardButton("Edit", callback_data="edit_meal"),
            ]
        ]
    )

    await update.message.reply_text(message, reply_markup=keyboard)


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
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, edit_meal_portion)
    )

    logging.info("NutriLens bot sedang berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()