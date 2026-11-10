# Pemeriksaan carousel, 10 November 2026

Lingkup: Social Media Specialist, upload manual, draft AI, kampanye manual/otomatis,
preview, urutan gambar, publishing Instagram dan WordPress. Mode anti-slop during
dipilih pengguna. Arah visual mengikuti DESIGN.md, ENERGY 2 / RHYTHM 2 / MOTION 1.

## Bukti verifikasi

- `python -m pytest -q`: **175 passed, 3 skipped**. Kasus baru memeriksa upload
  beberapa file, preview per indeks, konflik versi, perubahan urutan, kegagalan
  upload/generasi yang mempertahankan data sebelumnya, jumlah brief AI, konteks
  revisi, kampanye menunggu gambar lengkap, urutan child container Instagram,
  kegagalan child yang mencegah publish, serta seluruh gambar WordPress.
- `node --check app/static/workspace.js` dan `git diff --check`: lulus.
- `python scripts/check_workspace_ui.py --url http://127.0.0.1:8013 --output
  storage/ui_qa_carousel`: **PASS**, 74 kondisi tampilan, 20 kelompok interaksi.
  API fixture dan gambar uji dipakai, seluruh request eksternal diblokir.
- Laporan terperinci: `storage/ui_qa_carousel/report.json`. Screenshot carousel
  diperiksa pada 360px dark dan 1440px light; ruang preview tunggal kosong pada
  carousel sudah dihilangkan lalu pemeriksaan diulang.

## Delivery gate

- Hard Gate PASS: kontrol baru memakai label/native input/button, gambar berdimensi
  dan ber-alt, tidak menambah navigasi/aset/klaim pemasaran; pemeriksaan browser
  mencakup error, disabled states, keyboard ordering, fokus sesudah perubahan urutan,
  kontras teks dan overflow pada 360/768/1024/1440px dalam kedua tema.
- Purpose-Gate PASS: tidak menambah efek dekoratif, ikon, font, atau animasi;
  grid bernomor menunjukkan urutan publikasi dan tombol teks menyediakan alternatif
  keyboard untuk drag. Alasan visual tercatat di DESIGN.md.
- Liveliness PASS: dials tetap 2/2/1; panel brief dan materi, aksen cream untuk
  tindakan utama, tipografi studio, serta jarak antarkelompok tetap mengikuti
  arah proyek; screenshot menunjukkan slide membungkus dan menumpuk di ponsel.
- Craftsmanship & Quality Locks PASS: click-through mencakup upload tunggal dan
  multi, dua arah pemindahan, brief per slide, generate, revisi, simpan, persetujuan,
  jadwal, pembatalan, rekonsiliasi dan kampanye. 74 pemeriksaan layout/kontras serta
  tes backend mendukung perilaku yang dilaporkan; tidak ada error console tak terduga.

## Batas pemeriksaan

Tidak menjalankan provider gambar berbayar atau menerbitkan ke akun Instagram/
WordPress nyata. Interaksi provider dan platform diuji memakai HTTP mocks.
Ketepatan tulisan dan konsistensi visual infografis perlu ditinjau pada hasil
provider yang digunakan. Mode otomatis tetap memerlukan konfigurasi provider
gambar, scheduler, koneksi kanal, dan URL media publik yang sudah berlaku.
