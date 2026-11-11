# Unggah folder knowledge

1. Restart backend setelah pembaruan, lalu tekan Ctrl+F5.
2. Buka **Knowledge Base**, lalu **Pilih folder dari perangkat** pada panel
   **Unggah folder knowledge**.
3. Periksa jumlah file yang memenuhi syarat dan file yang dilewati. Klik
   **Unggah & indeks folder** untuk mulai mengirimnya.
4. Tunggu pemrosesan selesai, lalu periksa ringkasan dan daftar hasil. Knowledge
   yang berhasil diindeks tersedia melalui fitur RAG seperti unggahan satuan.

Pemilihan folder mencakup subfolder. Format saat ini: PDF, DOCX, XLSX, XLS, dan
CSV, termasuk ekstensi huruf besar. Batas ukuran mengikuti `MAX_UPLOAD_BYTES`
server (default 25 MB per file). File kosong, format lain dan file terlalu besar
dilewati serta dicatat alasannya. Isi dokumen tetap divalidasi oleh parser backend.

Progres utama 0–100% menghitung jumlah file yang selesai diproses dari seluruh
file yang memenuhi syarat. Status pengiriman menampilkan persentase data file
aktif; setelah data terkirim, status berubah menjadi membaca/mengindeks sampai
server mengonfirmasi hasil. Bar tidak mencapai 100% hanya berdasarkan byte yang
terkirim. Seratus persen juga dapat mencakup file gagal; ringkasan membedakan
berhasil, duplikat, gagal, dilewati dan menunggu.

**Jeda setelah file ini** membiarkan file aktif selesai, lalu menghentikan antrean.
**Lanjutkan folder** memproses yang masih menunggu. **Ulangi file gagal** hanya
mengirim ulang file gagal, tanpa memproses antrean lain yang sedang dijeda.
Jika batas request HTTP 429 tercapai, aplikasi menunggu `Retry-After` sebelum
mencoba kembali, maksimal dua pengulangan per file. Jika tetap gagal, hasil
dicatat dan antrean dijeda. Gangguan koneksi diberi status gagal; pengulangan
memeriksa lagi duplikat untuk menentukan apakah file sudah aktif.

Nama sumber mempertahankan path relatif, misalnya `Knowledge/finance/report.csv`.
File bernama sama pada subfolder berbeda menjadi sumber terpisah. Duplikat folder
dicocokkan berdasarkan hash konten dan path relatif yang sama. Pilih akar folder
yang sama pada unggahan berikutnya supaya identitas sumber tetap konsisten.
Perubahan isi pada path yang sama mengikuti penggantian versi atomik ingestion
yang sudah tersedia. Upload satuan tetap memakai nama sumber sebelumnya.

Browser hanya memberikan file dari folder yang dipilih pengguna. Backend tidak
membuka path perangkat tersebut: path relatif dipakai sebagai metadata sumber,
sedangkan berkas diterima sebagai multipart dan disimpan dengan nama UUID.
Path absolut, traversal, segmen kosong dan nama yang tidak cocok ditolak.

Antrean berada di browser; biarkan halaman terbuka hingga selesai. Folder tidak
dipantau otomatis ketika isinya berubah. Untuk batch berikutnya, pilih folder
kembali. Ekstraksi, OCR PDF, embedding, Qdrant, batas sumber/chunk, otorisasi admin
dan isolasi tenant mengikuti unggah dokumen yang sudah ada.

API: `GET /api/documents/formats` mengembalikan `extensions` dan
`max_upload_bytes`. `POST /api/documents/upload` menerima field tambahan opsional
`relative_path`; kontrak unggah satu file tetap didukung.

Dasar browser: [pemilihan folder dan path relatif](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory),
serta [event progres pengiriman](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload).
