from pathlib import Path
import csv
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

root = Path('output/knowledge-dummy-lentera')
knowledge = root / 'knowledge'
for folder in ['perusahaan', 'operasional', 'produk', 'penjualan', 'cabang']:
    (knowledge / folder).mkdir(parents=True, exist_ok=True)

def pdf(relative, title, sections):
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 11
    styles['BodyText'].leading = 16
    story = [Paragraph(title, styles['Title']), Paragraph('DATA FIKTIF UNTUK PENGUJIAN RAG', styles['BodyText']), Spacer(1, 16)]
    for heading, text in sections:
        story += [Paragraph(heading, styles['Heading2']), Paragraph(text, styles['BodyText']), Spacer(1, 10)]
    SimpleDocTemplate(str(knowledge / relative), rightMargin=48, leftMargin=48, topMargin=42, bottomMargin=42).build(story)

pdf('perusahaan/profil_lentera.pdf', 'Profil Lentera Office', [
    ('Identitas perusahaan', 'Lentera Office adalah perusahaan fiktif penyedia perlengkapan kerja. Didirikan pada 14 Februari 2021 oleh Mira Santosa. Kantor pusat berada di Bandung. Kode verifikasi knowledge perusahaan adalah LENTERA-7429.'),
    ('Layanan pelanggan', 'Email dukungan adalah bantuan@lentera.example. Layanan pelanggan tersedia Senin sampai Jumat pukul 09.00 sampai 17.00 WIB. Penanggung jawab layanan pelanggan adalah Dimas Prakoso.'),
    ('Program keanggotaan', 'Program anggota bernama Teman Lentera. Pembelian memperoleh 1 poin per Rp10.000 nilai produk setelah diskon. Ongkir tidak menghasilkan poin. Sebanyak 100 poin dapat ditukar dengan voucher Rp25.000. Poin berlaku 12 bulan sejak diperoleh.'),
    ('Cakupan data', 'Seluruh identitas, produk, kebijakan, angka, dan transaksi dalam paket ini merupakan data sintetis. Paket tidak memuat nomor rekening perusahaan atau laporan laba bersih tahunan.')])

pdf('operasional/pengiriman.pdf', 'Ketentuan Pengiriman Lentera Office', [
    ('Masa berlaku', 'Ketentuan pengiriman fiktif ini berlaku mulai 1 November 2026. Hari kerja adalah Senin sampai Jumat, kecuali hari libur nasional. Estimasi dihitung sejak paket diserahkan kepada kurir.'),
    ('Biaya dan estimasi', 'Bandung dikenakan ongkir Rp15.000 dengan estimasi 1 sampai 2 hari kerja. Jakarta dikenakan ongkir Rp25.000 dengan estimasi 2 sampai 3 hari kerja. Surabaya dikenakan ongkir Rp35.000 dengan estimasi 3 sampai 5 hari kerja.'),
    ('Gratis ongkir', 'Gratis ongkir hanya berlaku untuk tujuan Bandung jika subtotal produk setelah diskon minimal Rp500.000. Tujuan Jakarta dan Surabaya tetap dikenakan ongkir sesuai tarif meskipun subtotal melampaui Rp500.000.'),
    ('Batas pemrosesan', 'Pesanan dengan pembayaran terkonfirmasi sebelum pukul 14.00 WIB pada hari kerja diproses pada hari yang sama. Pembayaran pukul 14.00 WIB atau sesudahnya diproses pada hari kerja berikutnya. Pengambilan langsung tersedia hanya di cabang Bandung dengan janji temu.')])

document = Document()
section = document.sections[0]
section.top_margin = section.bottom_margin = Inches(0.75)
normal = document.styles['Normal']
normal.font.name = 'Calibri'
normal.font.size = Pt(11)
for style in ['Title', 'Heading 1', 'Heading 2']:
    document.styles[style].font.color.rgb = RGBColor(0, 0, 0)
for style in document.styles:
    for border in list(style.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
document.add_heading('Kebijakan Retur dan Garansi Lentera Office', 0)
document.add_paragraph('Data fiktif untuk pengujian RAG. Kebijakan berlaku mulai 1 November 2026 dan mengatur retur, garansi, serta pengecualian produk.')
for heading, text in [
    ('Pengajuan retur', 'Retur barang cacat saat diterima dapat diajukan maksimal 7 hari kalender sejak barang diterima. Pelanggan harus menyertakan nomor pesanan, foto kerusakan, dan video pembukaan paket. Pengajuan dikirim ke bantuan@lentera.example.'),
    ('Biaya dan pengembalian dana', 'Jika cacat dikonfirmasi oleh tim Lentera Office, ongkir retur ditanggung perusahaan. Pengembalian dana diproses maksimal 5 hari kerja setelah barang retur diterima dan lolos pemeriksaan. Pembelian karena berubah pikiran tidak dapat diretur.'),
    ('Garansi per produk', 'Kursi Aruna memiliki garansi rangka 24 bulan. Meja Nara memiliki garansi struktur 12 bulan. Lampu Sora memiliki garansi elektronik 6 bulan. Botol Reka tidak memiliki garansi penggunaan, tetapi cacat saat diterima tetap dapat diajukan melalui retur 7 hari.'),
    ('Pengecualian', 'Garansi tidak mencakup kerusakan akibat cairan, modifikasi, atau penggunaan di luar petunjuk. Produk berukir khusus tidak dapat diretur karena berubah pikiran. Produk berukir khusus yang cacat saat diterima tetap mengikuti prosedur retur barang cacat.')]:
    document.add_heading(heading, 1)
    document.add_paragraph(text)
document.save(knowledge / 'operasional/retur_dan_garansi.docx')

def write_csv(relative, rows):
    with (knowledge / relative).open('w', encoding='utf-8-sig', newline='') as stream:
        csv.writer(stream).writerows(rows)

write_csv('produk/katalog.csv', [
    ['sku', 'nama_produk', 'harga_idr', 'kategori', 'catatan_data'],
    ['KR-101', 'Kursi Aruna', 1250000, 'Kursi kerja', 'Fiktif untuk uji RAG'],
    ['MJ-202', 'Meja Nara', 1800000, 'Meja kerja', 'Fiktif untuk uji RAG'],
    ['LP-303', 'Lampu Sora', 275000, 'Lampu meja', 'Fiktif untuk uji RAG'],
    ['BT-404', 'Botol Reka', 120000, 'Botol minum', 'Fiktif untuk uji RAG']])
write_csv('penjualan/pesanan_november_2026.csv', [
    ['nomor_pesanan', 'tanggal', 'sku', 'nama_produk', 'jumlah', 'harga_satuan_idr', 'kota_tujuan', 'status', 'catatan_data'],
    ['ORD-001', '2026-11-02', 'KR-101', 'Kursi Aruna', 2, 1250000, 'Bandung', 'selesai', 'Fiktif; nilai produk sebelum ongkir'],
    ['ORD-002', '2026-11-03', 'LP-303', 'Lampu Sora', 4, 275000, 'Jakarta', 'selesai', 'Fiktif; nilai produk sebelum ongkir'],
    ['ORD-003', '2026-11-04', 'MJ-202', 'Meja Nara', 1, 1800000, 'Surabaya', 'diproses', 'Fiktif; nilai produk sebelum ongkir'],
    ['ORD-004', '2026-11-05', 'BT-404', 'Botol Reka', 5, 120000, 'Bandung', 'selesai', 'Fiktif; nilai produk sebelum ongkir'],
    ['ORD-005', '2026-11-06', 'KR-101', 'Kursi Aruna', 1, 1250000, 'Jakarta', 'dibatalkan', 'Fiktif; nilai produk sebelum ongkir'],
    ['ORD-006', '2026-11-09', 'LP-303', 'Lampu Sora', 2, 275000, 'Bandung', 'selesai', 'Fiktif; nilai produk sebelum ongkir']])

questions = [
    ('Apa kode verifikasi knowledge Lentera Office?', 'LENTERA-7429.', 'perusahaan/profil_lentera.pdf'),
    ('Berapa lama garansi elektronik Lampu Sora?', '6 bulan.', 'operasional/retur_dan_garansi.docx'),
    ('Pesanan mana yang dibatalkan dan apa produknya?', 'ORD-005, 1 Kursi Aruna.', 'penjualan/pesanan_november_2026.csv'),
    ('Berapa harga Meja Nara dan apa SKU-nya?', 'Rp1.800.000, MJ-202.', 'produk/katalog.csv'),
    ('Siapa pendiri Lentera Office dan kapan perusahaan didirikan?', 'Mira Santosa, 14 Februari 2021.', 'perusahaan/profil_lentera.pdf'),
    ('Cabang mana yang punya stok Kursi Aruna paling banyak?', 'Bandung, 12 unit. Jakarta 5 unit dan Surabaya 0 unit.', 'cabang/stok_cabang.xlsx'),
    ('Kalau membeli 2 Lampu Sora ke Bandung tanpa diskon, berapa total bayar termasuk ongkir?', 'Rp550.000. Subtotal 2 x Rp275.000 memenuhi gratis ongkir Bandung.', 'produk/katalog.csv + operasional/pengiriman.pdf'),
    ('Apakah belanja Rp600.000 ke Jakarta mendapatkan gratis ongkir?', 'Tetap dikenakan Rp25.000. Gratis ongkir hanya untuk Bandung dengan subtotal setelah diskon minimal Rp500.000.', 'operasional/pengiriman.pdf'),
    ('Apa saja bukti yang harus saya siapkan untuk retur barang cacat?', 'Nomor pesanan, foto kerusakan, dan video pembukaan paket.', 'operasional/retur_dan_garansi.docx'),
    ('Berapa nilai produk seluruh pesanan berstatus selesai dalam data November?', 'Rp4.750.000 dari ORD-001 Rp2.500.000, ORD-002 Rp1.100.000, ORD-004 Rp600.000, ORD-006 Rp550.000. Ongkir dikecualikan.', 'penjualan/pesanan_november_2026.csv'),
    ('Siapa penanggung jawab cabang Surabaya dan berapa stok Meja Nara di sana?', 'Rani Wicaksana, stok 4 unit.', 'cabang/stok_cabang.xlsx'),
    ('Kalau berubah pikiran setelah membeli Botol Reka, apakah bisa retur?', 'Tidak. Retur tersedia untuk cacat saat diterima dengan syarat kebijakan.', 'operasional/retur_dan_garansi.docx'),
    ('Pesanan dibayar tepat pukul 14.00 WIB pada hari kerja. Kapan diproses?', 'Hari kerja berikutnya.', 'operasional/pengiriman.pdf'),
    ('Berapa poin untuk membeli 2 Kursi Aruna tanpa diskon dan ongkir?', '250 poin dari subtotal Rp2.500.000 dibagi Rp10.000.', 'produk/katalog.csv + perusahaan/profil_lentera.pdf'),
    ('Apakah produk berukir khusus yang cacat saat diterima masih bisa diretur?', 'Bisa, mengikuti prosedur retur barang cacat maksimal 7 hari kalender dengan bukti yang diwajibkan.', 'operasional/retur_dan_garansi.docx'),
    ('Berapa jumlah total stok Botol Reka di semua cabang?', '45 unit, yaitu Bandung 20, Jakarta 15, dan Surabaya 10.', 'cabang/stok_cabang.xlsx'),
    ('Ke mana saya mengirim pengajuan retur dan siapa penanggung jawab layanan pelanggan?', 'bantuan@lentera.example. Penanggung jawab layanan pelanggan Dimas Prakoso.', 'operasional/retur_dan_garansi.docx + perusahaan/profil_lentera.pdf'),
    ('Berapa nilai produk ORD-003 dan estimasi pengirimannya?', 'Rp1.800.000. Tujuan Surabaya memiliki estimasi 3 sampai 5 hari kerja sejak diserahkan ke kurir. Status pesanan diproses.', 'penjualan/pesanan_november_2026.csv + operasional/pengiriman.pdf'),
    ('Berapa nomor rekening Lentera Office untuk pembayaran?', 'Informasi nomor rekening tidak tersedia dalam knowledge.', 'perusahaan/profil_lentera.pdf'),
    ('Berapa laba bersih Lentera Office tahun 2025?', 'Informasi laba bersih tahunan tidak tersedia dalam knowledge.', 'perusahaan/profil_lentera.pdf')]

(root / 'PERTANYAAN.md').write_text('# Pertanyaan uji RAG Lentera Office\n\nUnggah hanya folder `knowledge`. Ajukan pertanyaan berikut di tab Knowledge / RAG. Tambahkan permintaan menyebutkan sumber. Pertanyaan perhitungan dan lintas file menguji retrieval beberapa potongan sekaligus.\n\n' + '\n'.join(f'{i}. {q}' for i, (q, _, _) in enumerate(questions, 1)) + '\n', encoding='utf-8')
(root / 'KUNCI_JAWABAN.md').write_text('# Kunci jawaban uji RAG\n\nGunakan untuk membandingkan hasil. Semua data adalah fiktif.\n\n' + '\n\n'.join(f'## {i} {q}\n\n{a}\n\nSumber `{s}`.' for i, (q, a, s) in enumerate(questions, 1)) + '\n', encoding='utf-8')
(root / 'PETUNJUK.md').write_text('# Paket knowledge dummy Lentera Office\n\nSemua data dalam paket ini fiktif dan dibuat khusus untuk pengujian.\n\n1. Ekstrak ZIP jika menggunakan arsip.\n2. Buka Knowledge Base dan pilih folder `knowledge` melalui fitur unggah folder.\n3. Folder berisi 6 file dalam 4 format, yaitu PDF, DOCX, XLSX, dan CSV. Semua file seharusnya lolos pemindaian format.\n4. Jalankan unggah dan tunggu hingga 100%. Periksa ringkasan untuk memastikan 6 file sukses pada unggahan pertama ke knowledge yang masih bersih.\n5. Buka tab Knowledge / RAG dan gunakan PERTANYAAN.md. Bandingkan dengan KUNCI_JAWABAN.md.\n6. Unggah folder yang sama lagi untuk mengecek deteksi duplikat.\n\nPilih folder `knowledge` agar petunjuk, pertanyaan, dan kunci jawaban tetap di luar bahan retrieval. PDF berisi teks yang dapat diekstrak. Paket ini menguji ekstraksi dokumen biasa, subfolder, tabel spreadsheet, dan hubungan antarfile.\n\nPertanyaan 19 dan 20 menguji respons ketika informasi tidak tersedia. Pertanyaan agregasi dapat memerlukan beberapa potongan retrieval. Jawaban yang tidak lengkap perlu ditelusuri melalui sumber yang dikembalikan RAG.\n', encoding='utf-8')
print(json.dumps({'root': str(root), 'questions': len(questions), 'files_before_xlsx': len(list(knowledge.rglob('*.*')))}))
