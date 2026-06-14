# MAI_Experiment

Eksperimen kecil untuk mengambil data dari Instagram Business dan Facebook Page
melalui Meta Graph API, lalu menyimpannya ke file CSV lokal, Google Sheets
intermediate, dan opsional Google Slides.

V1 scheduler fokus ke Instagram dan memakai Windows Task Scheduler. Entrypoint
scheduler adalah `run_pipeline.py`, bukan `agentic/orchestration.py`.

Flow v1:

```text
Meta Instagram API
-> raw CSV per client/platform
-> processed JSON per client/platform
-> Google Sheets intermediate
-> opsional Google Slides
```

Struktur ETL lokal:

```text
data/
  demo_client/
    instagram/
      instagram_account_raw_<run_id>.csv
      instagram_media_raw_<run_id>.csv
      instagram_processed_<run_id>.json
```

File `*_raw_*.csv` adalah hasil extract dari source API. File
`*_processed_*.json` adalah hasil transform yang sudah siap dipakai untuk
analysis/reporting. Google Sheets diperlakukan sebagai consumer dari data
processed, bukan tempat utama untuk membersihkan data.

## File Penting

- `extract_instagram_raw.py`: command sederhana untuk mengambil raw CSV Instagram saja.
- `ETL_Pipeline/extract/meta_instagram.py`: helper low-level Meta Graph API khusus Instagram.
- `meta_export.py`: script legacy untuk diagnosis/Facebook/export lama.
- `ETL_Pipeline/extract/instagram.py`: extract Instagram raw CSV ke `data/<client>/instagram/`.
- `ETL_Pipeline/transform/instagram.py`: transform raw CSV menjadi processed payload.
- `ETL_Pipeline/load/load.py`: simpan processed payload sebagai JSON.
- `analytics_pipeline.py`: hitung KPI Instagram dari CSV.
- `ai_insight_pipeline.py`: buat insight JSON dari KPI via Gemini atau fallback.
- `push_to_sheets.py`: tulis raw/KPI/AI insight/report run ke Google Sheets intermediate.
- `run_pipeline.py`: entrypoint scheduler-ready.
- `.env`: tempat token dan ID disimpan secara lokal.
- `data/<client>/instagram/`: folder output raw CSV dan processed JSON Instagram.
- `data/processed/`: folder legacy output CSV dan hasil diagnosis.

Folder `data/`, file `.env`, `token.json`, `credentials.json`, dan `*.json`
sudah masuk `.gitignore`, jadi credential service account seperti
`optimum-essence-497706-i6-1c879e7ef3bd.json` tidak ikut commit.

## Isi `.env`

Buat atau isi file `.env` di folder ini:

```env
META_ACCESS_TOKEN=isi_token_meta_di_sini
IG_BUSINESS_ID=isi_instagram_business_id_di_sini
FB_PAGE_ID=isi_facebook_page_id_di_sini
META_API_VERSION=v23.0
META_EXPORT_LIMIT=5

GOOGLE_API_KEY=isi_google_gemini_api_key_di_sini
GEMINI_API_KEY=isi_google_gemini_api_key_di_sini
GEMINI_MODEL=gemini-2.5-flash

INTERMEDIATE_SPREADSHEET_ID=1Bp-msgx3dieEHyfw0xHDPYLGHTA47_or2PTPJJVbiCA
MASTER_SPREADSHEET_ID=18B6jAIq-A55o7lpRrHX2xDOQ33eLiNuIUQNTRzjOG5I
GOOGLE_SERVICE_ACCOUNT_FILE=optimum-essence-497706-i6-1c879e7ef3bd.json

SLIDES_TEMPLATE_ID=isi_google_slides_template_id_atau_url
GOOGLE_SLIDES_SERVICE_ACCOUNT_FILE=optimum-essence-497706-i6-1c879e7ef3bd.json
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
```

Catatan:

- `META_ACCESS_TOKEN` wajib ada.
- `IG_BUSINESS_ID` dipakai untuk export Instagram.
- `FB_PAGE_ID` dipakai untuk export Facebook.
- `META_API_VERSION` boleh diganti kalau versi API yang dipakai berbeda.
- `INTERMEDIATE_SPREADSHEET_ID` wajib untuk pipeline normal.
- `MASTER_SPREADSHEET_ID` disimpan untuk tahap berikutnya, belum dibaca di v1.
- `GOOGLE_SERVICE_ACCOUNT_FILE` dipakai untuk tulis Google Sheets intermediate.
- `GOOGLE_SLIDES_SERVICE_ACCOUNT_FILE` diprioritaskan untuk Google Slides scheduler.
- `GOOGLE_CREDENTIALS_FILE` dan `GOOGLE_TOKEN_FILE` tetap bisa dipakai untuk Google Slides via OAuth.

Script akan membaca `.env` otomatis saat dijalankan.

## Scheduler Pipeline V1

Dry-run aman tanpa menulis Google Sheets dan tanpa membuat Slides:

```powershell
python .\run_pipeline.py --client-id demo_client --frequency weekly --dry-run
```

Run normal tanpa Slides:

```powershell
python .\run_pipeline.py --client-id demo_client --frequency weekly --no-slides
```

Run normal dengan Google Slides:

```powershell
python .\run_pipeline.py --client-id demo_client --frequency weekly --generate-slides
```

Tab Google Sheets intermediate yang dibuat/dipastikan oleh pipeline:

```text
instagram
facebook
youtube
tiktok
report_runs
```

V1 baru mengisi tab `instagram`. Isi tab ini adalah data siap pakai dalam satu
baris per post: metadata run/client, account Instagram, posting ID, waktu post,
jenis konten, permalink/media URL, KPI post, KPI total periode, ranking top
content, dan AI insight/recommendation. Tab `facebook`, `youtube`, dan `tiktok`
dibuat sebagai struktur awal untuk fase berikutnya.

Contoh Windows Task Scheduler action:

```text
Program/script: python
Add arguments: .\run_pipeline.py --client-id demo_client --frequency weekly --no-slides
Start in: C:\Gawe\MAI\MAI_Experiment
```

Failure policy:

- Meta gagal: status `failed`.
- AI gagal: pipeline lanjut dengan fallback dan `warning`.
- Sheets gagal: pipeline berhenti.
- Slides gagal: status `partial_success`.

## Test Prototype KPI Report

Prototype KPI report dijalankan lewat terminal:

```powershell
python .\Main.py
```

Contoh prompt:

```text
buatkan KPI report dari instagram_media_20260513_105532.csv
```

Kalau berhasil, report akan muncul sebagai jawaban chat di terminal. Prototype ini
belum menyimpan hasil report ke file.

## Test Agentic Slides Generator

Folder `agentic/` adalah prototype agent berbasis LangGraph/LangChain. Agent ini
sekarang punya tool:

```text
generate_google_slides_report
```

Tool tersebut akan memanggil pipeline Google Slides yang sama dengan
`generate_slides_example.py`. Insight dan recommendation akan dibuat dengan
Gemini jika `GOOGLE_API_KEY` tersedia.

Pastikan `.env` punya:

```env
GOOGLE_API_KEY=isi_google_gemini_api_key_di_sini
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
```

Jalankan agent:

```powershell
python .\agentic\orchestration.py
```

Contoh prompt:

```text
generate google slides report dari data instagram terbaru untuk client Demo Client periode May 2026
```

Preview tanpa membuat Slides baru:

```text
preview mapping google slides report dari data instagram terbaru
```

Untuk mematikan AI insight dan memakai teks fallback template:

```powershell
python .\generate_slides_example.py --dry-run --no-ai-insights
```

Kalau dependency belum ada:

```powershell
python -m pip install -r requirements.txt
```

## Contoh Generate Google Slides

File `generate_slides_example.py` adalah contoh awal untuk mengisi Google Slides
template dari CSV Instagram.

Flow script:

```text
CSV Instagram
-> hitung KPI sederhana
-> buat mapping {{PLACEHOLDER}}
-> copy Google Slides template
-> replace placeholder di file copy
```

Template default yang dipakai:

```text
https://docs.google.com/presentation/d/1ZeYnxJOVIjjEbHqa6BJBh30JE3m2SVQuyEcOu4WaiMY/edit?usp=sharing
```

Tes mapping tanpa akses Google:

```powershell
python .\generate_slides_example.py --dry-run
```

Tes dengan CSV tertentu:

```powershell
python .\generate_slides_example.py --dry-run --csv .\data\processed\instagram_media_20260513_105532.csv
```

Tes dengan media CSV dan account CSV tertentu:

```powershell
python .\generate_slides_example.py --dry-run --csv .\data\processed\instagram_media_YYYYMMDD_HHMMSS.csv --account-csv .\data\processed\instagram_account_YYYYMMDD_HHMMSS.csv
```

Untuk benar-benar membuat Google Slides baru, pakai OAuth user login:

1. Buat OAuth Client ID di Google Cloud.
2. Download file OAuth credential.
3. Simpan sebagai `credentials.json` di folder project, atau set path-nya di `.env`.
4. Jalankan script.
5. Browser akan terbuka untuk login Google.
6. Setelah login berhasil, script otomatis membuat `token.json`.

Contoh `.env`:

```env
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
REPORT_CLIENT_NAME=Demo Client
REPORT_AGENCY_NAME=MAI
REPORT_PERIOD=May 2026 Week 2
IG_REACH_TARGET_MONTH=10000
IG_REACH_TARGET_YEAR=120000
```

Generate report:

```powershell
python .\generate_slides_example.py
```

Kalau berhasil, terminal akan menampilkan link Google Slides baru.

Catatan OAuth:

- `credentials.json` berasal dari Google Cloud Console.
- `token.json` tidak didownload manual. File ini dibuat otomatis setelah login pertama.
- Kalau credential kamu bertipe `web`, pastikan Authorized redirect URI berisi:

```text
http://localhost:8080/
```

- Kalau muncul `redirect_uri_mismatch`, tambahkan URI di atas atau buat OAuth Client ID tipe Desktop App.
- `credentials.json` dan `token.json` sudah masuk `.gitignore`.

Catatan: prototype ini baru replace text placeholder. Untuk image placeholder
seperti `{{TOP_POST_1_IMAGE}}`, script sementara mengisi URL gambar. Tahap
berikutnya bisa dikembangkan menjadi insert image langsung ke posisi placeholder.

Placeholder script ini sudah disesuaikan dengan template PDF `Social Media KPI
Report - Template.pdf`. Data yang bisa dihitung dari CSV Instagram akan diisi,
sedangkan bagian yang belum punya data seperti demographics, competitor, YouTube,
TikTok, web, SEO, dan ads akan diisi `-` atau teks prototype.

## Cek Token dan ID

Jalankan ini dulu sebelum export data:

```powershell
python .\meta_export.py --platform diagnose
```

Output akan dibuat di:

```text
data/processed/meta_diagnose_YYYYMMDD_HHMMSS.json
```

Cara membaca hasil diagnosis:

- Kalau `token_owner_me` berhasil, token bisa dipakai untuk memanggil endpoint `/me`.
- Kalau `user_pages_if_user_token` berisi list Page, token kemungkinan adalah User Access Token yang punya akses ke Page.
- Kalau `fb_page_id` berhasil, `FB_PAGE_ID` valid dan token punya akses ke Page itu.
- Kalau response `fb_page_id` punya `instagram_business_account`, berarti Page tersebut terhubung ke akun Instagram Business/Creator.
- Kalau `ig_business_id` berhasil, `IG_BUSINESS_ID` valid dan token bisa membaca akun Instagram tersebut.

## Extract Instagram Raw CSV

Untuk mengambil raw CSV Instagram saja, tanpa transform, Sheets, atau Slides:

```powershell
python .\extract_instagram_raw.py --client-id japaholic --limit 25
```

Dengan filter periode insight:

```powershell
python .\extract_instagram_raw.py --client-id japaholic --limit 25 --since 2026-06-01 --until 2026-06-14
```

Output:

```text
data/<client_id>/instagram/instagram_account_raw_<run_id>.csv
data/<client_id>/instagram/instagram_media_raw_<run_id>.csv
```

Data account raw yang diambil:

- `id`, `username`, `name`;
- `followers_count`, `follows_count`, `media_count`;
- `profile_picture_url`;
- `snapshot_date`, `snapshot_time`;
- `raw_demographic_age_gender` dan `raw_demographic_country` dari `follower_demographics`;
- `raw_reached_demographic_age_gender` dan `raw_reached_demographic_country` dari `reached_audience_demographics`.

Data media raw yang diambil per postingan:

- `id`, `timestamp`, `username`;
- `media_type`, `media_product_type`;
- `permalink`, `media_url`, `thumbnail_url`;
- `like_count`, `comments_count` dari media fields;
- `insight_views`, `insight_reach`, `insight_likes`, `insight_comments`;
- `insight_reposts`, `insight_shares`, `insight_saved`, `insight_total_interactions`.

Untuk kebutuhan laporan per postingan, row media juga membawa raw demographic account:

- `audience_demographic_source = instagram_account_insights`;
- `account_raw_demographic_age_gender`;
- `account_raw_demographic_country`;
- `account_raw_reached_demographic_age_gender`;
- `account_raw_reached_demographic_country`.

Catatan penting: Meta Graph API menyediakan metric seperti views/reach/likes/comments/shares/saved/reposts sebagai insight per media. Demografi umur, gender, dan country tidak tersedia sebagai insight per media biasa, jadi data demografi yang ditempel ke setiap row media berasal dari account/reached audience insights. Tahap transform/report boleh mengolah raw demographic ini menjadi persentase seperti Men/Women, Country, dan Age bucket.

Kolom yang tidak dipakai laporan tidak diambil/ditulis ke CSV raw, misalnya `caption`, `metric_errors`, `raw_insights`, `raw_media`, dan payload debug besar lain.

## Export Facebook

```powershell
python .\meta_export.py --platform facebook --limit 25
```

Output:

```text
data/processed/facebook_posts_YYYYMMDD_HHMMSS.csv
```

Data yang dicoba diambil:

- id post;
- message;
- created time;
- permalink;
- gambar utama jika ada;
- reaction/comment/share count;
- post insight yang tersedia seperti impressions, reach unique, engaged users, clicks, dan lainnya.

## Export Instagram dan Facebook Sekaligus

```powershell
python .\meta_export.py --platform all --limit 25
```

## Kenapa Default `--limit 25`?

Default 25 dipakai supaya eksperimen awal tidak terlalu lama dan tidak terlalu
banyak request ke Meta API.

Alasannya: satu media/post tidak cuma butuh satu request. Script mengambil daftar
media/post dulu, lalu mengambil insight per item. Kalau beberapa metric ditolak
oleh Meta, script akan mencoba fallback satu-satu agar data yang masih valid
tetap masuk CSV. Proses fallback ini bisa membuat runtime terasa lebih lama.

Kalau mau lebih cepat:

```powershell
python .\extract_instagram_raw.py --client-id japaholic --limit 5
```

Kalau sudah yakin token dan metric-nya stabil, limit bisa dinaikkan:

```powershell
python .\extract_instagram_raw.py --client-id japaholic --limit 100
```

## Progress Saat Berjalan

Saat export, script akan menampilkan progress seperti:

```text
Instagram: mengambil daftar media, maksimal 25 item...
Instagram: ditemukan 25 media. Mulai ambil insight per media.
Instagram: media 1/25 (IMAGE) id=...
Instagram: media 2/25 (VIDEO) id=...
```

Jadi kalau proses lama, kita bisa lihat sudah sampai item ke berapa.

## Filter Tanggal

Untuk Facebook post, `--since` dan `--until` bisa dipakai:

```powershell
python .\meta_export.py --platform facebook --since 2026-05-01 --until 2026-05-13
```

Untuk Instagram raw extract, `--since` dan `--until` diteruskan ke request media insight. Daftar media tetap dibatasi oleh `--limit`; filter tanggal post bisa ditambahkan di tahap berikutnya kalau dibutuhkan.

## Masalah Umum

`Missing environment variable: META_ACCESS_TOKEN`

Artinya `.env` belum ada, nama variabel salah, atau script dijalankan dari folder
yang berbeda. Jalankan command dari folder `MAI_Experiment`.

`Skip Instagram: IG_BUSINESS_ID is not set.`

Artinya `.env` belum punya `IG_BUSINESS_ID`, jadi export Instagram dilewati.

`Skip Facebook: FB_PAGE_ID is not set.`

Artinya `.env` belum punya `FB_PAGE_ID`, jadi export Facebook dilewati.

`Meta API error: Invalid OAuth 2.0 Access Token`

Artinya token yang terbaca dari `.env` ditolak oleh Meta. Kemungkinan umum:

- token sudah expired;
- yang dimasukkan bukan access token yang benar;
- token diawali teks `Bearer `;
- token tercopy dengan spasi, quote aneh, atau karakter tambahan;
- token tidak punya akses ke Page/Instagram yang ID-nya dipakai;
- token berasal dari app/user/Page yang berbeda.

Langkah cek paling awal:

```powershell
python .\meta_export.py --platform diagnose
```

Kalau diagnosis juga gagal dengan error token invalid, berarti masalahnya ada
di token sebelum masuk ke urusan Page ID atau IG Business ID.

Metric Instagram kosong

Biasanya karena permission token kurang, metric tidak tersedia untuk jenis media
tersebut, atau nama metric sudah berubah di versi Meta API yang sedang dipakai.

`[LLM ERROR] Bad request`

Artinya request ke Hugging Face gagal sebelum tool CSV dijalankan. Kemungkinan:

- `HF_API_KEY` salah atau sudah tidak aktif;
- token belum punya akses ke model yang dipakai;
- nama `HF_MODEL` tidak cocok;
- provider Hugging Face tidak mendukung model tersebut untuk chat completion;
- response model terlalu panjang atau request melebihi limit.

Langkah cek:

1. Pastikan `.env` punya `HF_API_KEY`.
2. Pastikan akun Hugging Face punya akses ke model di `HF_MODEL`.
3. Coba ganti `HF_PROVIDER=auto`.
4. Coba turunkan `HF_MAX_TOKENS=300` kalau request terlalu besar.
