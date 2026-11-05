# Command Code untuk chat RAG

Atur `.env` pada backend, lalu restart aplikasi:

```dotenv
AI_PROVIDER=api
AI_API_BASE_URL=https://api.commandcode.ai/provider/v1
AI_API_KEY=<key-commandcode>
AI_CHAT_MODEL=<id-model-default-yang-mendukung-chat-completions>
EMBEDDING_PROVIDER=ollama
```

Pertahankan model embedding yang dipakai saat mengindeks dokumen.
API key hanya dibaca backend. Jangan memasukkannya ke kunci akses workspace
di browser; kunci tersebut digunakan untuk autentikasi aplikasi RAG.

Di Chat RAG, pilih **Model LLM** sebelum mengirim pertanyaan. **Muat ulang model**
mengambil katalog terbaru dari provider. Pilihan berlaku untuk seluruh proses
pertanyaan tersebut, termasuk pemilihan bukti, jawaban, retry, dan verifikasi.
Pilihan tidak mengubah `.env`, model embedding, atau model pengguna lain.
Muat ulang halaman mengembalikan pilihan ke default server.

Kontrol model ada di toolbar bawah kotak pertanyaan, bersama Sumber dan Kirim.
Ikon panah melingkar memuat ulang daftar model. Ikon di pojok kanan atas
memperbesar atau memperkecil area tulis tanpa menghapus teks pertanyaan.

`GET /api/llm/models` mengembalikan `provider`, `default_model`, dan `models`.
Model dengan metadata `supported_endpoints` difilter untuk `/chat/completions`.
Katalog tidak menjamin izin paket atau saldo; provider memeriksa keduanya saat
request. Model Claude yang hanya mendukung `/messages` tidak ditampilkan.
Provider tanpa metadata endpoint mungkin menampilkan model non-chat; gunakan
model yang mendukung Chat Completions. Ollama memakai katalog lokal `/api/tags`.

`POST /api/chat-rag` dan `POST /api/chat-basic` menerima field opsional `model`.
Model eksplisit divalidasi melalui katalog sebelum digunakan. Tanpa `model`,
server memakai default `.env`, termasuk ketika pemuatan katalog di UI gagal.

Referensi: [Provider API](https://commandcode.ai/docs/provider),
[GOAT API support](https://commandcode.ai/docs/plans/goat#api-support).

## Diagnosis chat

Sapaan singkat seperti "Halo", "Haloo", atau "Selamat pagi" dibalas langsung
tanpa katalog provider, embedding, atau database. Pertanyaan substantif tetap
mengikuti pencarian dokumen dan verifikasi bukti; fitur ini bukan chat umum.

Jalankan `python scripts/diagnose_rag.py` untuk memeriksa Ollama dan Qdrant tanpa
menampilkan kredensial. Jika Qdrant tidak terhubung, jalankan Docker Desktop,
lalu `docker compose up -d qdrant`. Status Online di UI hanya memeriksa backend.

`--verify-chat --model gpt-6-luna` menguji sapaan dan pertanyaan layanan melalui
server lokal port 8000. `--trace-rag --model gpt-6-luna` menjalankan pipeline
langsung. Keduanya dapat memakai kredit API dan mengirim konteks dokumen.
Output diagnosis hanya mencatat status, jumlah sumber, dan lokasi error.

Adapter Command Code menyediakan minimal 4096 completion tokens untuk memberi
ruang bagi reasoning pada tahap selector/verifier yang sebelumnya memakai batas
64/8 token. GPT-5, GPT-6, dan Gemini memakai reasoning effort low. Respons
terpotong atau kosong menghasilkan pesan provider khusus tanpa isi mentah.
