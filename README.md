# NutriLens

NutriLens adalah chatbot Telegram berbasis AI untuk membantu pengguna mencatat dan memantau asupan kalori serta nutrisi harian melalui foto makanan.

Pengguna dapat mengirim foto makanan ke bot. Google Gemini Vision mengidentifikasi makanan dan memperkirakan porsinya, kemudian aplikasi mencari data nutrisi melalui **USDA FoodData Central**, **FatSecret Platform API** (makanan Indonesia), atau **Fallback Gemini AI**. Bot menampilkan estimasi kalori, protein, karbohidrat, lemak, dan serat secara interaktif.

> Hasil identifikasi makanan, ukuran porsi, dan nilai nutrisi merupakan estimasi. Metode memasak, bahan, dan ukuran sebenarnya dapat memengaruhi hasil. NutriLens bukan alat diagnosis atau pengganti saran medis.

---

## 🌟 Fitur Utama

1. **AI Vision Food Analysis**: Mengidentifikasi foto makanan dan memperkirakan porsi dalam gram.
2. **Multi-Source Nutrition Lookup**:
   - **USDA FoodData Central**: Untuk bahan makanan umum global.
   - **FatSecret API**: Untuk makanan khas Indonesia (seperti Rendang, Klepon, dll).
   - **Gemini AI Fallback**: Estimasi AI otomatis jika makanan tidak ada di database.
3. **Konfirmasi & Edit Porsi**: Tombol **Add Meal** dan **Edit Porsi** sebelum data disimpan ke database.
4. **PostgreSQL Database (Supabase)**: Menyimpan data pengguna dan riwayat asupan makanan secara aman.
5. **Daily Nutrition Tracker (`/today`)**: Memantau total kalori dan makronutrisi harian disandingkan dengan target personal.
6. **Profil & Target Kalori (`/profile` & `/setprofile`)**: Perhitungan TDEE dan target makronutrisi berdasarkan rumus Mifflin-St Jeor.
7. **AI Nutrition Assistant**: Tanya jawab bebas seputar kondisi nutrisi harian dalam bahasa natural.
8. **Weekly History & Statistics (`/history` / `/week`)**: Rekapitulasi kalori dan makronutrisi 7 hari terakhir beserta rata-rata harian.

---

## 📱 Daftar Command Telegram

- `/start` - Menampilkan pesan selamat datang dan petunjuk penggunaan.
- `/setprofile` - Alur interaktif pembuatan/perbaruan profil fisik dan target kalori.
- `/profile` - Menampilkan profil fisik dan target kebutuhan nutrisi harian.
- `/today` - Menampilkan akumulasi nutrisi dan daftar makanan hari ini.
- `/history` / `/week` - Menampilkan riwayat makanan dan rata-rata nutrisi 7 hari terakhir.
- *Kirim Foto Makanan* - Menganalisis makanan dari foto.
- *Kirim Pesan Teks Bebas* - Berdiskusi dengan AI Nutrition Assistant.

---

## 🛠️ Teknologi

- **Python 3.10+**
- **Telegram Bot API** (`python-telegram-bot`)
- **Google Gemini 2.5 Flash** (`google-genai`)
- **USDA FoodData Central API**
- **FatSecret Platform API**
- **PostgreSQL Database** (`psycopg` & Supabase)
- **HTTP Client** (`httpx`)

---

## 📁 Struktur Project

```text
NutriLens/
├── .venv/              # Environment virtual Python (diabaikan oleh Git)
├── downloads/          # Folder penyimpanan foto makanan sementara (diabaikan oleh Git)
├── .env                # Variabel lingkungan rahasia / API Keys (diabaikan oleh Git)
├── .env.example        # Contoh format file konfigurasi environment
├── .gitignore          # Daftar file/folder yang diabaikan Git
├── README.md           # Dokumentasi resmi proyek
├── ai_assistant.py     # Modul AI Assistant untuk percakapan & tanya jawab nutrisi
├── bot.py              # Telegram bot utama, event handler, & daftar command
├── database.py         # Modul koneksi PostgreSQL Supabase (manajemen user, profil, & meals)
├── fatsecret.py        # Modul integrasi FatSecret Platform API (OAuth2 & pencarian makanan lokal)
├── nutrition_service.py# Modul strategi pencarian nutrisi (USDA -> FatSecret -> Gemini Fallback)
├── requirements.txt    # Daftar dependensi modul Python
├── test_usda.py        # Script pengujian koneksi & pencarian USDA secara mandiri
└── usda.py             # Modul integrasi USDA FoodData Central API
```

---

## 🚀 Cara Menjalankan Bot

### 1. Clone Repository
```bash
git clone https://github.com/YogaTriputra/NutriLens.git
cd NutriLens
```

### 2. Buat Virtual Environment & Instal Dependensi
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. Setup Konfigurasi `.env`
Salin file konfigurasi:
```bash
cp .env.example .env
```
Isi file `.env` dengan kredensial API Anda:
```env
TELEGRAM_BOT_TOKEN=token_bot_anda
GEMINI_API_KEY=api_key_gemini_anda
USDA_API_KEY=api_key_usda_anda
DATABASE_URL=postgresql://postgres:password@host:5432/postgres
FATSECRET_CLIENT_ID=client_id_fatsecret_anda
FATSECRET_CLIENT_SECRET=client_secret_fatsecret_anda
```

### 4. Menjalankan Bot
```bash
source .venv/bin/activate
python bot.py
```
