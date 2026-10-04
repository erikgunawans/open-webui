const { Badge, Card, Button, Tag } = window.JupUI;
const R = window.RAPAT;
function LIcon({ d, size = 18 }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d}></path></svg>; }
const nf = (n, d = 1) => n.toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });
const TONE_L = { 'Selesai': 'success', 'Disetujui': 'success', 'On track': 'success', 'Dilanjutkan': 'success', 'Berjalan': 'info', 'Dalam review': 'info', 'Disesuaikan': 'info', 'Disetujui bersyarat': 'warning', 'At risk': 'warning', 'Sedang': 'warning', 'Ditunda': 'warning', 'Perlu evaluasi': 'warning', 'Belum diputuskan': 'neutral', 'Terhambat': 'danger', 'Delayed': 'danger', 'Ditolak': 'danger', 'Tinggi': 'danger', 'Mendesak': 'danger', 'Belum mulai': 'neutral', 'Rendah': 'neutral' };
const B = ({ s, dot = true, variant }) => <Badge tone={TONE_L[s] || 'neutral'} dot={dot} variant={variant}>{s}</Badge>;
const dev = (k) => { const d = (k.real - k.target) / k.target * 100; const good = k.cost ? d <= 0 : d >= 0; return { d, tone: good ? 'success' : Math.abs(d) <= 10 ? 'warning' : 'danger' }; };
const fmtD = (iso) => new Date(iso + 'T00:00').toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });

function Bar({ pct, tone = 'brand' }) {
  return <div className="lr-bar"><div className={'lr-bar__f lr-bar__f--' + tone} style={{ width: Math.min(100, pct) + '%' }}></div></div>;
}
function Head({ a, right }) {
  return (
    <header className="lr-ahead">
      <div>
        <div className="lr-eyebrow">Agenda {a.no} · {a.pemapar}</div>
        <h2 className="lr-h2">{a.nav}</h2>
        {a.focus ? <p className="lr-focus">{a.focus}</p> : null}
      </div>
      {right}
    </header>
  );
}

function VInfo({ a }) {
  const m = R.meta, s = R.ringkasan;
  return (
    <div className="lr-view">
      <Head a={{ ...a, focus: m.periode }}></Head>
      <div className="lr-g2">
        <Card title="Kondisi perusahaan" padding="md"><p className="lr-lead">{s.kondisi}</p></Card>
        <Card title="Kehadiran" description={m.peserta.length + ' dari 4 Direksi hadir · kuorum terpenuhi'} padding="md">
          <ul className="lr-people">{m.peserta.map(([n, j]) => <li key={n}><window.JupUI.Avatar name={n} size="md"></window.JupUI.Avatar><div><div className="lr-strong">{n}</div><div className="lr-sub">{j}</div></div></li>)}</ul>
          <div className="lr-sub lr-mt">Undangan: {m.eksternal.join(' · ')}</div>
        </Card>
        <Card title="Isu perhatian Direksi" padding="md"><ol className="lr-ol">{s.isu.map((x) => <li key={x}>{x}</li>)}</ol></Card>
        <Card title="Tindak lanjut mendesak" padding="md"><ol className="lr-ol">{s.mendesak.map((x) => <li key={x}>{x}</li>)}</ol></Card>
      </div>
    </div>
  );
}

function VStrategi({ a }) {
  return (
    <div className="lr-view">
      <Head a={a}></Head>
      <div className="lr-table lr-table--strat">
        <div className="lr-tr lr-th"><span>Sasaran strategis</span><span>Target</span><span>Posisi terkini</span><span>Pencapaian</span><span>Evaluasi</span></div>
        {R.strategi.map((s) => (
          <div className="lr-tr" key={s.sasaran}>
            <span><span className="lr-strong">{s.sasaran}</span><span className="lr-sub">{s.pemapar} · {s.deviasi}</span></span>
            <span className="lr-mono">{s.target}</span>
            <span className="lr-mono lr-strong">{s.posisi}</span>
            <span className="lr-progress"><Bar pct={s.pct} tone={s.pct >= 75 ? 'brand' : 'warning'}></Bar><span className="lr-mono">{s.pct}%</span></span>
            <span><B s={s.evaluasi}></B></span>
          </div>))}
      </div>
    </div>
  );
}

function VKinerja({ a }) {
  const max = Math.max(...R.kinerjaBulan.map((x) => Math.max(x[1], x[2])));
  const c = R.kinerjaCatatan;
  return (
    <div className="lr-view">
      <Head a={a} right={<div className="lr-tagline"><Badge tone="info" variant="outline">YTD September 2026</Badge><span className="lr-sub">Rp miliar kecuali dinyatakan lain</span></div>}></Head>
      <div className="lr-kpis">
        {R.kinerja.map((k) => { const v = dev(k); const pct = k.sat === 'Persen';
          return (
            <div className="lr-kpi" key={k.ind}>
              <div className="lr-kpi__h"><span>{k.ind}</span><Badge tone={v.tone} size="sm">{(v.d > 0 ? '+' : '') + nf(v.d)}%</Badge></div>
              <div className="lr-kpi__v">{nf(k.real)}{pct ? '%' : ''}</div>
              <Bar pct={k.real / k.target * 100} tone={v.tone === 'success' ? 'brand' : v.tone}></Bar>
              <div className="lr-sub">{k.cost ? 'Anggaran' : 'Target'} {nf(k.target)}{pct ? '%' : ''}</div>
            </div>); })}
      </div>
      <div className="lr-g2 lr-g2--chart">
        <Card title="Revenue bulanan vs target" description="Rp miliar · Jan–Sep 2026" padding="md">
          <div className="lr-chart">
            {R.kinerjaBulan.map(([b, r, t]) => (
              <div className="lr-chart__c" key={b}>
                <div className="lr-chart__bars">
                  <div className="lr-chart__t" style={{ bottom: (t / max * 100) + '%' }}></div>
                  <div className={'lr-chart__b' + (r < t ? ' is-under' : '')} style={{ height: (r / max * 100) + '%' }}></div>
                </div>
                <span className="lr-mono lr-sub">{b}</span>
              </div>))}
          </div>
          <div className="lr-legend"><span><i className="lr-sw lr-sw--b"></i>Realisasi ≥ target</span><span><i className="lr-sw lr-sw--u"></i>Di bawah target</span><span><i className="lr-sw lr-sw--t"></i>Target</span></div>
        </Card>
        <Card title="Penyebab & langkah koreksi" padding="md">
          <dl className="lr-dl"><dt>Penyebab</dt><dd>{c.penyebab}</dd><dt>Koreksi</dt><dd>{c.koreksi}</dd><dt>Likuiditas</dt><dd>{c.likuiditas}</dd></dl>
        </Card>
      </div>
    </div>
  );
}

function VIsu({ a }) {
  return (
    <div className="lr-view">
      <Head a={a}></Head>
      <div className="lr-stack">
        {R.isu.map((x, i) => (
          <Card key={x.isu} padding="md">
            <div className="lr-issue">
              <div className="lr-issue__n lr-mono">{String(i + 1).padStart(2, '0')}</div>
              <div className="lr-issue__b">
                <div className="lr-h3">{x.isu}</div>
                <div className="lr-sub">{x.unit}</div>
                <div className="lr-issue__g"><div><div className="lr-k">Dampak</div><div>{x.dampak}</div></div><div><div className="lr-k">Keputusan yang diperlukan</div><div className="lr-strong">{x.perlu}</div></div></div>
              </div>
              <div className="lr-issue__m"><div className="lr-k">PIC</div><div>{x.pic}</div><div className="lr-k lr-mt">Target</div><div className="lr-mono">{x.target}</div><Badge tone="info" variant="outline">{x.ref}</Badge></div>
            </div>
          </Card>))}
      </div>
    </div>
  );
}

function VProgram({ a }) {
  const tot = R.program.reduce((s, p) => [s[0] + p.ang, s[1] + p.real], [0, 0]);
  return (
    <div className="lr-view">
      <Head a={a} right={<div className="lr-tagline"><span className="lr-k">Serapan anggaran</span><span className="lr-bignum">{nf(tot[1] / tot[0] * 100)}%</span><span className="lr-sub">Rp {nf(tot[1])} M dari Rp {nf(tot[0])} M</span></div>}></Head>
      <div className="lr-table lr-table--prog">
        <div className="lr-tr lr-th"><span>Program / proyek</span><span>Progres</span><span>Anggaran · realisasi (Rp M)</span><span>Milestone berikutnya</span><span>Status</span></div>
        {R.program.map((p) => (
          <div className="lr-tr" key={p.nama}>
            <span><span className="lr-strong">{p.nama}</span><span className="lr-sub">{p.kat} · {p.pic}</span></span>
            <span className="lr-progress"><Bar pct={p.pct} tone={TONE_L[p.status] === 'danger' ? 'danger' : TONE_L[p.status] === 'warning' ? 'warning' : 'brand'}></Bar><span className="lr-mono">{p.pct}%</span></span>
            <span className="lr-mono">{nf(p.ang)} · <span className="lr-strong">{nf(p.real)}</span></span>
            <span>{p.milestone}</span>
            <span><B s={p.status}></B></span>
          </div>))}
      </div>
    </div>
  );
}

function VRisiko({ a }) {
  const lv = ['Tinggi', 'Sedang', 'Rendah'];
  return (
    <div className="lr-view">
      <Head a={a} right={<div className="lr-tagline">{lv.map((l) => <Badge key={l} tone={TONE_L[l]} variant="solid">{R.risiko.filter((r) => r.lvl === l).length} {l}</Badge>)}</div>}></Head>
      <div className="lr-stack lr-stack--tight">
        {R.risiko.map((r) => (
          <div className={'lr-risk lr-risk--' + TONE_L[r.lvl]} key={r.r}>
            <div className="lr-risk__lvl"><span className="lr-k">Tingkat</span><span className="lr-strong">{r.lvl}</span></div>
            <div><div className="lr-h3">{r.r}</div><div className="lr-sub">{r.mitigasi}</div><div className="lr-tags">{r.kat.map((k) => <Tag key={k} size="sm">{k}</Tag>)}</div></div>
            <div><div className="lr-k">Risk owner</div><div>{r.owner}</div></div>
            <div><div className="lr-k">Tenggat</div><div className="lr-mono">{r.tenggat}</div></div>
            <div><B s={r.status}></B></div>
          </div>))}
      </div>
    </div>
  );
}

function VStakeholder({ a }) {
  return (
    <div className="lr-view">
      <Head a={a}></Head>
      <div className="lr-table lr-table--stake">
        <div className="lr-tr lr-th"><span>Stakeholder</span><span>Isu / permintaan utama</span><span>PIC komunikasi</span><span>Target</span><span>Urgensi</span></div>
        {R.stakeholder.map((s) => (
          <div className="lr-tr" key={s.org}>
            <span><span className="lr-strong">{s.org}</span><span className="lr-sub">{s.jenis}</span></span>
            <span>{s.isu}</span><span>{s.pic}</span><span className="lr-mono">{s.target}</span><span><B s={s.urg}></B></span>
          </div>))}
      </div>
    </div>
  );
}

function VKeputusan({ a, dec, setDec, sel, setSel }) {
  const d = R.keputusan.find((x) => x.id === sel) || R.keputusan[0];
  const st = dec[d.id];
  const acts = [['Disetujui', 'primary', 'Setujui'], ['Disetujui bersyarat', 'secondary', 'Setujui bersyarat'], ['Ditunda', 'outline', 'Tunda'], ['Ditolak', 'danger', 'Tolak']];
  return (
    <div className="lr-view">
      <Head a={a} right={<div className="lr-tagline"><span className="lr-k">Diputuskan</span><span className="lr-bignum">{R.keputusan.filter((x) => dec[x.id] !== 'Belum diputuskan').length}/{R.keputusan.length}</span></div>}></Head>
      <div className="lr-dec">
        <div className="lr-dec__list" role="listbox" aria-label="Daftar keputusan">
          {R.keputusan.map((x) => (
            <button type="button" role="option" aria-selected={x.id === d.id} key={x.id} className={'lr-dec__item' + (x.id === d.id ? ' is-active' : '')} onClick={() => setSel(x.id)}>
              <span className="lr-mono lr-strong">{x.id}</span>
              <span className="lr-dec__t">{x.topik}</span>
              <B s={dec[x.id]}></B>
            </button>))}
        </div>
        <Card padding="md" className="lr-dec__detail">
          <div className="lr-dec__top"><span className="lr-mono lr-k">{d.id} · {d.agenda}</span><B s={st}></B></div>
          <div className="lr-h3 lr-h3--lg">{d.topik}</div>
          <div className="lr-k lr-mt">Keputusan yang dimohonkan</div><p className="lr-lead">{d.mohon}</p>
          <div className="lr-g2 lr-g2--tight">
            <div><div className="lr-k">Rekomendasi</div><div>{d.rekom}</div></div>
            <div><div className="lr-k">Kewenangan / persetujuan lanjutan</div><div className="lr-tags">{d.kewenangan.map((k) => <Tag key={k} size="sm">{k}</Tag>)}</div></div>
            <div><div className="lr-k">PIC pelaksanaan</div><div>{d.pic}</div></div>
          </div>
          <div className="lr-dec__acts">
            {acts.map(([s, v, l]) => <Button key={s} variant={st === s ? (v === 'outline' ? 'secondary' : v) : 'outline'} size="lg" onClick={() => setDec(d.id, st === s ? 'Belum diputuskan' : s)} aria-pressed={st === s}>{st === s ? '✓ ' : ''}{l}</Button>)}
          </div>
        </Card>
      </div>
    </div>
  );
}

function VAksi({ a, acts, setAct }) {
  const cols = ['Belum mulai', 'Berjalan', 'Terhambat', 'Selesai'];
  const next = (s) => cols[(cols.indexOf(s) + 1) % cols.length];
  return (
    <div className="lr-view">
      <Head a={a} right={<div className="lr-tagline"><span className="lr-sub">Klik kartu untuk memajukan status</span></div>}></Head>
      <div className="lr-board">
        {cols.map((c) => { const items = R.aksi.filter((x) => acts[x.id] === c);
          return (
            <div className="lr-col" key={c}>
              <div className="lr-col__h"><B s={c}></B><span className="lr-mono lr-sub">{items.length}</span></div>
              {items.map((x) => (
                <button type="button" className="lr-tile" key={x.id} onClick={() => setAct(x.id, next(c))}>
                  <div className="lr-tile__top"><span className="lr-mono lr-strong">{x.id}</span><span className="lr-mono lr-sub">{fmtD(x.target)}</span></div>
                  <div className="lr-tile__t">{x.t}</div>
                  <div className="lr-sub">{x.pic}</div>
                  <div className="lr-tile__f"><span className="lr-sub">{x.ind}</span>{x.asal === 'Rapat sebelumnya' ? <Badge size="sm" tone="info" variant="outline">Sebelumnya</Badge> : null}</div>
                </button>))}
            </div>); })}
      </div>
    </div>
  );
}

Object.assign(window, { LIcon, VInfo, VStrategi, VKinerja, VIsu, VProgram, VRisiko, VStakeholder, VKeputusan, VAksi, TONE_L, fmtD });
