# Company AI Workspace

Satu aplikasi dengan tiga mode: Knowledge / RAG, SEO Specialist, dan Social Media
Specialist. Jalankan FastAPI seperti sebelumnya, lalu buka UI pada port aplikasi.
Fitur specialist dan profil perusahaan memerlukan role admin; reader tetap hanya
memiliki akses baca RAG seperti sebelumnya. Setiap tenant mempunyai profil, audit,
draft, gambar, serta koneksi publishing sendiri.

## Prototype dengan API AI

Tambahkan konfigurasi berikut ke `.env` lokal atau `.env.staging` sesuai deployment.
Isi model dengan ID model yang tersedia pada akun/provider Anda. Tidak ada API key
yang harus dimasukkan melalui UI atau dikirim ke chat.

```dotenv
AI_PROVIDER=api
AI_API_BASE_URL=https://api.openai.com/v1
AI_API_KEY=<key-provider>
AI_CHAT_MODEL=<model-teks-yang-mendukung-chat-completions>
EMBEDDING_PROVIDER=api
AI_EMBEDDING_MODEL=<model-embedding>
```

Adapter teks memakai `/chat/completions`, `messages`, `max_completion_tokens`,
dan `store=false`; adapter embedding memakai `/embeddings`. Provider kompatibel
harus mendukung kontrak ini. Model specialist harus dapat menghasilkan JSON sesuai
schema yang dikirim di prompt; keluaran tidak valid ditolak sebelum disimpan.
Belum ada tool loop otonom; workflow dan tindakan eksternal dijalankan kode aplikasi.

`AI_PROVIDER` juga berlaku untuk jawaban RAG dan chat basic. Embedding mempunyai
pilihan provider tersendiri. Untuk prototype API penuh, Ollama tidak diperlukan;
Qdrant tetap diperlukan untuk indexing/retrieval dokumen. Specialist tetap dapat
digunakan hanya dengan profil dan brief ketika checkbox knowledge dimatikan.
Jika retrieval gagal, UI memberi peringatan bahwa hasil tidak memakai dokumen.

Dokumen dan indeks tetap disimpan lokal. Potongan knowledge yang dipilih, profil,
brief, riwayat revisi, atau hasil audit akan dikirim ke provider API saat digunakan.
Mode API bukan deployment yang sepenuhnya terisolasi/offline.

**Jangan mengganti embedding pada indeks lama.** Gunakan `STORAGE_DIR` dan
`QDRANT_COLLECTION` baru, lalu index ulang dokumen. Identitas embedding disimpan
di manifest untuk mendeteksi perubahan. Mengganti model teks saja tidak memerlukan
reindex. Backup profil/planner jika ingin memindahkannya ke deployment baru.

## Profil perusahaan dan knowledge

Isi menu Profil perusahaan: nama, deskripsi, audiens, produk, gaya bahasa, CTA,
batas klaim, dan arahan visual. Upload brand guideline/dokumen produk melalui
Knowledge Base. Specialist mengambil konteks melalui pencarian vector + keyword
tenant yang sama, lalu menampilkan referensi yang digunakan. Referensi retrieval
bukan jaminan setiap usulan kreatif adalah fakta; tinjau klaim sebelum persetujuan.
RAG mempertahankan aturan jawab-fakta-dengan-bukti dan fallback sebelumnya.

## SEO Specialist

Masukkan URL publik dan tujuan. Aplikasi memeriksa HTTP status, title, meta
description, H1, canonical, arahan robots, atribut alt gambar, serta jumlah internal
link. Aplikasi juga mengambil `/robots.txt` dan `/sitemap.xml`; status dan cuplikan
tersedia pada detail hasil, bukan verifikasi menyeluruh aturan robots/sitemap.
Usulan AI dipisahkan dari temuan deterministik. Jika AI gagal, hasil HTML tetap
tersimpan dan dapat diunduh sebagai JSON.

Audit hanya satu halaman HTML statis. Belum ada rendering JavaScript, crawl seluruh
situs, Search Console, keyword volume, traffic, ranking, Core Web Vitals, atau
perubahan codebase. Situs yang memblokir crawler dapat memberi hasil terbatas.
Fetch membatasi ukuran dan waktu, memvalidasi DNS, menghubungkan langsung ke IP
publik yang divalidasi dengan Host/TLS SNI asli, serta memvalidasi setiap redirect.
URL private, loopback, link-local, kredensial di URL, dan port selain 80/443 ditolak.

## Social Media: manual dan otomatis

1. Pada Chat / Manual, pilih Instagram atau Website dan tulis brief.
2. Specialist membuat judul, caption/artikel, hashtag, brief gambar, dan catatan.
3. Tulis instruksi berikutnya untuk merevisi draft yang sama. Riwayat sepuluh
   instruksi/hasil terbaru disimpan dan dipakai sebagai konteks revisi.
4. Edit materi secara langsung jika perlu, lalu simpan perubahan.
5. Generate gambar jika dibutuhkan. Instagram memerlukan gambar sebelum persetujuan.
6. Tinjau materi, lalu pilih **Setujui versi ini**.
7. Pilih **Terbitkan sekarang** atau setel jadwal WIB pada versi yang disetujui.

Planner otomatis menerbitkan **materi final yang sudah disetujui**. Belum ada
pembuatan konten dari tema berulang lalu langsung publish tanpa review. Tiap item
mewakili satu kanal; buat draft terpisah untuk adaptasi website dan Instagram.
Setiap perubahan teks, revisi AI, atau pembuatan gambar membatalkan persetujuan
dan jadwal. Pembatalan jadwal mengembalikan posting menjadi draft. Posting yang
sudah terbit tidak diedit/dihapus dari platform melalui aplikasi ini.

Status: `draft → approved → scheduled/publishing → published`. Kegagalan sebelum
publish menjadi `failed`. Hasil operasi publish yang tidak pasti menjadi `uncertain`.
Periksa kanal tujuan, lalu gunakan form rekonsiliasi untuk mencatat ID/link jika
sudah terbit, atau mengembalikan ke draft jika telah dipastikan belum terbit.
Tidak ada blind retry setelah operasi publish yang ambigu. Ini mengurangi risiko
duplikasi, bukan jaminan exactly-once lintas database lokal dan platform eksternal.

## Gambar

```dotenv
IMAGE_API_BASE_URL=https://api.openai.com/v1
IMAGE_API_KEY=<key-gambar>
IMAGE_MODEL=<model-gambar>
```

Adapter meminta `/images/generations`, ukuran 1024×1024, satu gambar, dan membutuhkan
respons `data[0].b64_json`. Contohnya model GPT Image yang mengembalikan base64 secara
default. Provider yang hanya mengembalikan URL belum didukung. Gambar dikonversi ke
JPEG lokal untuk preview dan posting satu gambar Instagram. Penggunaan API gambar
dapat menimbulkan biaya provider. Model gambar independen dari model teks/Ollama.

Preview memerlukan autentikasi workspace. Meta mengambil media melalui URL HTTPS
bertanda tangan dengan masa berlaku 24 jam; siapa pun yang memiliki URL tersebut
dapat mengambil gambar sampai kedaluwarsa. Jangan membagikan URL tersebut di log.

## Instagram API resmi

Implementasi memakai **Instagram Login**, bukan Facebook Login: host
`graph.instagram.com`, akun Professional Business/Creator, access token Instagram,
serta izin `instagram_business_basic` dan `instagram_business_content_publish`.
Selesaikan setup aplikasi Meta dan akses/peninjauan yang sesuai dengan akun yang
dikelola. Aplikasi ini belum menyediakan OAuth onboarding atau refresh token;
token aktif disediakan dan diperbarui oleh operator di konfigurasi server.

```dotenv
PUBLIC_BASE_URL=https://workspace.example.com
MEDIA_SIGNING_KEY=<random-secret-minimal-32-karakter>
INSTAGRAM_API_VERSION=v25.0
PUBLISHING_CONNECTIONS='{"local":{"instagram_user_id":"123456789","instagram_access_token":"<token-instagram>"}}'
```

`PUBLIC_BASE_URL` harus menunjuk aplikasi yang dapat diakses Meta melalui HTTPS.
Reverse proxy harus meneruskan `/media/...` ke FastAPI tanpa mengharuskan header
Authorization; endpoint tersebut memeriksa signature dan expiry. Route `/api/...`
tetap memakai autentikasi. Jangan mengekspos deployment lokal tanpa autentikasi
ke internet; gunakan staging + HTTPS sesuai `STAGING.md`. Pengaturan proxy/hosting
publik tidak dilakukan otomatis oleh kode ini.

Alur: buat media container → periksa kesiapan → publish → ambil permalink. ID
container disimpan sebelum publish untuk pemeriksaan bila operasi terputus.
Versi awal hanya single-image JPEG + caption, bukan carousel, Reel, Story, atau
analytics. Batas caption termasuk hashtag: 2200 karakter. Konfirmasi dukungan
versi API dan permission pada aplikasi Meta saat konfigurasi akun nyata.

## Website melalui WordPress

Karena CMS belum ditentukan, konektor awal memakai WordPress REST API + Application
Password, bukan password login utama. Gunakan akun dengan hak publikasi yang sesuai.
Kredensial ditentukan per tenant; jangan menggunakan token tenant lain sebagai fallback.

```dotenv
PUBLISHING_CONNECTIONS='{"local":{"wordpress_url":"https://website.example.com","wordpress_username":"publisher","wordpress_app_password":"<application-password>"}}'
```

Gabungkan key Instagram dan WordPress dalam objek tenant yang sama jika memakai
keduanya. Untuk staging, ganti `local` dengan tenant pada `API_KEYS`. Endpoint
status hanya menampilkan flag koneksi, tidak mengembalikan token/password.

Artikel diperlakukan sebagai plain text dan di-escape menjadi paragraf HTML. Jika
ada gambar, gambar diunggah ke media WordPress dan dijadikan featured image.
Posting dibuat sebagai draft terlebih dahulu, ID disimpan, baru dipublikasikan.
Kegagalan dapat meninggalkan media atau draft di WordPress untuk diperiksa operator.
CMS lain memerlukan adapter publishing tambahan.

## Scheduler, storage, dan operasi

```dotenv
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_SECONDS=30
```

Jalankan **satu proses Uvicorn, satu worker** seperti deployment staging yang ada.
Scheduler hidup dalam lifespan FastAPI; tidak perlu cron tambahan. Jangan memakai
`--reload` untuk operasi publishing. Jadwal disimpan dalam UTC dan input UI memakai
WIB/UTC+7 secara eksplisit. SQLite mengklaim job secara atomik; jadwal yang lewat
saat aplikasi mati diproses setelah server kembali berjalan. Tidak ada jaminan
terbit tepat pada detik jadwal. Scheduler nonaktif menolak penjadwalan baru.

Posting `publishing` yang tidak selesai lebih dari 15 menit ditandai `uncertain`
pada tick scheduler berikutnya, bukan dikirim ulang. Jika scheduler dinonaktifkan,
aktifkan kembali untuk menjalankan recovery sebelum rekonsiliasi melalui UI.

Backup `STORAGE_DIR/workspace.sqlite3` (beserta WAL jika server aktif) dan
`STORAGE_DIR/workspace_media/`, selain manifest dan Qdrant yang sudah ada. Gunakan
backup SQLite konsisten atau hentikan aplikasi sebelum menyalin. Belum ada GC media
lama otomatis, multi-replica, queue terdistribusi, atau OAuth management UI.

## API dan verifikasi

Endpoint `/api/workspace` mencakup `/status`, `/profile`, `/seo/audits`,
`/social/generate`, `/social/posts`, dan aksi per-post `/image`, `/approve`,
`/schedule`, `/cancel`, `/publish`, `/resolve`. Perubahan post memerlukan `revision`
terbaru. Konflik versi/status mengembalikan 409, ID tenant lain mengembalikan 404,
dan reader mengembalikan 403. Schema lengkap ada pada `/docs` dalam mode lokal.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/workspace.js
```

Test mencakup provider routing, audit berbukti saat AI gagal, penolakan URL internal,
isolasi tenant, revisi draft, invalidasi persetujuan, signed media, scheduler,
konflik publikasi bersamaan, hasil ambigu tanpa retry, dan kontrak HTTP publisher.
Integrasi AI/Meta/WordPress dalam test menggunakan mock; tetap lakukan smoke test
dengan akun dan deployment uji sebelum mengandalkan publikasi operasional.

Rujukan kontrak API:

- [OpenAI Chat API](https://platform.openai.com/docs/api-reference/chat/create)
- [OpenAI Images API](https://developers.openai.com/api/reference/resources/images/methods/generate)
- [Meta Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [WordPress Posts REST API](https://developer.wordpress.org/rest-api/reference/posts/)
