# Riwayat RAG pribadi

Login dengan akun workspace, lalu gunakan Knowledge / RAG seperti biasa. Pertanyaan
baru dan jawaban yang berhasil diproses disimpan otomatis bersama snapshot sumber,
citation, pilihan model dan jumlah sumber. Jawaban bahwa bukti belum cukup juga
disimpan; request yang gagal tidak menimpa percakapan tersimpan.

Klik **Riwayat RAG saya** untuk membuka daftar percakapan. Pilih judul untuk
memulihkan pertanyaan, jawaban dan sumber. **Percakapan baru** memulai thread baru
tanpa menghapus yang lama. **Hapus percakapan aktif** menghapus thread terpilih
setelah konfirmasi. Pop-up mendukung tombol Tutup, Escape, dan klik di luar.

Riwayat tersimpan di server dan tetap ada setelah refresh atau login ulang.
Pemilik ditentukan dari akun login server, bukan parameter dari browser. Akun
lain dalam tenant yang sama, termasuk admin lain, tidak dapat membaca, melanjutkan,
atau menghapus thread tersebut. Tenant tetap menjadi batas penyimpanan tambahan.
API key dan mode tanpa login tidak menyediakan riwayat pribadi; endpoint RAG
sebelumnya tetap dapat digunakan tanpa penyimpanan percakapan.

Riwayat bukan knowledge tambahan dan tidak dikirim kembali sebagai konteks model.
Setiap pertanyaan tetap dicari secara mandiri dari knowledge aktif. Sumber lama
dalam riwayat adalah snapshot ketika jawaban dibuat dan dapat berbeda dari dokumen
yang sudah diperbarui. Pesan yang dibuat sebelum fitur ini tersedia tidak dapat
dipulihkan otomatis. Satu thread dibatasi 100 jawaban; mulai thread baru untuk
melanjutkan. Daftar menampilkan hingga 10.000 metadata thread terbaru tanpa
memuat seluruh isi percakapan ke dalam daftar.

Data disimpan sebagai record pribadi di `STORAGE_DIR/workspace.sqlite3`; sertakan
database tersebut dalam backup yang sudah digunakan untuk workspace. Menonaktifkan
fitur chat pada profil juga memblokir endpoint riwayat RAG milik akun itu.

Endpoint baru (memerlukan sesi login dan perlindungan CSRF yang sama dengan UI):

- `GET /api/rag-history/conversations`
- `GET /api/rag-history/conversations/{id}`
- `DELETE /api/rag-history/conversations/{id}?revision=N`
- `POST /api/rag-history/messages`, dengan question, top_k, model, serta pasangan
  conversation_id/revision saat melanjutkan thread.

Versi percakapan mencegah tab lama menimpa perubahan yang sudah disimpan tab lain.
Menghapus atau melanjutkan ID milik akun lain menghasilkan 404.

## Verifikasi dan delivery gate

- PASS: seluruh 275 tes backend, termasuk isolasi akun satu tenant, admin lain,
  tenant berbeda, penolakan API key, fitur dinonaktifkan, versi stale, sumber yang
  bertahan setelah login ulang, dan kegagalan model tanpa menimpa riwayat.
- R-03/R-25/R-34 PASS: 118 pemeriksaan layout/kontras pada tema terang/gelap dan
  layar desktop/ponsel. Snapshot pop-up diperiksa secara visual.
- R-26/R-32/R-35 PASS: 27 kelompok interaksi browser, termasuk refresh halaman,
  buka riwayat, pulihkan jawaban/sumber/model/jumlah sumber, lanjutkan percakapan,
  hapus, navigasi keyboard, Escape dan pengembalian fokus. Respons akun lama yang
  terlambat tiba diabaikan setelah pergantian identitas.
- R-27/R-39 PASS: status muat/kosong/error, kontrol disabled saat memuat, label
  kepemilikan yang terlihat dan dialog native dengan focus containment.
- R-23/R-37/R-40 PASS: memakai komponen pop-up yang sudah ada, tanpa aset atau
  dependency baru. Arah desain dicatat di `DESIGN.md`. Gate visual bersama tetap
  memakai keputusan dan pemeriksaan di `CHAT_HISTORY_POPUP_QA.md`.
- C-1/C-2/C-4/C-5 PASS: UI menyatakan kepemilikan yang benar, tindakan bekerja,
  sumber snapshot dipulihkan dan batas akun diverifikasi pada server.

Laporan klik dan kontras: `storage/ui_qa_rag_history/report.json`. Screenshot
pop-up: `storage/ui_qa_rag_history/rag-history-360-dark.png` dan pasangan tema/ukuran
lainnya. Pengujian memakai respons RAG fixture, bukan model/provider langsung.
