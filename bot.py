import asyncio
import json
import logging
import os
from pathlib import Path

from ai_assistant import generate_ai_response
from database import (
    get_todays_meals,
    get_user_profile,
    save_meal,
    save_user_profile,
)
from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from nutrition_service import fetch_nutrition_with_fallback

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
            display_name = food.get("display_name", food_name)
            portion_grams = float(food["portion_grams"])

            nutrition = await fetch_nutrition_with_fallback(
                food_name,
                display_name,
                portion_grams,
            )

            nutrition["display_name"] = display_name
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
                f"• *{item['display_name']}* (~{item['portion_grams']:.0f}g)\n"
                f"  └ _USDA: {item['usda_name']}_"
            )

        message = (
            "🍽️ *HASIL ANALISIS MAKANAN*\n"
            "───────────────\n"
            + "\n".join(food_lines)
            + "\n\n📊 *ESTIMASI NUTRISI*\n"
            "───────────────\n"
            + f"🔥 *Kalori*: ~{total_calories:.0f} kcal\n"
            + f"🥩 *Protein*: ~{total_protein:.1f} g\n"
            + f"🌾 *Karbohidrat*: ~{total_carbohydrates:.1f} g\n"
            + f"🥑 *Lemak*: ~{total_fat:.1f} g\n"
            + f"🥦 *Serat*: ~{total_fiber:.1f} g\n\n"
            + "💡 _Hasil identifikasi, porsi, dan nutrisi merupakan estimasi. "
            + "Metode memasak dapat memengaruhi hasil._"
        )

        context.user_data["pending_meal"] = nutrition_results

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Add Meal",
                        callback_data="add_meal",
                    ),
                    InlineKeyboardButton(
                        "✏️ Edit Porsi",
                        callback_data="edit_meal",
                    ),
                ]
            ]
        )

        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
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
        nutrition = await fetch_nutrition_with_fallback(
            old_item["requested_name"],
            old_item["display_name"],
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
        f"• *{item['display_name']}* (~{item['portion_grams']:.0f}g)\n"
        f"  └ _USDA: {item['usda_name']}_"
        for item in pending_meal
    ]

    message = (
        "✏️ *HASIL SETELAH EDIT PORSI*\n"
        "───────────────\n"
        + "\n".join(food_lines)
        + "\n\n📊 *ESTIMASI NUTRISI*\n"
        "───────────────\n"
        + f"🔥 *Kalori*: ~{total_calories:.0f} kcal\n"
        + f"🥩 *Protein*: ~{total_protein:.1f} g\n"
        + f"🌾 *Karbohidrat*: ~{total_carbohydrates:.1f} g\n"
        + f"🥑 *Lemak*: ~{total_fat:.1f} g\n"
        + f"🥦 *Serat*: ~{total_fiber:.1f} g\n\n"
        + "💡 _Hasil porsi dan nutrisi merupakan estimasi._"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Add Meal", callback_data="add_meal"),
                InlineKeyboardButton("✏️ Edit Porsi", callback_data="edit_meal"),
            ]
        ]
    )

AGE, SEX, HEIGHT, WEIGHT, ACTIVITY, GOAL = range(6)


async def setprofile_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 *PENGATURAN PROFIL FUKSI & TARGET NUTRISI*\n"
        "───────────────\n"
        "Berapa umur Anda saat ini? (Contoh: `25`)",
        parse_mode="Markdown",
    )
    return AGE


async def setprofile_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return AGE

    try:
        age = int(update.message.text)
        if age <= 0 or age > 120:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Masukkan umur yang valid dalam bentuk angka. Contoh: `25`", parse_mode="Markdown")
        return AGE

    context.user_data["profile_age"] = age

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Pria", callback_data="sex_male"),
                InlineKeyboardButton("Wanita", callback_data="sex_female"),
            ]
        ]
    )
    await update.message.reply_text("Pilih jenis kelamin Anda:", reply_markup=keyboard)
    return SEX


async def setprofile_sex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return SEX

    await query.answer()
    sex = "male" if query.data == "sex_male" else "female"
    context.user_data["profile_sex"] = sex

    await query.message.reply_text("Berapa tinggi badan Anda dalam centimeter (cm)? (Contoh: `170`)", parse_mode="Markdown")
    return HEIGHT


async def setprofile_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return HEIGHT

    try:
        height = float(update.message.text)
        if height <= 50 or height > 250:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Masukkan tinggi badan yang valid dalam cm. Contoh: `170`", parse_mode="Markdown")
        return HEIGHT

    context.user_data["profile_height"] = height
    await update.message.reply_text("Berapa berat badan Anda saat ini dalam kilogram (kg)? (Contoh: `65.5`)", parse_mode="Markdown")
    return WEIGHT


async def setprofile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WEIGHT

    try:
        weight = float(update.message.text)
        if weight <= 20 or weight > 300:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Masukkan berat badan yang valid dalam kg. Contoh: `65.5`", parse_mode="Markdown")
        return WEIGHT

    context.user_data["profile_weight"] = weight

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Jarang Olahraga", callback_data="act_sedentary")],
            [InlineKeyboardButton("Olahraga Ringan (1-3 hari/mgg)", callback_data="act_light")],
            [InlineKeyboardButton("Olahraga Sedang (3-5 hari/mgg)", callback_data="act_moderate")],
            [InlineKeyboardButton("Olahraga Berat (6-7 hari/mgg)", callback_data="act_active")],
        ]
    )
    await update.message.reply_text("Pilih tingkat aktivitas harian Anda:", reply_markup=keyboard)
    return ACTIVITY


async def setprofile_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ACTIVITY

    await query.answer()
    act = query.data.replace("act_", "")
    context.user_data["profile_activity"] = act

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📉 Turun Berat Badan (Lose Weight)", callback_data="goal_lose")],
            [InlineKeyboardButton("⚖️ Menjaga Berat Badan (Maintain)", callback_data="goal_maintain")],
            [InlineKeyboardButton("📈 Naik Berat Badan (Gain Weight)", callback_data="goal_gain")],
        ]
    )
    await query.message.reply_text("Pilih tujuan (goal) kesehatan Anda:", reply_markup=keyboard)
    return GOAL


async def setprofile_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return GOAL

    await query.answer()
    goal = query.data.replace("goal_", "")
    telegram_id = update.effective_user.id

    try:
        targets = await asyncio.to_thread(
            save_user_profile,
            telegram_id,
            context.user_data["profile_age"],
            context.user_data["profile_sex"],
            context.user_data["profile_height"],
            context.user_data["profile_weight"],
            context.user_data["profile_activity"],
            goal,
        )

        message = (
            "✅ *PROFIL BERHASIL DISIMPAN!*\n"
            "───────────────\n"
            + f"🔥 *Target Kalori Harian*: {targets['calories']} kcal\n"
            + f"🥩 *Target Protein*: {targets['protein']} g\n"
            + f"🌾 *Target Karbo*: {targets['carbs']} g\n"
            + f"🥑 *Target Lemak*: {targets['fat']} g\n"
            + f"🥦 *Target Serat*: {targets['fiber']} g\n\n"
            + "Ketik `/today` untuk melihat akumulasi nutrisi harian dibanding target Anda!"
        )
        await query.message.reply_text(message, parse_mode="Markdown")
    except Exception:
        logging.exception("Gagal menyimpan profil")
        await query.message.reply_text("❌ Terjadi kesalahan saat menyimpan profil ke database.")

    return ConversationHandler.END


async def setprofile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Pengaturan profil dibatalkan.")
    return ConversationHandler.END


async def profile_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message:
        return

    telegram_id = update.effective_user.id
    profile = await asyncio.to_thread(get_user_profile, telegram_id)

    if not profile:
        await update.message.reply_text(
            "👤 *PROFIL PENGGUNA*\n"
            "───────────────\n"
            "Profil Anda belum dibuat.\n\n"
            "Ketik `/setprofile` untuk membuat profil fisik dan menghitung target kalori harian!",
            parse_mode="Markdown",
        )
        return

    goal_labels = {"lose": "Turun Berat Badan", "maintain": "Menjaga Berat Badan", "gain": "Naik Berat Badan"}
    activity_labels = {
        "sedentary": "Jarang berolahraga",
        "light": "Olahraga ringan (1-3 hari/minggu)",
        "moderate": "Olahraga sedang (3-5 hari/minggu)",
        "active": "Olahraga berat (6-7 hari/minggu)",
        "very_active": "Fisik sangat aktif / Atlet",
    }

    message = (
        "👤 *PROFIL PENGGUNA*\n"
        "───────────────\n"
        + f"• *Umur*: {profile['age']} tahun\n"
        + f"• *Jenis Kelamin*: {profile['sex'].capitalize()}\n"
        + f"• *Tinggi Badan*: {profile['height_cm']:.0f} cm\n"
        + f"• *Berat Badan*: {profile['weight_kg']:.1f} kg\n"
        + f"• *Tingkat Aktivitas*: {activity_labels.get(profile['activity_level'], profile['activity_level'])}\n"
        + f"• *Target*: {goal_labels.get(profile['goal'], profile['goal'])}\n\n"
        + "🎯 *TARGET NUTRISI HARIAN*\n"
        "───────────────\n"
        + f"🔥 *Kalori*: {profile['target_calories']:.0f} kcal\n"
        + f"🥩 *Protein*: {profile['target_protein']:.1f} g\n"
        + f"🌾 *Karbohidrat*: {profile['target_carbs']:.1f} g\n"
        + f"🥑 *Lemak*: {profile['target_fat']:.1f} g\n"
        + f"🥦 *Serat*: {profile['target_fiber']:.1f} g\n\n"
        + "_Ketik `/setprofile` jika ingin memperbarui profil._"
    )

    await update.message.reply_text(message, parse_mode="Markdown")


async def today_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message:
        return

    telegram_id = update.effective_user.id

    try:
        meals = await asyncio.to_thread(get_todays_meals, telegram_id)
        profile = await asyncio.to_thread(get_user_profile, telegram_id)
    except Exception:
        logging.exception("Gagal mengambil data harian dari database")
        await update.message.reply_text(
            "❌ Gagal mengambil data harian dari database."
        )
        return

    total_calories = sum(m["calories"] for m in meals)
    total_protein = sum(m["protein"] for m in meals)
    total_carbohydrates = sum(m["carbohydrates"] for m in meals)
    total_fat = sum(m["fat"] for m in meals)
    total_fiber = sum(m["fiber"] for m in meals)

    if profile:
        target_cal_str = f" / {profile['target_calories']:.0f}"
        target_prot_str = f" / {profile['target_protein']:.1f}"
        target_carbs_str = f" / {profile['target_carbs']:.1f}"
        target_fat_str = f" / {profile['target_fat']:.1f}"
        target_fiber_str = f" / {profile['target_fiber']:.1f}"
    else:
        target_cal_str = ""
        target_prot_str = ""
        target_carbs_str = ""
        target_fat_str = ""
        target_fiber_str = ""

    if not meals:
        target_info = (
            f"\n🎯 Target Kalori: {profile['target_calories']:.0f} kcal\n"
            if profile
            else "\nGunakan `/profile` untuk mengatur target kalori Anda!\n"
        )
        await update.message.reply_text(
            "📋 *NUTRISI HARI INI*\n"
            "───────────────\n"
            "Belum ada makanan yang dicatat hari ini.\n"
            + target_info +
            "Kirim foto makanan untuk mulai mencatat!",
            parse_mode="Markdown",
        )
        return

    food_list = []
    for item in meals:
        food_list.append(
            f"• *{item['food_name']}* (~{item['portion_grams']:.0f}g) — "
            f"~{item['calories']:.0f} kcal"
        )

    message = (
        "📊 *TOTAL NUTRISI HARI INI*\n"
        "───────────────\n"
        + f"🔥 *Kalori*: ~{total_calories:.0f}{target_cal_str} kcal\n"
        + f"🥩 *Protein*: ~{total_protein:.1f}{target_prot_str} g\n"
        + f"🌾 *Karbohidrat*: ~{total_carbohydrates:.1f}{target_carbs_str} g\n"
        + f"🥑 *Lemak*: ~{total_fat:.1f}{target_fat_str} g\n"
        + f"🥦 *Serat*: ~{total_fiber:.1f}{target_fiber_str} g\n\n"
        + "🍽️ *DAFTAR MAKANAN HARI INI*\n"
        "───────────────\n"
        + "\n".join(food_list)
    )

    await update.message.reply_text(message, parse_mode="Markdown")

async def handle_ai_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message or not update.message.text:
        return

    if context.user_data.get("awaiting_portion_edit"):
        await edit_meal_portion(update, context)
        return

    telegram_id = update.effective_user.id
    user_query = update.message.text

    await update.message.reply_text("🤔 *Sedang memikirkan jawaban...*", parse_mode="Markdown")

    try:
        reply = await asyncio.to_thread(generate_ai_response, telegram_id, user_query)
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception:
        logging.exception("Gagal memproses chat AI")
        await update.message.reply_text("❌ Maaf, terjadi kesalahan saat menghubungi AI Assistant.")


def main() -> None:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diatur di file .env.")

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY belum diatur di file .env.")

    application = Application.builder().token(telegram_token).build()
    
    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("setprofile", setprofile_start)],
        states={
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setprofile_age)],
            SEX: [CallbackQueryHandler(setprofile_sex, pattern="^sex_")],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, setprofile_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, setprofile_weight)],
            ACTIVITY: [CallbackQueryHandler(setprofile_activity, pattern="^act_")],
            GOAL: [CallbackQueryHandler(setprofile_goal, pattern="^goal_")],
        },
        fallbacks=[CommandHandler("cancel", setprofile_cancel)],
    )

    application.add_handler(profile_conv)
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("today", today_command))
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
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_chat)
    )

    logging.info("NutriLens bot sedang berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()