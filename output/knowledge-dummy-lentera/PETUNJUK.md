# Paket knowledge dummy Lentera Office

Semua data dalam paket ini fiktif dan dibuat khusus untuk pengujian.

1. Ekstrak ZIP jika menggunakan arsip.
2. Buka Knowledge Base dan pilih folder `knowledge` melalui fitur unggah folder.
3. Folder berisi 6 file dalam 4 format, yaitu PDF, DOCX, XLSX, dan CSV. Semua file seharusnya lolos pemindaian format.
4. Jalankan unggah dan tunggu hingga 100%. Periksa ringkasan untuk memastikan 6 file sukses pada unggahan pertama ke knowledge yang masih bersih.
5. Buka tab Knowledge / RAG dan gunakan PERTANYAAN.md. Bandingkan dengan KUNCI_JAWABAN.md.
6. Unggah folder yang sama lagi untuk mengecek deteksi duplikat.

Pilih folder `knowledge` agar petunjuk, pertanyaan, dan kunci jawaban tetap di luar bahan retrieval. PDF berisi teks yang dapat diekstrak. Paket ini menguji ekstraksi dokumen biasa, subfolder, tabel spreadsheet, dan hubungan antarfile.

Pertanyaan 19 dan 20 menguji respons ketika informasi tidak tersedia. Pertanyaan agregasi dapat memerlukan beberapa potongan retrieval. Jawaban yang tidak lengkap perlu ditelusuri melalui sumber yang dikembalikan RAG.
