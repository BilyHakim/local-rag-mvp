# Profil Saya

Buka **Profil Saya** di bagian bawah sidebar atau `/#account`. Halaman ini
terpisah dari **Profil perusahaan**, yang tetap menyimpan konteks brand.

Data yang dapat diedit: nama tampilan, email kontak opsional, dan bio. Nama
tampilan juga muncul pada header akun. Email kontak tidak diverifikasi dan
bukan pengganti username login. Username dan role hanya ditampilkan untuk dibaca.

Empat pilihan **Fitur yang aktif** mengatur Ruang Chat, Knowledge / RAG, SEO
Specialist, dan Social Media. Klik **Simpan profil & fitur** untuk menerapkan
perubahan. Pengaturan disimpan per akun dan tetap berlaku setelah login ulang.
Tab nonaktif disembunyikan, navigasi langsung diarahkan ke fitur aktif atau
Profil Saya, dan API fitur tersebut menolak request sesi akun dengan HTTP 403.
Semua fitur utama dapat dimatikan; Profil Saya tetap tersedia untuk pemulihan.

Role tetap membatasi akses: reader hanya dapat mengaktifkan Ruang Chat dan RAG.
Pilihan fitur tidak memberi izin admin. Pengaturan tidak menghentikan scheduler
atau kampanye bersama yang sudah aktif; jeda kampanye lewat Content planner
sebelum menonaktifkan Social Media bila publikasi juga ingin dihentikan.

Form **Ganti password** meminta password saat ini, password baru minimal delapan
karakter, dan konfirmasi. Password tetap disimpan sebagai hash scrypt. Perubahan
mengeluarkan sesi lain; sesi yang melakukan perubahan tetap aktif. Percobaan
perubahan password dibatasi sepuluh per menit per akun pada satu proses server.

Penyuntingan profil/password memerlukan sesi login browser yang sah. API key
dan mode lokal tanpa autentikasi hanya mendapat informasi profil dasar read-only;
key tetap menggunakan izin server yang sudah dikonfigurasi. Preferensi pribadi
tidak mengubah otorisasi API key atau pekerjaan scheduler.

Penyimpanan: tabel `account_profiles` dibuat otomatis di `auth.sqlite3`, dengan
revision untuk mencegah perubahan usang menimpa data terbaru. Tabel akun/sesi
yang sudah ada tetap dipakai. Tidak ada perubahan username atau perpindahan
riwayat percakapan.

API: `GET/PUT /api/account/profile` dan `POST /api/account/password`.
PUT menerima `revision`, `display_name`, `email`, `bio`, dan `enabled_features`.
POST password menerima `current_password` dan `new_password`. Username, role,
tenant, fitur tak dikenal, dan field tambahan ditolak. Request browser mutasi
tetap wajib memakai proteksi CSRF workspace.

Restart backend untuk memuat endpoint baru, lalu tekan Ctrl+F5 agar aset tampilan
terbaru terbaca. Semua fitur yang tersedia untuk role aktif secara default bagi
akun yang belum menyimpan preferensi.
