# Google OAuth Authentication untuk MAI Dashboard

## Ringkasan

Seluruh dashboard Ads dan Social Media dilindungi Google OAuth. Hanya akun
Google Workspace dengan email terverifikasi dan domain tepat `mai.co.id` yang
dapat masuk. Session berlaku absolut selama tujuh hari dan harus dibuat ulang
melalui Google setelah kedaluwarsa.

## Backend dan keamanan

- Gunakan OAuth 2.0 Authorization Code Flow dengan PKCE, state sekali pakai,
  dan scope `openid email profile`.
- Sediakan endpoint start, callback, current user, logout, dan health check.
- Verifikasi signature, issuer, audience, expiry, `email_verified`, claim `hd`,
  dan domain email pada backend. Parameter `hd` di Google hanya menjadi hint.
- Jangan menyimpan access token atau refresh token Google.
- Simpan user, login attempt, dan session pada PostgreSQL. Browser hanya
  menerima token session acak; database menyimpan hash-nya.
- Cookie session memakai `HttpOnly`, `SameSite=Lax`, host-only, dan `Secure`
  saat aplikasi menggunakan HTTPS.
- Lindungi request mutasi dengan CSRF token per session.
- Lindungi seluruh page dan API pengguna. Static asset, OAuth callback,
  health check, dan worker internal menjadi pengecualian; worker tetap memakai
  autentikasi QStash atau Cloud Tasks yang sudah ada.
- Cegah open redirect dengan hanya menerima destination path internal.

## Database dan konfigurasi

- Tambahkan `auth_users`, `auth_sessions`, dan `oauth_login_attempts` melalui
  migration yang aman dijalankan ulang, lalu selaraskan bootstrap schema untuk
  volume Docker baru.
- Environment wajib:

  ```env
  DASHBOARD_AUTH_MODE=google
  DASHBOARD_PUBLIC_BASE_URL=http://localhost:8000
  DASHBOARD_GOOGLE_OAUTH_CLIENT_ID=
  DASHBOARD_GOOGLE_OAUTH_CLIENT_SECRET=
  DASHBOARD_ALLOWED_EMAIL_DOMAIN=mai.co.id
  DASHBOARD_SESSION_TTL_DAYS=7
  DASHBOARD_OAUTH_CLOCK_SKEW_SECONDS=60
  DASHBOARD_RETRIEVAL_TOKEN=
  ```

- Untuk menguji halaman, session, redirect, dan logout tanpa kredensial Google,
  gunakan `DASHBOARD_AUTH_MODE=local`. Untuk melewati login sepenuhnya, gunakan
  `DASHBOARD_AUTH_MODE=disabled`. Kedua mode hanya diterima jika
  `DASHBOARD_PUBLIC_BASE_URL` memakai `localhost`, `127.0.0.1`, atau `::1`;
  backend menolak startup jika mode tersebut terbawa ke domain staging.
  Request dengan hostname selain loopback juga ditolak; Compose mengikat port
  dashboard ke `127.0.0.1`, sehingga mode bypass tidak terbuka melalui LAN.
  Session development tidak diterima saat mode beralih ke `google`.

- Agent retrieval menggunakan bearer `DASHBOARD_RETRIEVAL_TOKEN` khusus backend
  (secret acak minimal 32 karakter, nilai yang sama pada dashboard dan worker).
  Akses ini hanya mengizinkan GET `/api/clients` dan `/api/ads/clients/*`.
  Token tidak dapat digunakan untuk mutasi, membuat session, atau menjalankan
  worker queue. Client tidak mengikuti redirect dan hanya mengirim token melalui
  HTTPS atau HTTP loopback. Simpan sebagai secret staging, bukan variabel Vite.
- Sebelum deploy: jalankan migration `015_google_oauth.sql`, konfigurasi OAuth
  dan retrieval secret pada dashboard/worker, lalu gunakan `/healthz` untuk
  anonymous health probe. Smoke-test login, retrieval agent, dan generate report.

- Redirect URI lokal adalah
  `http://localhost:8000/api/auth/google/callback`; staging menggunakan path
  yang sama pada domain HTTPS staging.

## Frontend

- Lakukan pengecekan session sebelum dashboard memuat data.
- Login page memakai layout sekitar 55% cover gedung di kiri dan 45% form di
  kanan. Cover menjadi banner pendek pada mobile.
- Simpan cover sebagai asset lokal dan gunakan `object-fit: cover` agar mudah
  diganti tanpa mengubah layout.
- Tampilkan pesan domain ditolak, callback gagal, login kedaluwarsa, dan
  konfigurasi OAuth bermasalah.
- Setelah login, kembalikan user ke URL awal.
- Header menampilkan avatar, identitas user, dan aksi sign out.
- API client selalu mengirim cookie same-origin dan CSRF header untuk request
  mutasi; response `401` mengarahkan kembali ke login.

## Pengujian dan acceptance criteria

- Uji akun `@mai.co.id`, domain tidak valid, email belum terverifikasi, token
  invalid/expired, state replay/expired, user nonaktif, dan open redirect.
- Uji session tujuh hari, logout, revoke, hash token, dan CSRF.
- Pastikan API Social Media dan Ads menolak request tanpa session, sementara
  worker report internal tetap berjalan.
- Uji login, deep link, expiry, dan error state pada frontend.
- Visual QA pada desktop 1440 px, laptop 1024 px, dan mobile 390 px.
- Jalankan backend tests, frontend build, Docker build, dan smoke test.

## Asumsi

- Semua user aktif `@mai.co.id` memiliki akses yang sama; role dan pembatasan
  client belum termasuk fase ini.
- Login lokal dapat dinonaktifkan secara eksplisit melalui mode localhost yang
  dibatasi; staging dan production tetap wajib menggunakan Google OAuth.
- Session tidak memakai sliding expiration.
- Test otomatis memakai override aplikasi secara programatis, bukan bypass
  environment pada runtime.
