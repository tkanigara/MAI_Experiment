# MAI_Experiment

Eksperimen kecil untuk mengambil data dari Instagram Business dan Facebook Page
melalui Meta Graph API, lalu menyimpannya ke file CSV lokal.

Untuk tahap ini belum ada Google Sheets, Google Slides, scheduler, atau AI
report. Fokusnya hanya:

- cek token dan ID bisa akses apa saja;
- ambil data media/post;
- ambil insight yang tersedia;
- simpan hasil bersih ke CSV.

## File Penting

- `meta_export.py`: script utama untuk mengambil data dari Meta Graph API.
- `.env`: tempat token dan ID disimpan secara lokal.
- `data/processed/`: folder output CSV dan hasil diagnosis.

Folder `data/` dan file `.env` sudah masuk `.gitignore`, jadi tidak ikut commit.

## Isi `.env`

Buat atau isi file `.env` di folder ini:

```env
META_ACCESS_TOKEN=isi_token_meta_di_sini
IG_BUSINESS_ID=isi_instagram_business_id_di_sini
FB_PAGE_ID=isi_facebook_page_id_di_sini
META_API_VERSION=v23.0
```

Catatan:

- `META_ACCESS_TOKEN` wajib ada.
- `IG_BUSINESS_ID` dipakai untuk export Instagram.
- `FB_PAGE_ID` dipakai untuk export Facebook.
- `META_API_VERSION` boleh diganti kalau versi API yang dipakai berbeda.

Script akan membaca `.env` otomatis saat dijalankan.

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

## Export Instagram

```powershell
python .\meta_export.py --platform instagram --limit 25
```

Output:

```text
data/processed/instagram_media_YYYYMMDD_HHMMSS.csv
```

Data yang dicoba diambil:

- id media;
- caption;
- timestamp;
- username;
- media type;
- permalink;
- media URL atau thumbnail URL;
- like/comment count;
- insight yang tersedia seperti reach, views, shares, saved, total interactions, dan lainnya.

Tidak semua metric pasti tersedia. Kalau Meta menolak metric tertentu, error-nya
akan disimpan di kolom `metric_errors`.

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
python .\meta_export.py --platform instagram --limit 5
```

Kalau sudah yakin token dan metric-nya stabil, limit bisa dinaikkan:

```powershell
python .\meta_export.py --platform instagram --limit 100
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

Untuk Instagram media, filter tanggal belum dipakai untuk membatasi daftar media.
Saat ini parameter tersebut hanya diteruskan ke request insight jika metric
mendukungnya. Nanti bisa dikembangkan supaya filter tanggal dilakukan setelah
media list diambil.

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

Metric kosong atau muncul di `metric_errors`

Biasanya karena permission token kurang, metric tidak tersedia untuk jenis media
tersebut, atau nama metric sudah berubah di versi Meta API yang sedang dipakai.
