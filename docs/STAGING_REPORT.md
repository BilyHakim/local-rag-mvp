# Report implementasi staging — 22 September 2026

Status: kode dan konfigurasi staging tersedia; validasi container/model nyata masih pending.

## Perubahan

| Area | Hasil |
| --- | --- |
| Ingestion | Batch embedding/upsert immutable, publikasi sumber atomic via SQLite, query snapshot konsisten, kegagalan tidak mengganti versi aktif |
| Security | API key admin/reader, tenant dari server, collection tenant terpisah, filter lexical tenant, limits body/rate/concurrency, error disanitasi |
| Retrieval | Qdrant dense + SQLite FTS5 BM25, Reciprocal Rank Fusion, pencarian token tanpa full collection scan |
| Jawaban | Evidence citation/lokasi sumber, status fallback eksplisit, angka dicek sebagai token utuh, respons kosong ditolak |
| PostgreSQL | Override koneksi ditolak di staging, table allowlist, sync snapshot lengkap, row yang dihapus tidak lagi terbaca |
| Operasional | HTTP client reuse, thread offload Qdrant/parser, readiness, metrics, audit log, Docker non-root, Compose privat, workflow CI |
| Evaluasi | Dataset enam kasus dan runner live dengan pemeriksaan fakta, fallback, citation, evidence, dan latency |

## Verifikasi yang sudah dijalankan

- `python -m pytest -q`: **46 passed, 3 skipped**.
- Tes mencakup Qdrant in-memory + SQLite nyata, failure di tengah batch, replacement,
  snapshot query, empty sync, tenant isolation, batas sumber, model change, API role/rate/body,
  alur HTTP upload → chat → citation, dan validasi batch Ollama dengan transport mock.
- Tiga tes Qdrant remote skipped karena service `localhost:6333` tidak berjalan.
- `docker compose ... config --no-env-resolution --quiet`: sukses.
- `pip check`: tidak ada dependency conflict di virtual environment lokal.
- AST check 26 file Python: sukses. `git diff --check`: sukses dengan konfigurasi Git normal repo.

## Release gate yang belum dijalankan

Docker daemon tidak aktif pada mesin audit. Karena itu container Linux belum dibangun,
model nyata belum diuji, live evaluation belum memiliki hasil akurasi/latency, dan restore
backup belum diuji. CI sudah disiapkan tetapi belum dijalankan di layanan GitHub.
Ikuti [panduan staging](STAGING.md) untuk menjalankan gate tersebut.

## Batas operasional

Satu host/satu worker, ingestion sinkron, maksimum 1.000 sumber per tenant dan 10.000 chunk
per sumber. Tidak ada ACL per dokumen atau garbage collection otomatis. Versi lama/parsial
tidak terlihat di staging tetapi tetap menggunakan storage. SQLite dan Qdrant harus dibackup
sebagai pasangan. Citation berupa selected evidence, bukan validasi entailment per klaim.

File `.env` sudah tracked sebelum perubahan ini. Isi maupun tracking file tersebut tidak
diubah; sebelum publikasi repo, keluarkan dari index dan rotasi secret bila pernah terekspos.
Perubahan `.pyc` yang sudah ada sebelum pekerjaan juga dipertahankan.
