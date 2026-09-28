# Self-hosted staging

Target: satu host, satu proses Uvicorn, satu volume lokal SQLite, Qdrant dan Ollama privat.
Ini bukan konfigurasi multi-replica atau high availability. Smoke test container dan
evaluasi model nyata merupakan release gate; unit test saja tidak membuktikan kualitas jawaban.

## Menjalankan

1. Salin `.env.staging.example` menjadi `.env.staging`. Ganti kedua contoh API key
   dengan key acak minimal 32 karakter (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
   Key contoh sengaja ditolak ketika startup. Jangan memasukkan secret ke Git.
   Repo sebelumnya sudah melacak `.env`; `.gitignore` tidak menghapus tracking/history.
   Sebelum publikasi, keluarkan `.env` dari index Git tanpa menghapus file lokal dan rotasi
   credential jika pernah dibagikan. Docker build mengecualikan seluruh file env.
2. Tenant berasal dari `API_KEYS`, bukan header tenant. Buat pasangan admin/reader untuk setiap
   departemen. Key hanya disimpan di memori tab UI; refresh membutuhkan login kembali.
3. Jalankan perintah berikut dari root repo (Docker daemon harus aktif):

```sh
docker compose --env-file .env.staging -f compose.staging.yml config --quiet
docker compose --env-file .env.staging -f compose.staging.yml up -d --build
docker compose --env-file .env.staging -f compose.staging.yml exec ollama ollama pull qwen2.5:3b
docker compose --env-file .env.staging -f compose.staging.yml exec ollama ollama pull nomic-embed-text
```

UI: `http://127.0.0.1:8000`. Isi API key di bagian atas. Container app berjalan sebagai
non-root, filesystem root read-only, storage persisten di `/data`. Compose ini memakai
CPU Ollama; GPU memerlukan override sesuai host. Ukur RAM/VRAM dan latency dengan dataset nyata.
Image dipin ke release versi; setelah smoke test, pin digest yang dipakai untuk reproduksibilitas.
Rujukan release: [Qdrant v1.18.0](https://github.com/qdrant/qdrant/releases/tag/v1.18.0)
dan [Ollama v0.18.0](https://github.com/ollama/ollama/releases/tag/v0.18.0).

Untuk akses dari luar host, pasang reverse proxy HTTPS/VPN di depan port loopback ini.
Jangan publish port Qdrant/Ollama. Tetapkan batas body proxy 26 MiB dan read timeout
lebih panjang dari `REQUEST_TIMEOUT`; jangan log Authorization. Port aplikasi sengaja
tidak terbuka ke jaringan sampai konfigurasi TLS host tersedia.

## Readiness dan monitoring

- `/api/health`: liveness publik; tidak menunjukkan kesiapan model.
- `/api/ready`: Bearer key reader/admin; memeriksa Qdrant, model Ollama, dan manifest.
- `/api/metrics`: admin; counters HTTP, total durasi, jawaban/fallback/retry/error.
- Log stdout: request ID, tenant, status, durasi; log ingestion berisi version/chunk count.
  Prompt, document text, API key dan connection password tidak dicatat.
- Default: 60 request/menit/key, maksimal 4 request aktif/proses, deadline 180 detik.
  Counters/rate limit di memori, direset saat restart. Satu worker wajib dipertahankan.

## Konsistensi dan data

Setiap upload/knowledge/sync menghasilkan versi immutable dengan ID chunk baru. Seluruh
batch embedding dan Qdrant upsert harus sukses sebelum satu transaksi SQLite mengaktifkan
versi baru bersama indeks FTS5. Retrieval vector dan BM25 memakai snapshot daftar versi yang
sama, lalu RRF menggabungkan ranking. Nilai score retrieval bukan confidence jawaban.

Kegagalan sebelum commit meninggalkan versi lama aktif. Crash/timeout ketika commit dapat
berarti operasi sudah selesai walau client tidak menerima sukses; periksa sumber atau ulang
upload. Versi gagal dan lama tidak muncul di staging tetapi masih memakai disk. Versi lama
dipertahankan agar query yang sedang berjalan tidak kehilangan snapshot. Belum ada GC otomatis.
Pantau pertumbuhan disk; lakukan reindex ke deployment/volume baru saat maintenance jika perlu.
Upload identik dengan filename sama dilewati. Concurrent replacement menggunakan last completed
publication wins. Dokumen kosong ditolak. Sync tabel kosong sah dan menyembunyikan baris lama.

Batas staging: 25 MiB/upload, 10.000 chunk/sumber, 1.000 sumber/tenant. Request buffer
dibatasi sebelum parsing multipart; file dibaca bertahap setelahnya. Parser/OCR tetap
memakai worker thread; cancellation tidak menghentikan thread yang sedang berjalan.
Container memory/pid limits membatasi dampaknya. Indexing sinkron belum memiliki queue/progress API;
pecah dokumen besar bila melewati deadline.

Qdrant memakai collection terpisah per tenant. SQLite menyimpan data lexical semua tenant
dengan filter tenant wajib. Satu tenant adalah batas akses: belum ada ACL per dokumen di dalamnya.
Gunakan tenant terpisah untuk kelompok dengan akses berbeda. Backup mengandung teks sensitif.

## PostgreSQL

Default dimatikan. Untuk mengaktifkan, konfigurasi koneksi di server, gunakan akun database
read-only dan view berisi kolom yang boleh dibagikan. Isi `POSTGRES_ALLOWED_TABLES` dengan
daftar view/tabel yang diizinkan; semua admin tenant pada deployment ini memiliki akses ke
allowlist tersebut. Connection override dari request ditolak di staging.
Sync mengganti satu tabel penuh secara atomic, bukan seluruh kumpulan tabel sekaligus.
Partial sync (`limit_per_table`) ditolak untuk menghindari hilangnya baris yang tidak diambil.
Row yang dihapus serta chunk berlebih tidak lagi terbaca setelah snapshot baru aktif.

## Migrasi, backup, rollback

Staging memakai `staging_v1__<tenant>` dan volume baru. Data lokal lama tidak otomatis
dimigrasi: upload ulang agar mendapat versi aktif dan indeks BM25. Mode local lama tetap
bisa membaca point legacy tanpa version; gunakan staging untuk jaminan isolasi di atas.

Backup saat app dihentikan: salin seluruh volume `rag_data` (termasuk SQLite/WAL dan upload),
serta snapshot/volume Qdrant dari waktu yang sama. Restore keduanya sebagai satu pasangan.
Jangan hanya restore Qdrant: manifest menentukan data mana yang boleh terlihat.
Model embedding yang berubah memerlukan collection + volume manifest baru dan reindex;
perbedaan nama model/dimensi ditolak. Pin juga digest model Ollama secara operasional.
Untuk rollback, gunakan image aplikasi sebelumnya dengan pasangan volume backup yang sesuai.
Lakukan latihan restore dan uji `/api/ready` serta retrieval sebelum menerima pengguna.

## Acceptance gate

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Buat API key admin untuk tenant khusus `eval` di `API_KEYS` dan restart app. Set
`RAG_EVAL_API_KEY` di environment shell (jangan key tenant pengguna). Jalankan:

```sh
python scripts/evaluate_rag.py --seed --max-p95-seconds 60
```

`--seed` menulis fixture sintetis, termasuk contoh prompt injection. Tanpa flag itu evaluasi
hanya membaca. Report JSON stdout menunjukkan fakta wajib/terlarang, bukti, fallback,
citation dan p50/p95; exit code bukan nol berarti gate gagal. Ini smoke dataset enam kasus,
bukan benchmark akurasi production. Tambahkan kasus dokumen internal, OCR, tabel panjang,
sinonim dan konflik versi; review manusia tetap diperlukan untuk faithfulness semantik.

Sebelum menyatakan staging operasional: container build sukses, readiness 200, evaluation
lulus pada model nyata, uji admin/reader/tenant terpisah, dan latihan restore berhasil.
Citation saat ini adalah evidence yang dipakai untuk jawaban beserta lokasi sumber;
belum merupakan pemetaan entailment per klaim. Verifier menggunakan model generator yang sama.
