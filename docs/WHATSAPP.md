# Asisten WhatsApp melalui WAHA

Asisten mengirim reminder sekali kirim sesuai topik, nomor, dan jadwal yang Anda
tentukan. Isi disusun dari RAG tenant yang sama saat jadwal diproses. Pesan teks
masuk dari nomor yang diizinkan juga dapat dijawab menggunakan knowledge tersebut.
Setiap pertanyaan berdiri sendiri; konteks percakapan lintas pesan, grup, lampiran,
dan penjadwalan berulang belum didukung.

## Pengaturan di website

1. Restart server, login sebagai admin workspace, lalu buka **Asisten WhatsApp**.
2. Buat password tambahan menggunakan password login workspace sebagai verifikasi.
   Password tambahan minimal delapan karakter dan harus berbeda dari password login.
3. Buka pengaturan dengan password tambahan. Akses berlaku 15 menit dan terikat
   pada sesi login browser. API key admin tidak dapat melewati gerbang ini.
4. Isi URL WAHA, nama session, API key, dan nomor yang boleh mengakses knowledge.
   Gunakan format internasional, misalnya `6281234567890`, satu nomor per baris.
5. Pilih model, aktifkan asisten, dan pilih apakah pesan masuk perlu dijawab.
   Simpan, kemudian gunakan **Periksa koneksi tersimpan**. Session harus `WORKING`.
6. Hubungkan nomor pengirim melalui QR di dashboard WAHA. Nomor pengirim ini adalah
   akun asisten; pesan dari akun pengirim sendiri diabaikan untuk mencegah loop.
7. Buka **Hubungkan session dan webhook WAHA**. Salin objek konfigurasi webhook ke
   `config.webhooks` pada session WAHA. Pilih event `message` dan HMAC SHA-512 memakai
   secret yang ditampilkan. Sesuaikan URL agar dapat diakses dari container/server
   WAHA. Pada jaringan Compose yang sama, alamatnya misalnya
   `http://app:8000/hooks/waha/local`; gunakan tenant yang ditampilkan website.

API key tidak dikembalikan oleh endpoint pengaturan. Kolom kosong saat menyimpan
mempertahankan key lama. Password disimpan sebagai hash scrypt. API key dan secret
webhook disimpan di `STORAGE_DIR/workspace.sqlite3`, tanpa enkripsi tingkat aplikasi;
batasi akses file dan backup seperti kredensial `.env`. Detail webhook hanya dapat
dibaca setelah gerbang password dibuka. Mengganti password pengaturan juga memerlukan
password pengaturan lama dan mencabut semua akses tambahan yang masih terbuka.

Untuk produksi, gunakan HTTPS agar cookie login dan pengaturan bekerja dalam mode
non-local. Jangan mengekspos dashboard WAHA atau API key ke pengguna umum.

## Reminder dan pengiriman

Isi pertanyaan/topik knowledge, nomor tujuan, dan waktu kirim sesuai zona waktu
perangkat. Server menyimpannya dalam UTC. Batal hanya tersedia sebelum pekerjaan
mulai diproses. Worker WhatsApp berjalan bersama aplikasi, terpisah dari opsi
scheduler Instagram; aplikasi harus tetap berjalan dan menggunakan satu worker
Uvicorn seperti deployment yang sudah ada.

Reminder tanpa bukti yang cukup dilewati. Untuk pertanyaan masuk yang jawabannya
tidak tersedia, asisten mengirim jawaban fallback RAG. Sumber dokumen disertakan
jika tersedia. Waktu kirim dapat mundur karena antrean, proses model, atau server
yang sedang berhenti. Saat server hidup kembali, jadwal yang terlewat masih diproses.

Riwayat menampilkan 100 pekerjaan terbaru. `Diterima WAHA` berarti API menerima
pesan dan memberikan ID, bukan bukti bahwa penerima sudah membaca atau menerima
pesan di perangkatnya. Respons timeout, koneksi terputus saat mengirim, atau crash
di batas pengiriman ditandai `Belum pasti` dan tidak dikirim ulang otomatis.
Periksa WhatsApp sebelum membuat reminder pengganti. Error penyusunan juga perlu
ditinjau dan dibuat ulang secara manual. Pesan webhook duplikat tidak dibuat ulang.

Menonaktifkan asisten menahan antrean yang belum diproses; menyalakannya kembali
dapat menjalankan jadwal yang sudah lewat. Mengunci halaman atau logout tidak
mematikan asisten. Pesan yang sudah mulai diproses tidak dapat dibatalkan.

## WAHA di Docker (opsional)

Gunakan instance WAHA yang sudah tersedia, atau gabungkan `compose.whatsapp.yml`
dengan stack staging. Salin `docs/waha.env.example` ke `.env.waha`, isi tag image
WAHA yang telah Anda uji, API key acak, dan password dashboard. Jangan menambahkan
variabel WAHA ke `.env` aplikasi lokal: file `.env.waha` terpisah untuk Compose.

```sh
docker compose --env-file .env.staging --env-file .env.waha -f compose.staging.yml -f compose.whatsapp.yml up -d --build
```

Dashboard WAHA tersedia di `http://127.0.0.1:3000`. Untuk koneksi dari aplikasi
container, masukkan `http://waha:3000` pada pengaturan website. Session WAHA
disimpan pada volume `waha_sessions`. Model Ollama dan login staging tetap perlu
disiapkan mengikuti panduan deployment. File Compose tambahan tidak menjalankan
atau memasangkan nomor WhatsApp sampai Anda sendiri melakukan setup.

## Pengujian

```sh
python -m pytest tests/test_whatsapp.py -q
python scripts/check_whatsapp_ui.py
```

Tes browser menjalankan server dengan data terisolasi, RAG fixture, dan WAHA
simulasi. Tidak ada pesan WhatsApp sungguhan yang dikirim. Hasil klik, kontras,
dan screenshot disimpan di `storage/ui_qa_whatsapp_<timestamp>`.

Kontrak API: [pengiriman teks WAHA](https://waha.devlike.pro/docs/how-to/send-messages/)
dan [webhook/HMAC WAHA](https://waha.devlike.pro/docs/how-to/events/).
