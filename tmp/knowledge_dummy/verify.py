from pathlib import Path
import csv
import json
import zipfile
import fitz
from app.services.pdf_service import extract_pdf_pages
from app.services.docx_service import extract_docx_pages
from app.services.spreadsheet_service import extract_spreadsheet_pages

root = Path('output/knowledge-dummy-lentera')
knowledge = root / 'knowledge'
extra = knowledge / 'cabang/stok_cabang.xlsx.inspect.ndjson'
extra.unlink(missing_ok=True)
files = sorted(file for file in knowledge.rglob('*') if file.is_file())
assert len(files) == 6
texts = {}
for file in files:
    suffix = file.suffix.lower()
    if suffix == '.pdf':
        pages = extract_pdf_pages(file)
    elif suffix == '.docx':
        pages = extract_docx_pages(file)
    else:
        pages = extract_spreadsheet_pages(file, suffix)
    text = '\n'.join(page['text'] for page in pages)
    assert text.strip(), file
    texts[file.name] = text
    print(json.dumps({'file': str(file.relative_to(root)), 'records': len(pages), 'characters': len(text)}))
assert 'LENTERA-7429' in texts['profil_lentera.pdf']
assert '24 bulan' in texts['retur_dan_garansi.docx']
assert 'Rani Wicaksana' in texts['stok_cabang.xlsx']
assert 'ORD-006' in texts['pesanan_november_2026.csv']
with (knowledge / 'penjualan/pesanan_november_2026.csv').open(encoding='utf-8-sig') as stream:
    orders = list(csv.DictReader(stream))
assert sum(int(r['jumlah']) * int(r['harga_satuan_idr']) for r in orders if r['status'] == 'selesai') == 4750000
for pdf in [knowledge / 'perusahaan/profil_lentera.pdf', knowledge / 'operasional/pengiriman.pdf', Path('tmp/knowledge_dummy/retur_preview.pdf')]:
    with fitz.open(pdf) as document:
        for index, page in enumerate(document):
            page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(f'tmp/knowledge_dummy/{pdf.stem}-{index + 1}.png')
            assert page.get_text().strip()
archive = root.parent / 'knowledge-dummy-lentera.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for file in sorted(root.rglob('*')):
        if file.is_file():
            bundle.write(file, file.relative_to(root.parent))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    assert len(bundle.namelist()) == 9
print(f'PASS extraction, arithmetic, and ZIP integrity. Archive {archive.stat().st_size} bytes')
