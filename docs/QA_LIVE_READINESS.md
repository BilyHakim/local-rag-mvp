# QA fondasi RAG untuk operasi live

Tanggal: 28 September 2026. Cakupan: satu host, satu worker Uvicorn, Qdrant,
Ollama, dan SQLite manifest sebagaimana `compose.staging.yml`.

## Putusan

Fondasi konsistensi data dan isolasi tenant bekerja untuk deployment kecil satu
host. Belum ada bukti yang cukup untuk menyatakan layanan siap untuk trafik live
umum. Batas kapasitas, pengelolaan versi lama, pemulihan backup, dan kualitas
jawaban pada data produksi masih perlu gate sebelum publikasi.

## Bukti QA yang dijalankan

| Area | Hasil |
| --- | --- |
| Tes otomatis | 60 lulus. Mencakup kegagalan ingestion, snapshot versi, tenant, role, body/rate limit, OCR readiness, grounding kode-angka, dan pemilihan sitasi. |
| Runtime staging sementara | API key tanpa otorisasi 401; reader menulis 403; tenant beta tidak melihat data alpha; reader alpha mendapat jawaban 417 dengan sitasi; upload ulang `qa.csv` mengganti stok 12 menjadi 29. Menggunakan Ollama dan Qdrant nyata, bukan container staging. |
| Format data | PDF teks, PDF scan OCR, DOCX, XLSX, dan CSV berhasil diunggah dan ditanya. XLS lama belum diuji. |
| Evaluasi live bawaan | 6/6 kasus lulus; p95 11,6 detik pada eksekusi berurutan tanpa beban. Dataset masih kecil dan sintetis. |
| Probe tambahan | 6/6 kasus lulus: kode sensor mirip, entitas tidak ada, atribut tidak ada, hubungan palsu, dan data tabel lintas dokumen. |
| Burst enam request | Empat HTTP 200 dan dua HTTP 503. Batas empat request aktif bekerja, tetapi kapasitas efektif belum memenuhi target trafik yang belum ditentukan. |
| Sitasi | Kasus garansi 18 bulan sebelumnya mengembalikan tiga sumber, dua tidak relevan. Setelah perbaikan hanya PDF pendukung yang dikembalikan. |

## Temuan yang masih membatasi rilis

1. **Kapasitas dan ketersediaan.** Satu worker menerima maksimal empat request
   aktif. Request berikutnya mendapat 503 dan `Retry-After`. Tidak ada antrean,
   replika, atau high availability. Ukur p95, throughput, dan tingkat 503 pada
   jumlah pengguna serta ukuran dokumen target sebelum menetapkan SLO.
2. **Pertumbuhan storage.** Penggantian sumber menjaga versi lama agar query
   yang sedang berjalan konsisten. Versi lama di Qdrant, FTS SQLite, dan file
   upload belum dibersihkan otomatis. Satu uji penggantian menghasilkan satu
   chunk tidak aktif dari tiga chunk total. Perlu prosedur pemeliharaan saat
   layanan dihentikan, dengan backup dan batas kapasitas disk.
3. **Pemulihan.** Qdrant dan SQLite harus dipulihkan sebagai satu pasangan.
   Dokumentasi backup ada, tetapi restore nyata dan pengukuran waktu pemulihan
   belum diuji.
4. **Kualitas jawaban.** Seleksi dan verifikasi masih memakai model 3B serta
   pemeriksaan token. Guard untuk kode-angka dan sitasi mengurangi kesalahan
   yang ditemukan, tetapi tidak membuktikan setiap hubungan semantik. Dataset
   enam kasus tidak mewakili dokumen dan pertanyaan pengguna sebenarnya.
5. **Batas akses.** Isolasi berada pada tenant, bukan per dokumen di dalam satu
   tenant. Kelompok dengan izin dokumen berbeda perlu tenant terpisah.
6. **Paket rilis.** Konfigurasi Compose tervalidasi, tetapi image dan stack
   container staging belum dijalankan dalam audit ini. `.env` sudah dikeluarkan
   dari index Git; riwayat commit lama tetap perlu ditinjau untuk kredensial.

## Gate minimum sebelum publikasi

- Tentukan target pengguna bersamaan, volume dokumen, dan SLO latency/error.
  Jalankan tes beban pada host target sampai target itu tercapai tanpa tingkat
  503 yang tidak diterima.
- Buat kumpulan pertanyaan nyata yang ditinjau manusia, termasuk jawaban ada,
  jawaban tidak ada, entitas mirip, tabel, PDF scan, prompt injection, dan
  sitasi. Tetapkan ambang akurasi dan fallback sebelum pengujian.
- Jalankan stack container staging dan ulangi evaluasi dengan key reader/admin
  pada minimal dua tenant.
- Lakukan satu backup dan restore pasangan Qdrant + SQLite, lalu buktikan
  jawaban, sitasi, dan isolasi tenant tetap benar setelah restore.
- Tetapkan prosedur pembersihan versi lama saat maintenance dan alarm kapasitas
  disk. Rotasi kredensial apa pun yang pernah masuk riwayat `.env`.

Putusan ini berlaku untuk hasil pengujian pada mesin audit dan dataset di atas;
tidak menyatakan semua pertanyaan akan dijawab benar.
