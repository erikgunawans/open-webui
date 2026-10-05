const { JupUIProvider, ToastProvider, useToast, Button, IconButton, Card, Badge, Alert, Dialog, Tabs, Checkbox: DSCheckbox } = window.JupUI;
const ND = window.NOTULEN_DATA;
const STORE = 'jup-notulen-rapat-direksi-v1';

const AGENDAS = [
  { eyebrow: 'Informasi rapat', nav: 'Informasi Rapat', title: 'Informasi & Ringkasan Rapat', focus: 'Informasi rapat, peserta, dokumen, ringkasan eksekutif, serta penutupan dan validasi notulen.' },
  { eyebrow: 'Agenda 01', nav: '1. Strategic Update', title: '1. Strategic Update', focus: 'Perkembangan target dan strategi perusahaan.', unit: 'satu baris untuk setiap sasaran strategis' },
  { eyebrow: 'Agenda 02', nav: '2. Kinerja Perusahaan', title: '2. Kinerja Perusahaan', focus: 'Revenue, EBITDA/laba, cash flow, CAPEX–OPEX, dan KPI.', unit: 'satu baris untuk setiap indikator' },
  { eyebrow: 'Agenda 03', nav: '3. Isu Lintas Direktorat', title: '3. Isu Lintas Direktorat / Divisi', focus: 'Masalah yang membutuhkan keputusan bersama.', unit: 'satu baris untuk setiap isu' },
  { eyebrow: 'Agenda 04', nav: '4. Program Prioritas', title: '4. Program Prioritas', focus: 'Proyek strategis, investasi, business development, dan transformasi.', unit: 'satu baris untuk setiap program / proyek' },
  { eyebrow: 'Agenda 05', nav: '5. Risk & Compliance', title: '5. Risk & Compliance', focus: 'Risiko utama dan mitigasinya.', unit: 'satu baris untuk setiap risiko / isu kepatuhan' },
  { eyebrow: 'Agenda 06', nav: '6. Stakeholder Issues', title: '6. Stakeholder Issues', focus: 'Pemegang Saham, regulator, pemerintah, mitra, dan pelanggan.', unit: 'satu baris untuk setiap stakeholder / isu' },
  { eyebrow: 'Agenda 07', nav: '7. Decision Making', title: '7. Decision Making', focus: 'Keputusan yang harus disepakati Direksi.', unit: 'satu baris untuk setiap usulan / keputusan' },
  { eyebrow: 'Agenda 08', nav: '8. Action Plan', title: '8. Action Plan', focus: 'PIC, target waktu, dan indikator penyelesaian.', unit: 'satu baris untuk setiap tindakan / deliverable' },
];
const INFO_GROUPS = [
  ['Informasi rapat', ['Tanggal & waktu', 'Ruang / lokasi', 'Tautan meeting', 'Periode pelaporan']],
  ['Peserta', ['Pimpinan rapat', 'Peserta', 'Peserta berhalangan', 'Peserta eksternal & jabatan', 'Notulis']],
  ['Dokumen', ['Dokumen pendukung', 'Tautan bahan rapat', 'Klasifikasi dokumen']],
  ['Ringkasan eksekutif', ['Kondisi perusahaan', 'Pencapaian & deviasi utama', 'Isu perhatian Direksi', 'Ringkasan keputusan utama', 'Tindak lanjut mendesak']],
  ['Penutupan & validasi', ['Topik rapat berikutnya', 'Rapat berikutnya', 'Waktu rapat ditutup', 'Disusun oleh', 'Tanggal penyusunan', 'Diperiksa / disetujui oleh', 'Tanggal validasi', 'Status validasi']],
  ['Checklist finalisasi', ['Delapan agenda dicatat', 'Keputusan jelas', 'PIC & tenggat lengkap', 'Basis angka lengkap', 'Bukti ditautkan', 'Siap didistribusikan']],
];
const CHECKLIST = INFO_GROUPS[5][1];
const SUMMARY_KEYS = ['Status validasi', 'Status', 'Status keputusan', 'Status progres', 'Status mitigasi', 'Tingkat risiko', 'Urgensi', 'Evaluasi strategi', 'Basis pelaporan', 'Kategori', 'Jenis stakeholder'];
const TONE = { 'Selesai': 'success', 'Disetujui': 'success', 'On track': 'success', 'Dilanjutkan': 'success', 'Berjalan': 'info', 'Dalam review': 'info', 'Disesuaikan': 'info', 'Disetujui bersyarat': 'warning', 'At risk': 'warning', 'Sedang': 'warning', 'Ditunda': 'warning', 'Perlu evaluasi': 'warning', 'Belum diputuskan': 'warning', 'Terhambat': 'danger', 'Delayed': 'danger', 'Ditolak': 'danger', 'Perlu revisi': 'danger', 'Tinggi': 'danger', 'Mendesak': 'danger', 'Dihentikan': 'danger', 'Draft': 'neutral', 'Belum mulai': 'neutral', 'Rendah': 'neutral' };

const uid = () => Math.random().toString(36).slice(2, 10);
const rec = (values = {}, body = '', origin = 'Record kosong dari sumber') => ({ id: uid(), values, body, time: {}, origin });
function initialState() {
  const s = ND.schema;
  const empty = (i) => [rec({}, '', 'Formulir kosong — belum ada record di sumber')];
  return [
    [rec(), rec({ 'Nama rapat': 'Isi nama rapat', 'Status validasi': 'Draft' }, ND.info2body, 'Record sumber')],
    [rec()],
    [...['Revenue', 'EBITDA', 'Laba bersih', 'Arus kas operasi', 'Saldo kas akhir', 'CAPEX', 'OPEX', 'KPI utama — isi nama KPI'].map((n) => rec({ Indikator: n }, '', 'Indikator awal')), rec()],
    empty(3), empty(4), empty(5), empty(6), empty(7), empty(8),
  ];
}
function loadState() {
  try { const el = document.getElementById('saved-state'); if (el && el.textContent.trim()) return JSON.parse(el.textContent); } catch (e) {}
  try { const ls = localStorage.getItem(STORE); if (ls) return JSON.parse(ls); } catch (e) {}
  return initialState();
}
const titleField = (i) => ND.schema[i].fields.find((f) => f.type === 'title');
const fmtDate = (d) => {
  if (!d || !d.start) return '';
  const f = (x) => { const dt = new Date(x.length === 10 ? x + 'T00:00' : x); return dt.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }) + (x.length > 10 ? ' ' + x.slice(11, 16) : ''); };
  return f(d.start) + (d.end ? ' – ' + f(d.end) : '');
};
const filled = (v) => v !== undefined && v !== null && v !== '' && v !== false && !(Array.isArray(v) && !v.length) && !(typeof v === 'object' && !Array.isArray(v) && !v.start && !v.end);

function RecordCard({ ai, r, idx, total, open, onToggle, onChange, onDelete, t }) {
  const fields = ND.schema[ai].fields;
  const tf = titleField(ai);
  const title = r.values[tf.name];
  const set = (name, v) => onChange({ ...r, values: { ...r.values, [name]: v } });
  const setTime = (name, on) => onChange({ ...r, time: { ...r.time, [name]: on } });
  const pf = (f) => <PropField key={f.name} f={f} value={r.values[f.name]} timeOn={r.time[f.name]} showType={t.showTypes} onChange={(v) => set(f.name, v)} onTime={(on) => setTime(f.name, on)}></PropField>;
  const nFilled = fields.filter((f) => filled(r.values[f.name])).length;
  const badges = SUMMARY_KEYS.filter((k) => r.values[k]).map((k) => <Badge key={k} tone={TONE[r.values[k]] || 'neutral'} dot>{r.values[k]}</Badge>);
  let groups;
  if (ai === 0) groups = INFO_GROUPS.map(([g, names]) => [g, names.map((n) => fields.find((f) => f.name === n))]);
  else {
    const rest = fields.filter((f) => f.type !== 'title');
    groups = [['Properti', rest.filter((f) => !['rich_text', 'files'].includes(f.type))], ['Uraian, pembahasan & arahan', rest.filter((f) => ['rich_text', 'files'].includes(f.type))]];
  }
  return (
    <Card className={'nt-rec' + (open ? ' is-open' : '')} padding="md"
      title={<button type="button" className="nt-rec__toggle" aria-expanded={open} onClick={onToggle}><span className="nt-rec__chev"><Icon name="chevron"></Icon></span><span className="nt-rec__title">{title || <span className="nt-muted">Tanpa judul</span>}</span></button>}
      description={<span className="nt-rec__meta"><span className="nt-mono">{String(idx + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</span><span>{r.origin}</span><span className="nt-mono">{nFilled}/{fields.length} terisi</span>{badges}</span>}
      actions={<IconButton label="Hapus record" size="sm" onClick={onDelete}><Icon name="trash"></Icon></IconButton>}>
      {open ? (
        <div className="nt-rec__body">
          <div className="nt-titlefield">{pf(tf)}</div>
          {groups.map(([g, fs]) => fs.length ? (
            <section key={g} className="nt-group">
              <h4 className="nt-group__h">{g}{g === 'Checklist finalisasi' ? <span className="nt-mono"> · {fs.filter((f) => r.values[f.name]).length}/{fs.length}</span> : null}</h4>
              <div className={'nt-grid ' + (g === 'Checklist finalisasi' ? 'nt-grid--checks' : fs.every((f) => ['rich_text', 'files'].includes(f.type)) ? 'nt-grid--long' : 'nt-grid--short')}>{fs.filter((f) => ai !== 0 || f.type !== 'title').map(pf)}</div>
            </section>) : null)}
          <section className="nt-group">
            <h4 className="nt-group__h">Isi halaman / catatan panjang</h4>
            <window.JupUI.Textarea rows={3} autoResize maxRows={20} value={r.body} placeholder="Catatan panjang untuk record ini…" aria-label="Isi halaman / catatan panjang" onChange={(e) => onChange({ ...r, body: e.target.value })}></window.JupUI.Textarea>
          </section>
        </div>
      ) : null}
    </Card>
  );
}

function AgendaView({ ai, records, setRecords, t, printing }) {
  const { toast } = useToast();
  const a = AGENDAS[ai];
  const [openIds, setOpen] = React.useState(() => new Set(records.length <= 2 || t.expand === 'semua' ? records.map((r) => r.id) : [records[0]?.id]));
  const [del, setDel] = React.useState(null);
  const add = () => {
    const r = rec({}, '', 'Record baru');
    setRecords([...records, r]); setOpen(new Set([...openIds, r.id]));
    toast({ title: 'Record ditambahkan', description: a.nav, tone: 'success' });
  };
  const allOpen = records.every((r) => openIds.has(r.id));
  return (
    <section className="nt-agenda" data-screen-label={a.nav}>
      <header className="nt-ahead">
        <div className="nt-eyebrow">{a.eyebrow}</div>
        <h2 className="nt-h2">{a.title}</h2>
        <p className="nt-focus"><strong>Fokus:</strong> {a.focus}{a.unit ? <span> — {a.unit}.</span> : null}</p>
        <div className="nt-ahead__row">
          <span className="nt-mono nt-muted">{ND.schema[ai].fields.length} properti · {records.length} record</span>
          <div className="nt-actions">
            {records.length > 1 ? <Button variant="ghost" size="sm" onClick={() => setOpen(allOpen ? new Set() : new Set(records.map((r) => r.id)))}>{allOpen ? 'Tutup semua' : 'Buka semua'}</Button> : null}
            <Button variant="secondary" size="sm" iconLeft={<Icon name="plus"></Icon>} onClick={add}>Tambah record</Button>
          </div>
        </div>
      </header>
      {ai === 2 ? <Alert tone="info" title="Catatan angka">Deviasi dan progres diisi manual, bukan dihitung otomatis. Masukkan angka persen langsung: 10 berarti 10%.</Alert> : null}
      <div className="nt-records">
        {records.map((r, i) => <RecordCard key={r.id} ai={ai} r={r} idx={i} total={records.length} t={t} open={printing || openIds.has(r.id)}
          onToggle={() => { const n = new Set(openIds); n.has(r.id) ? n.delete(r.id) : n.add(r.id); setOpen(n); }}
          onChange={(nr) => setRecords(records.map((x) => x.id === r.id ? nr : x))}
          onDelete={() => setDel(r)}></RecordCard>)}
        {!records.length ? <div className="nt-empty">Belum ada record. Gunakan <strong>Tambah record</strong>.</div> : null}
      </div>
      <Dialog open={!!del} onClose={() => setDel(null)} title="Hapus record?" description={del ? (del.values[titleField(ai).name] || 'Record tanpa judul') + ' akan dihapus dari ' + a.nav + '.' : ''}
        footer={<><Button variant="ghost" onClick={() => setDel(null)}>Batal</Button><Button variant="danger" onClick={() => { setRecords(records.filter((x) => x.id !== del.id)); setDel(null); toast({ title: 'Record dihapus', tone: 'neutral' }); }}>Hapus</Button></>}></Dialog>
    </section>
  );
}

function ViewsPanel({ state }) {
  const v = (r, k) => r.values[k];
  const pending = state[7].filter((r) => v(r, 'Topik keputusan') && ['', undefined, 'Belum diputuskan', 'Ditunda'].includes(v(r, 'Status keputusan')));
  const risks = state[5].filter((r) => v(r, 'Tingkat risiko') === 'Tinggi');
  const acts = state[8].filter((r) => v(r, 'Tindakan / deliverable'));
  const cal = acts.filter((r) => v(r, 'Target waktu')?.start).sort((a, b) => v(a, 'Target waktu').start.localeCompare(v(b, 'Target waktu').start));
  const Empty = () => <p className="nt-empty">Belum ada record yang sesuai.</p>;
  const Row = ({ title, meta, badge }) => <li className="nt-vrow"><div className="nt-vrow__t">{title}</div><div className="nt-vrow__m">{meta.filter(Boolean).join(' · ') || '—'}</div>{badge ? <Badge tone={TONE[badge] || 'neutral'} size="sm">{badge}</Badge> : null}</li>;
  return (
    <section className="nt-agenda" data-screen-label="Tampilan pendukung">
      <header className="nt-ahead">
        <div className="nt-eyebrow">Tampilan pendukung</div>
        <h2 className="nt-h2">Review keputusan, risiko & tindak lanjut</h2>
        <p className="nt-focus">Dihitung ulang dari record agenda 5, 7, dan 8 setiap kali nilai berubah. Kalender bukan acara kalender pribadi.</p>
      </header>
      <div className="nt-views">
        <Card title="Perlu Keputusan" description="Status: Belum diputuskan, Ditunda, atau kosong." actions={<Badge tone="warning">{pending.length}</Badge>}>
          {pending.length ? <ul className="nt-vlist">{pending.map((r) => <Row key={r.id} title={(v(r, 'ID keputusan') ? v(r, 'ID keputusan') + ' — ' : '') + v(r, 'Topik keputusan')} meta={[v(r, 'Agenda'), v(r, 'PIC pelaksanaan')]} badge={v(r, 'Status keputusan') || 'Belum diisi'}></Row>)}</ul> : <Empty></Empty>}
        </Card>
        <Card title="Risiko Tinggi" description="Review mitigasi, PIC dan tenggat." actions={<Badge tone="danger">{risks.length}</Badge>}>
          {risks.length ? <ul className="nt-vlist">{risks.map((r) => <Row key={r.id} title={v(r, 'Risiko / isu kepatuhan') || 'Tanpa judul'} meta={[v(r, 'Mitigasi / kontrol'), v(r, 'Risk owner / PIC'), fmtDate(v(r, 'Tenggat'))]} badge={v(r, 'Status mitigasi')}></Row>)}</ul> : <Empty></Empty>}
        </Card>
        <Card className="nt-views__wide" title="Follow-up Board" description="Dikelompokkan berdasarkan Status. Terhambat memerlukan perhatian; Selesai setelah indikator terpenuhi.">
          <div className="nt-board">
            {['Belum mulai', 'Berjalan', 'Terhambat', 'Selesai', 'Belum diisi'].map((s) => {
              const items = acts.filter((r) => (v(r, 'Status') || 'Belum diisi') === s);
              return <div key={s} className="nt-col"><div className="nt-col__h"><Badge tone={TONE[s] || 'neutral'} dot>{s}</Badge><span className="nt-mono nt-muted">{items.length}</span></div>
                {items.length ? items.map((r) => <div key={r.id} className="nt-tile"><div className="nt-vrow__t">{(v(r, 'ID tindakan') ? v(r, 'ID tindakan') + ' — ' : '') + v(r, 'Tindakan / deliverable')}</div><div className="nt-vrow__m">{[v(r, 'PIC utama'), fmtDate(v(r, 'Target waktu')) || 'Tanpa target'].filter(Boolean).join(' · ')}</div>{v(r, 'Indikator penyelesaian') ? <div className="nt-vrow__m">{v(r, 'Indikator penyelesaian')}</div> : null}</div>) : <p className="nt-empty nt-empty--sm">Belum ada tindakan.</p>}
              </div>;
            })}
          </div>
        </Card>
        <Card className="nt-views__wide" title="Kalender Tindak Lanjut" description="Diurutkan berdasarkan Target waktu, paling awal lebih dulu. Milestone program ditinjau melalui agenda 4.">
          {cal.length ? <ul className="nt-vlist">{cal.map((r) => <li key={r.id} className="nt-vrow nt-vrow--cal"><span className="nt-mono nt-cal__d">{fmtDate(v(r, 'Target waktu'))}</span><div><div className="nt-vrow__t">{v(r, 'Tindakan / deliverable')}</div><div className="nt-vrow__m">{v(r, 'PIC utama') || '—'}</div></div>{v(r, 'Status') ? <Badge tone={TONE[v(r, 'Status')]} size="sm">{v(r, 'Status')}</Badge> : null}</li>)}</ul> : <Empty></Empty>}
        </Card>
      </div>
    </section>
  );
}

function GuidePanel() {
  return (
    <section className="nt-agenda" data-screen-label="Panduan">
      <header className="nt-ahead"><div className="nt-eyebrow">Panduan asli — ditampilkan lengkap</div><h2 className="nt-h2">Panduan & checklist</h2></header>
      <Card padding="lg"><div className="nt-guide" dangerouslySetInnerHTML={{ __html: ND.guide }}></div></Card>
    </section>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "showTypes": true,
  "expand": "pertama",
  "nav": "sidebar"
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [state, setState] = React.useState(loadState);
  const [view, setView] = React.useState(() => localStorage.getItem(STORE + ':view') || '0');
  const [printing, setPrinting] = React.useState(false);
  const [confirmReset, setConfirmReset] = React.useState(false);
  const { toast } = useToast();
  React.useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {} }, [state]);
  React.useEffect(() => { localStorage.setItem(STORE + ':view', view); }, [view]);
  React.useEffect(() => { const off = () => setPrinting(false); window.addEventListener('afterprint', off); return () => window.removeEventListener('afterprint', off); }, []);
  const setRecords = (ai) => (recs) => setState((s) => s.map((x, i) => i === ai ? recs : x));

  const main = state[0].find((r) => r.values['Nama rapat'] && r.values['Nama rapat'] !== 'Isi nama rapat') || state[0].find((r) => r.values['Nama rapat']) || state[0][0] || { values: {} };
  const mv = main.values || {};
  const checks = CHECKLIST.filter((k) => mv[k]).length;
  const pendingN = state[7].filter((r) => r.values['Topik keputusan'] && ['', undefined, 'Belum diputuskan', 'Ditunda'].includes(r.values['Status keputusan'])).length;

  const save = () => {
    const copy = document.documentElement.cloneNode(true);
    copy.querySelector('#root').innerHTML = '';
    copy.querySelectorAll('[data-om-transient], .twk-panel').forEach((e) => e.remove());
    let s = copy.querySelector('#saved-state');
    s.textContent = JSON.stringify(state).replace(/</g, '\\u003c');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['<!doctype html>\n' + copy.outerHTML], { type: 'text/html;charset=utf-8' }));
    a.download = 'Notulen_Rapat_Direksi_terisi.html'; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast({ title: 'HTML terisi diunduh', description: 'Simpan di folder yang sama dengan file aslinya.', tone: 'success' });
  };
  const doPrint = () => { setPrinting(true); setTimeout(() => window.print(), 300); };

  const navItems = [...AGENDAS.map((a, i) => ({ id: String(i), label: a.nav, badge: state[i].length })), { id: 'views', label: 'Tampilan pendukung', badge: pendingN || undefined }, { id: 'guide', label: 'Panduan & checklist' }];
  const content = printing
    ? <>{AGENDAS.map((_, i) => <AgendaView key={'p' + i} ai={i} records={state[i]} setRecords={setRecords(i)} t={t} printing></AgendaView>)}<ViewsPanel state={state}></ViewsPanel></>
    : view === 'views' ? <ViewsPanel state={state}></ViewsPanel>
    : view === 'guide' ? <GuidePanel></GuidePanel>
    : <AgendaView key={view + t.expand} ai={+view} records={state[+view]} setRecords={setRecords(+view)} t={t}></AgendaView>;

  return (
    <JupUIProvider theme={t.theme} storageKey={null} className="nt-app">
      <header className="nt-top">
        <div className="nt-top__in">
          <div className="nt-top__id">
            <div className="nt-eyebrow">Rapat Direksi / Notulen</div>
            <h1 className="nt-h1">{mv['Nama rapat'] && mv['Nama rapat'] !== 'Isi nama rapat' ? mv['Nama rapat'] : 'Notulen Rapat Direksi'}</h1>
            <div className="nt-top__meta">
              {mv['Status validasi'] ? <Badge tone={TONE[mv['Status validasi']] || 'neutral'} dot>{mv['Status validasi']}</Badge> : null}
              {mv['Klasifikasi dokumen'] ? <Badge tone={mv['Klasifikasi dokumen'] === 'Rahasia' ? 'danger' : 'info'} variant="outline">{mv['Klasifikasi dokumen']}</Badge> : null}
              {fmtDate(mv['Tanggal & waktu']) ? <span className="nt-mono">{fmtDate(mv['Tanggal & waktu'])}</span> : null}
              {mv['Ruang / lokasi'] ? <span>{mv['Ruang / lokasi']}</span> : null}
              <span className="nt-mono nt-muted">Checklist {checks}/{CHECKLIST.length}</span>
            </div>
          </div>
          <div className="nt-actions">
            <Button variant="ghost" iconLeft={<Icon name="reset"></Icon>} onClick={() => setConfirmReset(true)}>Reset</Button>
            <Button variant="secondary" iconLeft={<Icon name="printer"></Icon>} onClick={doPrint}>Cetak / PDF</Button>
            <Button variant="primary" iconLeft={<Icon name="download"></Icon>} onClick={save}>Simpan HTML terisi</Button>
          </div>
        </div>
        {t.nav === 'tabs' ? <div className="nt-top__tabs"><Tabs items={navItems} value={view} onChange={setView} label="Navigasi agenda" size="sm"></Tabs></div> : null}
      </header>
      <div className={'nt-shell' + (t.nav === 'tabs' ? ' nt-shell--tabs' : '')}>
        {t.nav === 'sidebar' ? (
          <nav className="nt-side" aria-label="Navigasi agenda">
            {navItems.map((n, i) => <React.Fragment key={n.id}>
              {i === 9 ? <div className="nt-side__sep"></div> : null}
              <button type="button" className={'nt-side__item' + (view === n.id ? ' is-active' : '')} aria-current={view === n.id ? 'page' : undefined} onClick={() => { setView(n.id); window.scrollTo({ top: 0 }); }}>
                <span>{n.label}</span>{n.badge != null ? <span className="nt-side__n">{n.badge}</span> : null}
              </button>
            </React.Fragment>)}
          </nav>) : null}
        <main className="nt-main">
          {view === '0' && !printing ? <Alert tone="info" title="HTML mandiri · bukan koneksi langsung ke Notion">Isi nama orang secara manual; dokumen disimpan sebagai nama/tautan. Perubahan tersimpan di peramban ini; gunakan <strong>Simpan HTML terisi</strong> untuk membuat salinan berisi data.</Alert> : null}
          {content}
          <footer className="nt-foot">{ND.footer}</footer>
        </main>
      </div>
      <Dialog open={confirmReset} onClose={() => setConfirmReset(false)} title="Reset notulen?" description="Seluruh isian dikembalikan ke template awal. Tindakan ini tidak dapat dibatalkan."
        footer={<><Button variant="ghost" onClick={() => setConfirmReset(false)}>Batal</Button><Button variant="danger" onClick={() => { setState(initialState()); setConfirmReset(false); setView('0'); toast({ title: 'Template dikembalikan', tone: 'neutral' }); }}>Reset</Button></>}></Dialog>
      <TweaksPanel>
        <TweakSection label="Tampilan"></TweakSection>
        <TweakRadio label="Tema" value={t.theme} options={['light', 'dark']} onChange={(v) => setTweak('theme', v)}></TweakRadio>
        <TweakRadio label="Navigasi" value={t.nav} options={['sidebar', 'tabs']} onChange={(v) => setTweak('nav', v)}></TweakRadio>
        <TweakSection label="Record"></TweakSection>
        <TweakRadio label="Buka record" value={t.expand} options={['pertama', 'semua']} onChange={(v) => setTweak('expand', v)}></TweakRadio>
        <TweakToggle label="Tampilkan jenis properti" value={t.showTypes} onChange={(v) => setTweak('showTypes', v)}></TweakToggle>
      </TweaksPanel>
    </JupUIProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<ToastProviderRoot></ToastProviderRoot>);
function ToastProviderRoot() { return <JupUIProvider theme="light" storageKey={null} className="nt-outer"><ToastProvider><App></App></ToastProvider></JupUIProvider>; }
