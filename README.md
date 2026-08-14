# MAI Social Media Reporting

Web dashboard untuk mengimpor data social media, mengelola KPI, menjalankan
analisis Gemini, dan menghasilkan Google Slides report.

## Project Specs

| Bagian              | Teknologi / versi                                 |
| ------------------- | ------------------------------------------------- |
| Backend             | Python 3.11, FastAPI, Uvicorn                     |
| Database layer      | SQLAlchemy + psycopg 3                            |
| Frontend            | Node.js 20, React 18.3.1, Vite 6.4.3              |
| Database lokal      | PostgreSQL 16 Alpine                              |
| Database cloud      | Cloud SQL for PostgreSQL 18                       |
| AI orchestration    | Gemini + LangChain + LangGraph                    |
| Default AI model    | `gemini-3.1-flash-lite`                         |
| Background jobs     | Cloud Tasks + PostgreSQL job state                |
| Google integration  | Google Drive API + Google Slides API (OAuth user) |
| Container / hosting | Docker + Cloud Run gen2                           |
| CI/CD               | Cloud Build + Artifact Registry                   |
| Region staging      | `asia-southeast2` (Jakarta)                     |

Versi frontend dikunci oleh `dashboard/package-lock.json`. Dependency Python
saat ini tercantum di `requirements.txt`, tetapi belum dikunci ke versi spesifik.
Sebelum production, buat lock file agar build dapat direproduksi secara konsisten.

## Arsitektur

```text
Browser
  -> Cloud Run: React static app + FastAPI API
       -> Cloud SQL PostgreSQL
       -> Cloud Tasks -> authenticated internal worker
       -> Gemini API
       -> Google Drive & Google Slides API

GitHub main
  -> Cloud Build: test -> frontend build -> Docker build
  -> Artifact Registry
  -> Cloud Run revision baru
```

Fitur utama:

- kelola client, periode report, KPI, dan data tiap platform;
- impor CSV Instagram, Facebook, TikTok, dan YouTube;
- edit data report dan menyimpan riwayat perubahan;
- menghasilkan insight dengan Gemini;
- membuat report dari template Google Slides.

## Struktur Penting

```text
dashboard/              FastAPI API dan React frontend
agentic/                workflow analisis Gemini
db/init/001_init.sql    schema lengkap untuk database baru
db/migrations/          perubahan schema untuk database yang sudah ada
tests/                  backend unit tests dan load-test scripts
Dockerfile              production container
docker-compose.yml      environment lokal
cloudbuild.yaml         test, build image, dan deploy staging
```

## Menjalankan Secara Lokal

Prasyarat: Docker Desktop dan Docker Compose.

1. Salin konfigurasi contoh:

   ```powershell
   Copy-Item .env.example .env
   ```
2. Isi minimal `GEMINI_API_KEY`, `SLIDES_TEMPLATE_ID`,
   `GOOGLE_CREDENTIALS_FILE`, dan `GOOGLE_TOKEN_FILE`.
3. Jalankan seluruh service:

   ```powershell
   docker compose up -d --build
   ```
4. Buka:

   - dashboard: [http://localhost:8000](http://localhost:8000)
   - API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Adminer: [http://localhost:8080](http://localhost:8080)
   - PostgreSQL: `localhost:15432`

Untuk database lokal baru, Docker menjalankan `db/init/001_init.sql` saat volume
PostgreSQL pertama kali dibuat. Untuk database yang sudah berisi data, jalankan
file baru di `db/migrations/` secara berurutan; jangan menghapus volume hanya
untuk menerapkan migration.

Perintah verifikasi:

```powershell
python -m unittest discover -s tests -p "test_*.py"
Set-Location dashboard
npm ci
npm run build
```

## Environment Variables Utama

| Variable                               | Wajib | Keterangan                         |
| -------------------------------------- | ----: | ---------------------------------- |
| `DATABASE_URL`                       |    ya | SQLAlchemy URL ke PostgreSQL       |
| `GEMINI_API_KEY`                     |    ya | credential Gemini                  |
| `GEMINI_MODEL`                       | tidak | default`gemini-3.1-flash-lite`   |
| `SLIDES_TEMPLATE_ID`                 |    ya | ID template Google Slides          |
| `GOOGLE_CREDENTIALS_FILE`            |    ya | path OAuth client JSON             |
| `GOOGLE_TOKEN_FILE`                  |    ya | path OAuth user token JSON         |
| `DB_POOL_SIZE`                       | tidak | default`3`                       |
| `DB_MAX_OVERFLOW`                    | tidak | default`2`                       |
| `DB_POOL_TIMEOUT`                    | tidak | default`30` detik                |
| `DB_POOL_RECYCLE`                    | tidak | default`1800` detik              |
| `DB_CONNECT_TIMEOUT`                 | tidak | default`10` detik                |
| `GCS_REPORT_ASSET_BUCKET`            | tidak | bucket untuk upload asset editor   |
| `REPORT_QUEUE_BACKEND`               | tidak | `local` atau `qstash`               |
| `QSTASH_TOKEN`                       | queue | token publish/cancel QStash         |
| `QSTASH_CURRENT_SIGNING_KEY`         | queue | verifikasi request worker           |
| `QSTASH_NEXT_SIGNING_KEY`            | queue | key rotasi verifikasi worker        |
| `QSTASH_QUEUE`                       | queue | nama FIFO queue                     |
| `QSTASH_URL`                         | tidak | hanya untuk QStash CLI lokal        |
| `REPORT_WORKER_BASE_URL`             | queue | origin HTTPS aplikasi/worker        |

Daftar konfigurasi development yang lebih lengkap tersedia di `.env.example`.

## Google Cloud Deployment

### Resource staging yang sudah pernah digunakan

Nama berikut adalah referensi environment staging saat ini. Dapat
dipertahankan atau membuat resource baru di project milik organisasi.

| Resource                | Nilai staging                                                                    |
| ----------------------- | -------------------------------------------------------------------------------- |
| Project ID              | `mai-reporting-staging`                                                        |
| Cloud Run service       | `mai-reporting-staging`                                                        |
| Cloud SQL instance      | `mai-postgres-staging`                                                         |
| Cloud SQL connection    | `mai-reporting-staging:asia-southeast2:mai-postgres-staging`                   |
| Database / user         | `mai-socmed-report` / `mai-user`                                             |
| Artifact Registry       | `mai-reporting`                                                                |
| Runtime service account | `mai-cloud-run-staging@mai-reporting-staging.iam.gserviceaccount.com`          |
| Build service account   | `mai-cloud-build-staging@mai-reporting-staging.iam.gserviceaccount.com`        |
| Task caller SA          | `mai-report-task-caller-staging@mai-reporting-staging.iam.gserviceaccount.com` |
| Cloud Tasks queue       | `mai-report-generation-staging`                                                |
| Database export bucket  | `mai-reporting-staging-db-exports-676930675074`                                |
| Cloud Build trigger     | `deploy-mai-staging`                                                           |
| Trigger source          | branch`main`, config `cloudbuild.yaml`                                       |

Cloud Run staging menggunakan 2 vCPU, RAM 2 GiB, timeout 900 detik,
concurrency 10, minimum 0 instance, dan maksimum 2 instance.

Cloud SQL staging yang dibuat saat eksperimen menggunakan Enterprise Plus,
`db-perf-optimized-N-8`, zonal, dan disk 100 GB. Ukuran ini relatif besar untuk
staging; bisa dininjau ulang kebutuhan dan biayanya.

### 1. Project dan API

Gunakan project yang dimiliki Google Cloud Organization kantor, aktifkan billing,
lalu aktifkan API berikut:

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudtasks.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  drive.googleapis.com \
  slides.googleapis.com
```

`storage.googleapis.com` juga diperlukan bila aplikasi memakai
`GCS_REPORT_ASSET_BUCKET`.

### 2. Cloud SQL

1. Buat Cloud SQL PostgreSQL di region yang sama dengan Cloud Run.
2. Buat database dan application user.
3. Import `db/init/001_init.sql`.
4. Berikan application user akses ke object yang dibuat oleh owner schema:

```sql
GRANT USAGE ON SCHEMA public TO "mai-user";
GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public TO "mai-user";
GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA public TO "mai-user";

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "mai-user";
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "mai-user";
```

Cloud Run terhubung melalui Cloud SQL Unix socket, bukan public IP:

```text
postgresql+psycopg://USER:PASSWORD@/DATABASE?host=/cloudsql/INSTANCE_CONNECTION_NAME
```

Password pada URL harus di-URL-encode.

Untuk database yang sudah berjalan, apply migration secara berurutan:

```text
db/migrations/004_content_profile_visits.sql
db/migrations/005_report_generation_jobs.sql
```

Buat backup atau logical SQL export sebelum migration. Verifikasi tabel
`report_generation_jobs`, keenam index-nya, dan CRUD privilege application user
sebelum mengaktifkan queue.

### 3. Service Account dan IAM

Pisahkan identity runtime dari identity build.

| Identity             | Minimum access                                                     |
| -------------------- | ------------------------------------------------------------------ |
| Cloud Run runtime SA | `roles/cloudsql.client`                                          |
| Cloud Run runtime SA | `roles/secretmanager.secretAccessor` pada secret yang diperlukan |
| Cloud Run runtime SA | akses bucket asset bila fitur GCS digunakan                        |
| Cloud Run runtime SA | `roles/cloudtasks.enqueuer` pada report queue                    |
| Cloud Run runtime SA | `roles/cloudtasks.taskDeleter` pada report queue                 |
| Cloud Run runtime SA | `roles/iam.serviceAccountUser` pada task caller SA               |
| Task caller SA       | `roles/run.invoker` pada Cloud Run service                       |
| Cloud Tasks agent    | `roles/cloudtasks.serviceAgent` pada project                     |
| Cloud Build SA       | `roles/artifactregistry.writer`                                  |
| Cloud Build SA       | `roles/run.developer`                                            |
| Cloud Build SA       | `roles/logging.logWriter`                                        |
| Cloud Build SA       | `roles/iam.serviceAccountUser` pada runtime SA                   |

Hindari memakai personal account atau role `Editor` sebagai runtime identity.

### 4. Secret Manager

Buat secret berikut. Simpan value-nya melalui Console/CLI yang aman, bukan di
GitHub atau `cloudbuild.yaml`.

| Secret                                   | Isi                        |
| ---------------------------------------- | -------------------------- |
| `mai-database-url-staging`             | `DATABASE_URL` Cloud SQL |
| `mai-gemini-api-key-staging`           | Gemini API key             |
| `mai-slides-template-id-staging`       | ID template Google Slides  |
| `mai-google-oauth-credentials-staging` | OAuth client JSON          |
| `mai-google-oauth-token-staging`       | OAuth user token JSON      |

Berikan runtime SA `Secret Accessor` hanya pada kelima secret tersebut. Mount
dua file OAuth sebagai file, lalu arahkan `GOOGLE_CREDENTIALS_FILE` dan
`GOOGLE_TOKEN_FILE` ke path mount. Secret lain diinjeksi sebagai environment
variable. Gunakan versi secret eksplisit agar rollback dapat diprediksi.

OAuth token menentukan akun Google Drive yang membuat report. Untuk production,
gunakan akun kantor khusus dan simpan template/output di Shared Drive bila
tersedia. Drive dan Slides API tidak digantikan oleh IAM Cloud Run; keduanya
tetap mengikuti OAuth scopes dan permission file Google.

### 5. Artifact Registry dan Initial Cloud Run Service

Buat Docker repository di region yang sama:

```bash
gcloud artifacts repositories create mai-reporting \
  --repository-format=docker \
  --location=asia-southeast2
```

Build dan push image pertama, lalu buat Cloud Run service. Contoh konfigurasi
initial deploy:

```bash
gcloud run deploy mai-reporting-staging \
  --region=asia-southeast2 \
  --image=asia-southeast2-docker.pkg.dev/PROJECT_ID/mai-reporting/app:IMAGE_TAG \
  --service-account=RUNTIME_SERVICE_ACCOUNT \
  --set-cloudsql-instances=INSTANCE_CONNECTION_NAME \
  --set-secrets="DATABASE_URL=mai-database-url-staging:VERSION,GEMINI_API_KEY=mai-gemini-api-key-staging:VERSION,SLIDES_TEMPLATE_ID=mai-slides-template-id-staging:VERSION,/secrets/google/credentials.json=mai-google-oauth-credentials-staging:VERSION,/secrets/google/token.json=mai-google-oauth-token-staging:VERSION" \
  --set-env-vars="GOOGLE_SLIDES_AUTH=oauth,GOOGLE_CREDENTIALS_FILE=/secrets/google/credentials.json,GOOGLE_TOKEN_FILE=/secrets/google/token.json,DB_POOL_SIZE=3,DB_MAX_OVERFLOW=2,DB_POOL_TIMEOUT=30,DB_POOL_RECYCLE=1800,DB_CONNECT_TIMEOUT=10" \
  --port=8080 \
  --cpu=2 \
  --memory=2Gi \
  --timeout=900 \
  --concurrency=10 \
  --min-instances=0 \
  --max-instances=2 \
  --execution-environment=gen2 \
  --no-allow-unauthenticated
```

Ganti semua placeholder huruf besar. Untuk staging sementara yang perlu dibuka
publik, berikan `roles/run.invoker` kepada `allUsers`. Untuk production, gunakan
IAP atau identity-aware access dengan Google Group/domain kantor.

### 6. QStash Report Queue

Backend staging di VPS menggunakan Upstash QStash. Pesan dimasukkan ke named
queue sehingga report diproses FIFO dengan satu delivery aktif pada konfigurasi
default queue. QStash memanggil endpoint
`POST /internal/report-jobs/{job_id}/execute`; endpoint memverifikasi header
`Upstash-Signature` terhadap raw request body dan URL publik worker.

Set environment berikut pada backend staging:

```text
REPORT_QUEUE_BACKEND=qstash
QSTASH_TOKEN=...
QSTASH_CURRENT_SIGNING_KEY=...
QSTASH_NEXT_SIGNING_KEY=...
QSTASH_QUEUE=mai-report-generation-staging
QSTASH_RETRIES=2
QSTASH_TIMEOUT=14m
REPORT_WORKER_BASE_URL=https://ai-report.microads.co.id
REPORT_JOB_LEASE_SECONDS=900
REPORT_JOB_HARD_CANCEL=true
REPORT_CANCEL_POLL_SECONDS=1
REPORT_CANCEL_GRACE_SECONDS=2
REPORT_JOB_PROCESS_START_METHOD=spawn
```

`QSTASH_URL` tidak perlu diisi untuk Upstash Cloud. Nilainya hanya digunakan
untuk local QStash CLI, misalnya `http://127.0.0.1:8070` bila backend berjalan
langsung di host atau `http://host.docker.internal:8070` bila backend berjalan
di Docker Desktop. Untuk local CLI, `REPORT_WORKER_BASE_URL` harus menunjuk ke
dashboard lokal yang dapat dipanggil CLI, biasanya `http://127.0.0.1:8000`.

Database menjadi sumber status utama dan menyimpan queued, running, retrying,
cancel, hasil Slides, error, serta Gemini token usage. ID message QStash
disimpan pada kolom queue ID yang sudah ada, sehingga migrasi database tambahan
tidak diperlukan. Cancel menghapus message yang masih menunggu; job yang sudah
berjalan berhenti melalui cancellation checkpoint aplikasi.

Database lease mencegah eksekusi ganda. Jika worker
gagal setelah deck dibuat, retry melanjutkan `presentation_id` yang sama.
Worker menjalankan generator dalam child process terisolasi. Cancel diperiksa
setiap satu detik, diberi cooperative grace period dua detik, lalu child process
diterminasi jika masih tertahan pada request Gemini/Google. Presentation parsial
dipindahkan ke Drive Trash; jika izin Trash tidak tersedia, namanya diubah
menjadi `[CANCELED] ...`. `cancel_latency_seconds` dan hasil cleanup tersimpan
di `result_metadata` job.

Adapter Cloud Tasks lama tetap tersedia sebagai rollback path dengan
`REPORT_QUEUE_BACKEND=cloud_tasks`; variabel lengkapnya ada di `.env.example`.

### 7. Cloud Build dan GitHub

Hubungkan repository GitHub ke Cloud Build, lalu buat trigger:

- event: push ke branch `main`;
- config: `cloudbuild.yaml`;
- service account: build SA;
- substitutions mengikuti `_REGION`, `_REPOSITORY`, dan `_SERVICE_NAME`.

Pipeline yang sudah ada menjalankan:

```text
backend tests + frontend build
-> Docker image build
-> push commit SHA dan staging-latest ke Artifact Registry
-> update Cloud Run service
-> arahkan traffic ke revision baru
```

`cloudbuild.yaml` melakukan update terhadap Cloud Run service yang sudah ada.
Karena itu initial service, Cloud SQL attachment, secret, env variable, scaling,
dan IAM harus disiapkan lebih dahulu.

## Verifikasi Setelah Deploy

```bash
gcloud run services describe mai-reporting-staging \
  --region=asia-southeast2

gcloud run services logs read mai-reporting-staging \
  --region=asia-southeast2 \
  --limit=100
```

Checklist:

- revision Cloud Run berstatus `Ready`;
- halaman `/` dan `/docs` dapat dibuka sesuai kebijakan akses;
- `GET /api/clients` mengembalikan HTTP 200;
- import satu dataset uji berhasil masuk Cloud SQL;
- dry-run report berhasil dan mencatat `gemini_usage`;
- create job menghasilkan status `queued`, lalu `running` dan `completed`;
- history, retry, serta cancel job bekerja;
- Cloud Tasks request memakai OIDC task caller dan worker menolak token invalid;
- generate report membuat Google Slides dengan teks, chart, dan post image;
- rollback ke revision sebelumnya sudah pernah diuji.

## Catatan Sebelum Production

- pindahkan project, billing, OAuth consent, template, dan output Drive ke akun
  atau organisasi kantor;
- ganti akses publik dengan IAP/Google Group domain kantor;
- jangan membagikan generated Slides sebagai `anyone = editor`;
- pin dependency Python dan tambahkan dependency/security scanning;
- tentukan backup, point-in-time recovery, migration, monitoring, dan alerting;
- monitor backlog, retry, latency, dan kegagalan Cloud Tasks;
- review ukuran Cloud SQL, batas instance Cloud Run, dan biaya Gemini.
