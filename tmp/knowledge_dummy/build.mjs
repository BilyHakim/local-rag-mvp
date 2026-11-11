import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-973-0_26.1110.973.0_x64__3k8sg7r9htsxt/dependencies/node/package.json');
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);

const workbook = Workbook.create();
const sheet = workbook.worksheets.add('Stok cabang');
const rows = [
  ['cabang', 'penanggung_jawab', 'sku', 'nama_produk', 'stok_unit', 'tanggal_snapshot', 'catatan_data'],
  ['Bandung', 'Nadia Putri', 'KR-101', 'Kursi Aruna', 12, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Jakarta', 'Bima Saputra', 'KR-101', 'Kursi Aruna', 5, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Surabaya', 'Rani Wicaksana', 'KR-101', 'Kursi Aruna', 0, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Bandung', 'Nadia Putri', 'MJ-202', 'Meja Nara', 6, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Jakarta', 'Bima Saputra', 'MJ-202', 'Meja Nara', 3, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Surabaya', 'Rani Wicaksana', 'MJ-202', 'Meja Nara', 4, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Bandung', 'Nadia Putri', 'LP-303', 'Lampu Sora', 18, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Jakarta', 'Bima Saputra', 'LP-303', 'Lampu Sora', 9, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Surabaya', 'Rani Wicaksana', 'LP-303', 'Lampu Sora', 7, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Bandung', 'Nadia Putri', 'BT-404', 'Botol Reka', 20, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Jakarta', 'Bima Saputra', 'BT-404', 'Botol Reka', 15, '2026-11-10', 'Fiktif untuk uji RAG'],
  ['Surabaya', 'Rani Wicaksana', 'BT-404', 'Botol Reka', 10, '2026-11-10', 'Fiktif untuk uji RAG'],
];
sheet.getRange('A1:G13').values = rows;
sheet.getRange('A1:G13').format.font.name = 'Calibri';
sheet.getRange('A1:G13').format.font.size = 11;
sheet.getRange('A1:G13').format.rowHeight = 27;
sheet.getRange('A1:G13').format.columnWidth = 21;
sheet.getRange('B1:B13').format.columnWidth = 24;
sheet.getRange('G1:G13').format.columnWidth = 26;
sheet.getRange('A1:G1').format.fill = '#164E63';
sheet.getRange('A1:G1').format.font.color = '#FFFFFF';
sheet.getRange('A1:G1').format.font.bold = true;
sheet.getRange('A1:G13').format.borders = { preset: 'all', style: 'thin', color: '#D9D9D9' };
sheet.getRange('E2:E13').setNumberFormat('0');
sheet.freezePanes.freezeRows(1);
await workbook.recalculate();
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save('output/knowledge-dummy-lentera/knowledge/cabang/stok_cabang.xlsx');
const preview = await workbook.render({ sheetName: 'Stok cabang', range: 'A1:G13', scale: 1.3, format: 'png' });
await fs.writeFile('tmp/knowledge_dummy/stok.png', new Uint8Array(await preview.arrayBuffer()));
console.log((await workbook.inspect({ kind: 'sheet', range: 'A1:G4', maxChars: 1000 })).ndjson);
