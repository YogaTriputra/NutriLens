# NutriLens

NutriLens adalah chatbot Telegram berbasis AI untuk membantu pengguna mencatat asupan kalori dan nutrisi melalui foto makanan.

Pengguna mengirim foto makanan ke bot. Google Gemini Vision mengidentifikasi makanan dan memperkirakan porsinya, kemudian aplikasi mencari referensi nutrisi melalui USDA FoodData Central. Bot menampilkan estimasi kalori, protein, karbohidrat, lemak, dan serat.

> Hasil identifikasi makanan, ukuran porsi, dan nilai nutrisi merupakan estimasi. Metode memasak, bahan, dan ukuran sebenarnya dapat memengaruhi hasil. NutriLens bukan alat diagnosis atau pengganti saran medis.

## Fitur Saat Ini

- Command Telegram `/start`
- Menerima dan mengunduh foto makanan
- Identifikasi makanan menggunakan Gemini Vision
- Estimasi ukuran porsi dalam gram
- Pencarian data nutrisi melalui USDA FoodData Central
- Estimasi total kalori, protein, karbohidrat, lemak, dan serat

## Rencana Pengembangan

- Koreksi makanan dan ukuran porsi sebelum disimpan
- Tombol **Add Meal** dan **Edit**
- Penyimpanan meal menggunakan PostgreSQL
- Daily nutrition tracker melalui `/today`
- Profil pengguna dan target kalori/makro
- AI nutrition assistant berdasarkan data pengguna
- History dan statistik mingguan

## Teknologi

- Python
- Telegram Bot API
- Google Gemini Vision
- USDA FoodData Central API
- `python-telegram-bot`
- `google-genai`
- `httpx`

## Cara Kerja

1. Pengguna mengirim foto makanan melalui Telegram.
2. Bot mengunduh foto ke penyimpanan sementara.
3. Gemini mengidentifikasi makanan dan memperkirakan berat porsinya.
4. Nama makanan dicari melalui USDA FoodData Central.
5. Nilai nutrisi per 100 gram disesuaikan dengan estimasi porsi.
6. Bot mengirim hasil estimasi nutrisi kepada pengguna.

## Persyaratan

- Python 3.10 atau lebih baru
- Telegram Bot Token dari BotFather
- Google Gemini API Key
- USDA FoodData Central API Key

## Instalasi

Clone repository dan masuk ke direktorinya:

```bash
git clone https://github.com/YogaTriputra/NutriLens.git
cd NutriLens
```

Buat dan aktifkan virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instal dependensi:

```bash
python -m pip install -r requirements.txt
```

## Konfigurasi

Salin file konfigurasi contoh:

```bash
cp .env.example .env
```

Isi `.env` dengan kredensial Anda:

```env
TELEGRAM_BOT_TOKEN=token_telegram_anda
GEMINI_API_KEY=api_key_gemini_anda
USDA_API_KEY=api_key_usda_anda
```

Jangan membagikan atau memasukkan file `.env` ke Git.

## Menjalankan Bot

```bash
source .venv/bin/activate
python bot.py
```

Buka bot di Telegram, kirim `/start`, kemudian kirim foto makanan. Bot akan menampilkan hasil identifikasi dan estimasi nutrisi.

## Struktur Project

```text
NutriLens/
├── bot.py              # Telegram bot dan analisis foto dengan Gemini
├── usda.py             # Pencarian dan perhitungan nutrisi USDA
├── test_usda.py        # Pengujian koneksi dan pencarian USDA
├── requirements.txt    # Dependensi Python
├── .env.example        # Contoh environment variables
└── .gitignore          # File dan folder yang tidak disimpan di Git
```

## Keterbatasan Saat Ini

- Pemilihan hasil USDA masih menggunakan hasil pencarian pertama dan dapat tidak sesuai.
- Cakupan makanan Indonesia di USDA terbatas.
- Estimasi porsi dari satu foto dapat kurang akurat tanpa objek pembanding.
- Data meal dan profil pengguna belum disimpan.
- Fitur koreksi hasil sebelum penyimpanan belum tersedia.

## Keamanan

API key dan bot token harus disimpan sebagai environment variables dalam `.env`. Folder foto sementara dan file `.env` tidak boleh dimasukkan ke repository.
