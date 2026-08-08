# Local RAG MVP

Aplikasi Retrieval-Augmented Generation (RAG) lokal dengan FastAPI, Ollama, dan Qdrant. Aplikasi menerima knowledge manual, dokumen, spreadsheet, serta data PostgreSQL opsional, lalu menggunakan data tersebut sebagai konteks jawaban.

Dokumentasi ini disusun dari implementasi di repository. Sumber konfigurasi utama adalah `app/core/config.py`, endpoint berada di `app/api`, dan dependency Python dikunci di `requirements.txt`.

## Komponen

| Komponen | Fungsi | Sumber implementasi |
| --- | --- | --- |
| FastAPI | API dan penyaji UI | `app/main.py` |
| Ollama | Chat completion dan embedding | `app/services/ollama_service.py` |
| Qdrant | Penyimpanan dan pencarian vector | `app/services/qdrant_service.py` |
| PostgreSQL | Sumber knowledge opsional | `app/services/postgres_service.py` |
| PyMuPDF + Tesseract | Ekstraksi PDF dan OCR opsional | `app/services/pdf_service.py` |
| python-docx | Ekstraksi DOCX | `app/services/docx_service.py` |
| openpyxl / xlrd | Ekstraksi XLSX dan XLS | `app/services/spreadsheet_service.py` |

UI disajikan langsung oleh FastAPI. Tidak ada proses build frontend atau dependency Node.js untuk menjalankan aplikasi.

## Prasyarat

Alur utama aplikasi memerlukan:

- Python 3.10 atau lebih baru. Source memakai sintaks seperti `str | None`, yang memerlukan Python 3.10+.
- Docker dengan Docker Compose untuk menjalankan Qdrant dari `docker-compose.yml`.
- Ollama yang dapat diakses melalui `OLLAMA_BASE_URL`.
- Model chat `qwen2.5:3b`, atau model lain yang dikonfigurasi melalui `OLLAMA_CHAT_MODEL`.
- Model embedding `nomic-embed-text`, atau model lain yang dikonfigurasi melalui `OLLAMA_EMBEDDING_MODEL`.

Komponen opsional:

- Tesseract OCR untuk PDF hasil scan/gambar ketika `OCR_ENABLED=true`.
- PostgreSQL jika sinkronisasi PostgreSQL akan digunakan.

Repository tidak menyertakan installer Python, Docker, Ollama, model Ollama, Tesseract, atau PostgreSQL.

## Setup di Windows PowerShell

Jalankan perintah dari root repository.

### 1. Buat virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Buat konfigurasi lokal

```powershell
Copy-Item .env.example .env
```

Buka `.env`, lalu sesuaikan nilainya. Jika PostgreSQL tidak digunakan, ubah:

```dotenv
POSTGRES_ENABLED=false
```

Hal ini penting karena `.env.example` mengaktifkan PostgreSQL, sedangkan nilai default di `app/core/config.py` adalah `false`.

### 3. Jalankan Qdrant

```powershell
docker compose up -d qdrant
docker compose ps
```

Konfigurasi Compose membuka port HTTP `6333`, port gRPC `6334`, dan menggunakan named volume `qdrant_data`. Aplikasi mengakses `http://localhost:6333` secara default.

### 4. Siapkan Ollama

Pastikan service Ollama berjalan dan model yang tercantum di `.env` tersedia. Dengan nilai bawaan repository:

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Aplikasi memanggil `/api/generate` untuk chat dasar, `/api/chat` untuk jawaban RAG, dan `/api/embed` untuk embedding. Base URL default adalah `http://localhost:11434`.

### 5. Jalankan aplikasi

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Kemudian buka:

- UI: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health endpoint: <http://localhost:8000/api/health>

`APP_HOST` dan `APP_PORT` tersedia di settings, tetapi `app/main.py` tidak menjalankan Uvicorn secara langsung. Saat memakai CLI, host dan port tetap harus diberikan sebagai argumen seperti contoh di atas.

## Verifikasi service

### FastAPI

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

Respons:

```json
{
  "status": "ok",
  "app": "Local RAG MVP",
  "env": "local"
}
```

Endpoint ini hanya membuktikan bahwa FastAPI berjalan. Implementasinya tidak mengecek Ollama, Qdrant, Tesseract, atau PostgreSQL.

### Ollama embedding

```powershell
$body = @{ text = "tes embedding" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/embedding-test `
  -ContentType "application/json" `
  -Body $body
```

Respons berisi dimensi vector dan 10 nilai pertama. Keberhasilan request ini membuktikan FastAPI dapat memanggil model embedding Ollama.

### Qdrant

```powershell
Invoke-RestMethod http://localhost:6333/collections
```

Collection `local_knowledge` dibuat otomatis ketika data pertama kali di-upsert atau pencarian pertama dilakukan. Ukuran vector mengikuti panjang embedding pertama.

## Konfigurasi environment

Semua konfigurasi dibaca dari `.env` oleh `pydantic-settings`.

| Variabel | Default di source | Keterangan |
| --- | --- | --- |
| `APP_NAME` | `Local RAG MVP` | Nama aplikasi dan nilai pada health response. |
| `APP_ENV` | `local` | Nama environment pada health response. |
| `APP_HOST` | `0.0.0.0` | Nilai konfigurasi host; tidak otomatis dipakai Uvicorn CLI. |
| `APP_PORT` | `8000` | Nilai konfigurasi port; tidak otomatis dipakai Uvicorn CLI. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL Ollama. |
| `OLLAMA_CHAT_MODEL` | `qwen2.5:3b` | Model untuk chat dasar dan jawaban RAG. |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Model embedding untuk indexing dan pencarian. |
| `QDRANT_URL` | `http://localhost:6333` | URL Qdrant. |
| `QDRANT_COLLECTION` | `local_knowledge` | Nama collection vector. |
| `RAG_SCORE_THRESHOLD` | `0.45` | Batas score hasil vector sebelum menjadi konteks, kecuali ada entity code yang cocok. |
| `STORAGE_DIR` | `storage` | Direktori file upload. Tidak dicantumkan di `.env.example`. |
| `CHUNK_SIZE` | `900` | Panjang maksimum chunk dalam karakter. |
| `CHUNK_OVERLAP` | `150` | Overlap antar-chunk dalam karakter. |
| `OCR_ENABLED` | `true` | Mengaktifkan fallback OCR untuk halaman PDF dengan sedikit teks. |
| `OCR_LANG` | `eng+ind` | Bahasa yang diteruskan ke Tesseract. |
| `OCR_DPI` | `200` | Resolusi render halaman sebelum OCR. |
| `OCR_MIN_TEXT_LENGTH` | `20` | OCR dijalankan jika teks native lebih pendek dari nilai ini. |
| `TESSERACT_CMD` | kosong | Path executable Tesseract; `.env.example` memberi contoh Windows. |
| `POSTGRES_ENABLED` | `false` | Mengaktifkan endpoint PostgreSQL; `.env.example` mengisinya `true`. |
| `POSTGRES_HOST` | `localhost` | Host PostgreSQL. |
| `POSTGRES_PORT` | `5432` | Port PostgreSQL. |
| `POSTGRES_DB` | `seamon-local-ipc-db` | Nama database. |
| `POSTGRES_USER` | `postgres` | User PostgreSQL. |
| `POSTGRES_PASSWORD` | kosong | Password PostgreSQL. |
| `POSTGRES_SCHEMA` | `public` | Schema yang didaftarkan dan disinkronkan. |

`CHUNK_SIZE` harus lebih besar daripada `CHUNK_OVERLAP`. Fungsi chunking menggeser posisi berikutnya dengan `end - overlap`; overlap yang sama atau lebih besar dapat membuat proses tidak maju.

## Menggunakan UI

### Menambah dokumen

1. Buka menu **Knowledge Base**.
2. Pilih PDF, DOCX, XLSX, XLS, atau CSV.
3. Klik **Unggah & indeks**.
4. Tunggu hasil jumlah halaman dan chunk.

Alur backend upload:

1. Membaca file dan menghitung SHA-256 content hash.
2. Melewati upload jika hash identik sudah ada di Qdrant.
3. Menyimpan file ke `STORAGE_DIR/documents` dengan prefix UUID.
4. Mengekstrak teks sesuai format.
5. Memecah teks dengan `CHUNK_SIZE` dan `CHUNK_OVERLAP`.
6. Meminta embedding Ollama untuk setiap chunk.
7. Menyimpan vector dan metadata ke Qdrant.

Batas 25 MB pada UI hanya diperiksa oleh JavaScript frontend. Endpoint backend tidak memiliki pemeriksaan ukuran file tersendiri.

### Menambah knowledge manual

Isi nama sumber opsional dan teks minimal 3 karakter. Data identik berdasarkan kombinasi teks dan nama sumber dilewati oleh mekanisme deduplikasi.

### Bertanya

Pertanyaan minimal 2 karakter. `top_k` menerima nilai 1 sampai 20 dengan default 5.

RAG melakukan embedding pertanyaan, pencarian Qdrant, filtering berdasarkan `RAG_SCORE_THRESHOLD`, reranking, lalu meminta Ollama menjawab hanya dari context. Jika context tidak cukup atau jawaban dinilai tidak grounded, backend mengembalikan:

```text
Maaf, informasi tersebut belum tersedia di knowledge base.
```

## Perilaku format dokumen

### PDF

- Teks native dibaca dengan PyMuPDF.
- Jika OCR aktif dan teks halaman lebih pendek dari `OCR_MIN_TEXT_LENGTH`, halaman dirender pada `OCR_DPI` lalu diproses Tesseract.
- Halaman tanpa hasil teks tidak masuk indexing.

Jika memakai `OCR_LANG=eng+ind`, instalasi Tesseract harus menyediakan data bahasa yang sesuai. Contoh path dari `.env.example`:

```dotenv
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

Jika hanya memakai PDF dengan text layer, OCR dapat dimatikan:

```dotenv
OCR_ENABLED=false
```

### DOCX

Paragraf dan isi tabel digabung menjadi satu blok dengan `page_number=1`. Implementasi tidak mempertahankan nomor halaman asli DOCX.

### XLSX, XLS, dan CSV

- Baris tidak kosong pertama dianggap header jika seluruh cell bukan numeric-like.
- Setiap baris data dibuat sebagai record teks terpisah.
- XLSX dibaca dengan `openpyxl`, XLS dengan `xlrd`, dan CSV sebagai UTF-8 dengan BOM (`utf-8-sig`).
- Metadata menyimpan sheet dan nomor baris jika tersedia.

## Integrasi PostgreSQL opsional

Integrasi ini tidak diperlukan untuk chat berbasis dokumen atau knowledge manual.

```dotenv
POSTGRES_ENABLED=true
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=seamon-local-ipc-db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_SCHEMA=public
```

Restart FastAPI setelah mengubah `.env`, karena settings dibuat saat module di-import.

### Tes koneksi

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/postgres/test-connection `
  -ContentType "application/json" `
  -Body '{}'
```

### Daftar tabel

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/postgres/tables `
  -ContentType "application/json" `
  -Body '{}'
```

### Sinkronkan tabel

```powershell
$body = @{
  tables = @("nama_tabel")
  limit_per_table = 1000
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/postgres/sync `
  -ContentType "application/json" `
  -Body $body
```

Sinkronisasi memakai `SELECT *`. Primary key dipakai sebagai row key jika tersedia; jika tidak, urutan baris digunakan. Setiap baris diformat menjadi teks, di-chunk, dibuat embedding, lalu disimpan ke Qdrant dengan `source_type=postgres`.

Nama schema dan tabel hanya menerima huruf, angka, dan underscore serta tidak boleh diawali angka. `limit_per_table` opsional dan menerima 1 sampai 100.000.

## Endpoint API

Semua endpoint API memakai prefix `/api`.

| Method | Path | Fungsi |
| --- | --- | --- |
| `GET` | `/api/health` | Status proses FastAPI. |
| `POST` | `/api/chat-basic` | Chat langsung ke Ollama tanpa RAG. |
| `POST` | `/api/embedding-test` | Membuat embedding dan menampilkan sampel. |
| `POST` | `/api/chat-rag` | Menjawab dengan context dari Qdrant. |
| `POST` | `/api/knowledge` | Menambah knowledge manual. |
| `POST` | `/api/knowledge/search` | Vector search pada knowledge. |
| `POST` | `/api/documents/upload` | Upload dan indexing dokumen. |
| `POST` | `/api/postgres/test-connection` | Menguji koneksi PostgreSQL. |
| `POST` | `/api/postgres/tables` | Mengambil daftar base table. |
| `POST` | `/api/postgres/sync` | Mengindeks tabel PostgreSQL. |

Schema request dan response lengkap tersedia di `/docs` dan `app/schemas`.

Contoh chat RAG:

```powershell
$body = @{
  question = "Apa isi utama dokumen ini?"
  top_k = 5
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/chat-rag `
  -ContentType "application/json" `
  -Body $body
```

Contoh upload tanpa UI:

```powershell
curl.exe -X POST http://localhost:8000/api/documents/upload `
  -F "file=@C:\path\ke\dokumen.pdf"
```

## Menjalankan test

```powershell
python -m pytest -q
```

`pytest.ini` menetapkan `tests` sebagai lokasi test dan `asyncio_mode=auto`.

Test integration Qdrant hanya berjalan jika `http://localhost:6333/collections` dapat diakses. Jika Qdrant tidak berjalan, test tersebut dilewati. Test lain memakai mock untuk service eksternal sehingga tidak semuanya memerlukan Ollama atau PostgreSQL aktif.

## Struktur repository

```text
app/
|-- api/            # Route FastAPI
|-- core/           # Konfigurasi environment
|-- schemas/        # Model request/response Pydantic
|-- services/       # Ollama, Qdrant, RAG, parser, OCR, PostgreSQL
|-- static/         # UI HTML, CSS, dan JavaScript
`-- main.py         # Entry point FastAPI
storage/            # Dokumen hasil upload; diabaikan Git
tests/              # Unit dan integration test
docker-compose.yml  # Qdrant
requirements.txt    # Dependency Python terkunci
```

## Troubleshooting

### Health `ok`, tetapi chat atau upload gagal

Health tidak memeriksa dependency eksternal. Verifikasi Ollama dan Qdrant secara terpisah dengan langkah di atas.

### `Gagal membuat embedding` atau `Gagal memanggil Ollama`

Periksa apakah Ollama dapat diakses melalui `OLLAMA_BASE_URL`, nama model tersedia, serta model chat dan embedding tidak tertukar. Timeout di source adalah 120 detik untuk embedding dan 300 detik untuk generate/chat.

### Error koneksi Qdrant

```powershell
docker compose ps
Invoke-RestMethod http://localhost:6333/collections
```

Jika mengganti model embedding dengan model yang dimensinya berbeda, jangan memakai collection lama tanpa migrasi. `ensure_collection()` hanya membuat collection jika belum ada dan tidak mengubah ukuran vector collection yang sudah ada. Pilihan non-destruktif adalah memakai nama `QDRANT_COLLECTION` baru.

### OCR tidak menemukan Tesseract

Pastikan Tesseract terpasang dan `TESSERACT_CMD` mengarah ke executable yang benar. OCR hanya dibutuhkan ketika fallback OCR dijalankan; PDF dengan text layer dapat dipakai tanpa OCR jika `OCR_ENABLED=false`.

### Endpoint PostgreSQL mengembalikan HTTP 503

Set `POSTGRES_ENABLED=true` di `.env`, lalu restart FastAPI. Pemeriksaan flag dilakukan sebelum koneksi database dicoba.

## Keamanan dan batasan saat ini

- Route API tidak menerapkan authentication atau authorization.
- `docker-compose.yml` mengekspos port Qdrant ke host.
- File upload disimpan di disk dan vector disimpan pada volume Qdrant.
- Belum ada endpoint untuk menghapus dokumen atau knowledge.
- UI tidak menyediakan kontrol PostgreSQL; gunakan API atau Swagger UI.

Jangan mengekspos aplikasi atau Qdrant langsung ke jaringan publik tanpa kontrol akses dan konfigurasi jaringan yang sesuai.
