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
dan `store=false` untuk provider selain Google; adapter embedding memakai `/embeddings`. Provider kompatibel
harus mendukung kontrak ini. Model specialist harus dapat menghasilkan JSON sesuai
schema yang dikirim di prompt; keluaran tidak valid ditolak sebelum disimpan.
Belum ada tool loop otonom; workflow dan tindakan eksternal dijalankan kode aplikasi.

### Gemini dari Google AI Studio

```dotenv
AI_PROVIDER=api
AI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=<gemini-api-key>
AI_CHAT_MODEL=gemini-3.8-flash
EMBEDDING_PROVIDER=ollama
```

Adapter mengenali hostname Google dan tidak mengirim `store`, karena endpoint
Google menolaknya dengan HTTP 400. Request Gemini memakai `reasoning_effort=low`
dan anggaran completion minimal 4096 token untuk memberi ruang thinking sebelum
output singkat penyaring/verifikator RAG. Anggaran ini adalah batas, bukan jumlah
token yang selalu dipakai. Pilih model yang mendukung reasoning effort tersebut.
Embedding Ollama tetap digunakan sehingga indeks lama tidak perlu diganti.

Error provider ditampilkan sebagai pesan tetap tanpa body mentah, prompt, atau
key: key/izin ditolak, model tidak ditemukan, kuota tercapai, koneksi gagal, atau
model sedang sibuk. HTTP 503 dari Google memerlukan percobaan ulang setelah
beberapa saat; mengganti embedding tidak memperbaiki kondisi tersebut. Tidak ada
retry generasi otomatis. Status Online di sidebar hanya menunjukkan FastAPI hidup.

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

Posting satuan tetap memerlukan persetujuan. Content planner juga mendukung
**kampanye otomatis dari tema**: pilih model teks, kanal, jadwal pertama dalam WIB,
interval (per jam, harian, dua harian, mingguan), jumlah 1 sampai 30 posting, mode
gambar dan penggunaan knowledge. Klik **Aktifkan kampanye otomatis** untuk
mengizinkan generasi serta publikasi tanpa persetujuan per posting.

Agent membuat caption segera setelah kampanye aktif, maksimal dua slot per putaran
generasi. Publikasi berjalan pada loop terpisah agar request AI yang lambat tidak
menahan pemeriksaan posting yang sudah siap. Riwayat konten tenant menjadi konteks
dan pembanding: caption yang identik atau terlalu mirip dibuat ulang maksimal tiga
kali, lalu slot menjadi gagal jika belum memenuhi pemeriksaan. Pemeriksaan memakai
normalisasi teks, kemiripan urutan dan tumpang tindih kata pada maksimal 10.000
posting terbaru; ini bukan jaminan bahwa semua makna atau ide pasti berbeda.
Prompt menggunakan 60 caption terbaru sebagai konteks, beserta angle tiap slot.
Model memakai adapter AI yang sama, termasuk konfigurasi Command Code yang ada.

**Mode gambar Manual adalah default.** Buka slot melalui **Buka / kelola** untuk
mengunggah gambar sendiri, sebelum atau sesudah caption dibuat. Slot tanpa gambar
berstatus **Menunggu gambar** dan tidak dipublikasikan. Setelah caption dan gambar
tersedia, slot otomatis masuk antrean jadwal. Mode **Otomatis** memerlukan
`IMAGE_API_KEY` dan `IMAGE_MODEL`, lalu membuat gambar untuk setiap slot.
Instagram tetap memerlukan URL media HTTPS publik serta signing key dan token.

Kampanye dapat dijeda/dilanjutkan. Jeda mencegah generasi berikutnya dan pengambilan
posting berikutnya; request AI atau publikasi yang sudah dimulai dapat tetap
selesai. Jika jadwal terlewat ketika server mati, kampanye dijeda, atau gambar
belum tersedia, posting siap dapat terbit pada pemeriksaan berikutnya setelah
syaratnya terpenuhi. Ini dapat memproses beberapa posting yang terlambat.
Generasi yang gagal/terputus dan publikasi berstatus tidak pasti tidak diulang
secara otomatis. Periksa slot melalui editor; hasil publish ambigu tetap memakai
rekonsiliasi. Daftar planner diperbarui setiap 15 detik saat tab terlihat dan
operator tidak sedang memfokuskan kontrol pada daftar.

Tiap item mewakili satu kanal; buat kampanye terpisah untuk website dan Instagram.
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

### Prototype lokal dengan gambar sendiri dan Unified Login

Di Social Media, pilih **Tulis tanpa AI**, isi caption, simpan perubahan, lalu
unggah PNG/JPEG/WebP melalui **Gambar dari komputer**. Maksimal 10 MB dan 20 MP;
rasio Instagram 4:5 sampai 1.91:1. Gambar dikonversi menjadi JPEG. Unggah baru
membatalkan persetujuan dan jadwal, sama seperti pembuatan gambar AI.

Token Unified Login/System User memakai `graph.facebook.com`. Tambahkan
`"instagram_login_mode":"unified"` pada objek koneksi tenant yang sama dalam
`PUBLISHING_CONNECTIONS`. Tanpa field ini, konektor lama tetap memakai
`graph.instagram.com`. Jangan mengganti ID akun dengan ID business portfolio.
`GET /api/workspace/instagram/connection` memeriksa identitas melalui GET saja;
keberhasilannya belum membuktikan izin publikasi atau akses URL gambar.

Untuk prototype lokal tanpa domain, unduh executable cloudflared resmi, lalu:

```powershell
.\.venv\Scripts\python.exe -B scripts/run_instagram_prototype.py --cloudflared storage/tools/cloudflared.exe
```

Launcher memakai konfigurasi aplikasi tanpa mencetak secret, memilih Unified Login
untuk koneksi `local`, mematikan scheduler secara default, memeriksa identitas, dan membuat draft
uji dengan `assets/instagram/thumbnail-tes-integrasi.png` satu kali. Tidak ada
panggilan LLM atau gambar AI. UI tersedia di port 8011; tunnel hanya membuka
gateway media di 8012, bukan UI/API. URL publik dan signing key diatur di memori
proses; `.env` tidak diubah. Endpoint publik lain mengembalikan 404. Tutup proses
untuk menutup tunnel. Token tetap hanya di server. Quick Tunnel adalah fasilitas
pengujian sementara, bukan deployment produksi.

Untuk kampanye otomatis atau jadwal publikasi, hentikan launcher lama lalu jalankan:

```powershell
.\.venv\Scripts\python.exe -B scripts/run_instagram_prototype.py --cloudflared storage/tools/cloudflared.exe --enable-scheduler
```

Gunakan UI pada port **8011**, dan biarkan terminal/tunnel tetap berjalan. Flag
tersebut mengaktifkan scheduler pada proses launcher; `.env` tidak diubah.
Kampanye aktif yang tersimpan akan dilanjutkan ketika scheduler hidup kembali.
Kampanye yang ingin ditunda dapat dijeda dari planner sebelum server dihentikan.

Di UI, buka draft **Tes integrasi Instagram** di planner, periksa materi, klik
**Setujui versi ini**, lalu **Terbitkan sekarang**. Post dengan status `published`
tidak dipublikasikan ulang saat launcher dijalankan lagi. Jika `uncertain`, periksa
akun Instagram dan rekonsiliasi sebelum mencoba lagi.

Sumber tunnel: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Konektor mendukung **Instagram Login** (bawaan, `graph.instagram.com`) dan
**Unified Login** (`instagram_login_mode=unified`, `graph.facebook.com`).
Instagram Login memakai access token Instagram serta izin `instagram_business_basic`
dan `instagram_business_content_publish`. Unified Login memakai token Business
Integration System User dengan `instagram_basic` dan `instagram_content_publish`.
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
