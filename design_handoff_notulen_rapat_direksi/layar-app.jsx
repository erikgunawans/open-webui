const { JupUIProvider, ToastProvider, useToast, Button: LButton, Badge: LBadge } = window.JupUI;
const RD = window.RAPAT;
const LKEY = 'jup-layar-rapat-v1';
const VIEWS = [VInfo, VStrategi, VKinerja, VIsu, VProgram, VRisiko, VStakeholder, VKeputusan, VAksi];
const AG = window.RAPAT.agendas;

function useStored(init) {
  const [s, setS] = React.useState(() => { try { return { ...init, ...JSON.parse(localStorage.getItem(LKEY) || '{}') }; } catch (e) { return init; } });
  React.useEffect(() => { localStorage.setItem(LKEY, JSON.stringify(s)); }, [s]);
  return [s, setS];
}
const mmss = (s) => String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');

function Stage({ children }) {
  const [k, setK] = React.useState(1);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const f = () => { const el = ref.current; const w = el?.clientWidth || window.innerWidth, h = el?.clientHeight || window.innerHeight; if (w > 0 && h > 0) { const n = Math.min(w / 1920, h / 1080); setK((p) => Math.abs(p - n) > 0.0005 ? n : p); } };
    f();
    const ro = new ResizeObserver(f); ro.observe(ref.current); ro.observe(document.documentElement);
    const iv = setInterval(f, 500);
    window.addEventListener('resize', f); document.addEventListener('visibilitychange', f);
    return () => { clearInterval(iv); ro.disconnect(); window.removeEventListener('resize', f); document.removeEventListener('visibilitychange', f); };
  }, []);
  return <div className="lr-viewport" ref={ref}><div className="lr-stage" style={{ transform: `translate(-50%,-50%) scale(${k})` }}>{children}</div></div>;
}

const LTWEAKS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "rail": true,
  "timer": true
}/*EDITMODE-END*/;

function Layar() {
  const [t, setTweak] = useTweaks(LTWEAKS);
  const init = { cur: 0, done: [], dec: Object.fromEntries(RD.keputusan.map((d) => [d.id, d.status])), acts: Object.fromEntries(RD.aksi.map((a) => [a.id, a.status])), sel: 'D-01' };
  const [s, setS] = useStored(init);
  const { toast } = useToast();
  const [now, setNow] = React.useState(new Date());
  const [enteredAt, setEnteredAt] = React.useState(Date.now());
  React.useEffect(() => { const i = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(i); }, []);
  const go = (i) => { if (i < 0 || i >= AG.length) return; setS((p) => ({ ...p, cur: i })); setEnteredAt(Date.now()); };
  React.useEffect(() => {
    const k = (e) => { if (e.target.closest && e.target.closest('input,textarea,select')) return; if (e.key === 'ArrowRight' || e.key === 'PageDown') go(s.cur + 1); else if (e.key === 'ArrowLeft' || e.key === 'PageUp') go(s.cur - 1); else if (/^[0-8]$/.test(e.key)) go(+e.key); };
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k);
  }, [s.cur]);
  const a = AG[s.cur];
  const V = VIEWS[s.cur];
  const elapsed = Math.max(0, Math.floor((now - enteredAt) / 1000));
  const over = elapsed > a.menit * 60;
  const setDec = (id, st) => { setS((p) => ({ ...p, dec: { ...p.dec, [id]: st } })); toast({ title: id + ' · ' + st, description: RD.keputusan.find((d) => d.id === id).topik, tone: st === 'Disetujui' ? 'success' : st === 'Ditolak' ? 'danger' : st === 'Belum diputuskan' ? 'neutral' : 'warning' }); };
  const setAct = (id, st) => setS((p) => ({ ...p, acts: { ...p.acts, [id]: st } }));
  const finish = () => { setS((p) => ({ ...p, done: [...new Set([...p.done, p.cur])] })); if (s.cur < AG.length - 1) go(s.cur + 1); toast({ title: 'Agenda ' + a.no + ' selesai dibahas', tone: 'success' }); };
  const pending = RD.keputusan.filter((d) => ['Belum diputuskan', 'Ditunda'].includes(s.dec[d.id]));
  const decided = RD.keputusan.length - RD.keputusan.filter((d) => s.dec[d.id] === 'Belum diputuskan').length;
  const soon = RD.aksi.filter((x) => s.acts[x.id] !== 'Selesai').sort((x, y) => x.target.localeCompare(y.target)).slice(0, 4);
  const totalMin = AG.reduce((n, x) => n + x.menit, 0);

  return (
    <JupUIProvider theme={t.theme} storageKey={null} className="lr-app">
      <div className={'lr-grid' + (t.rail ? '' : ' lr-grid--norail')}>
        <header className="lr-top">
          <div className="lr-top__id">
            <div className="lr-eyebrow">PT Jakarta Utilitas Propertindo · Notulen Rapat Direksi</div>
            <h1 className="lr-h1">{RD.meta.nama}</h1>
            <div className="lr-top__meta"><span className="lr-mono">{RD.meta.nomor}</span><span>{RD.meta.tanggal} · {RD.meta.waktu}</span><span>{RD.meta.lokasi}</span><LBadge tone="danger" variant="outline">{RD.meta.klasifikasi}</LBadge><LBadge tone="warning" variant="subtle">Data dummy</LBadge></div>
          </div>
          <div className="lr-clock">
            <div className="lr-clock__t lr-mono">{now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}<span className="lr-sub"> WIB</span></div>
            {t.timer ? <div className={'lr-clock__a' + (over ? ' is-over' : '')}><span className="lr-k">Agenda {a.no}</span><span className="lr-mono">{mmss(elapsed)} / {String(a.menit).padStart(2, '0')}:00</span></div> : null}
          </div>
        </header>

        <nav className="lr-nav" aria-label="Agenda rapat">
          <div className="lr-k lr-nav__h">Agenda · {totalMin} menit</div>
          {AG.map((x, i) => { const st = i === s.cur ? 'cur' : s.done.includes(i) ? 'done' : 'todo';
            return (
              <button type="button" key={x.key} className={'lr-nav__i lr-nav__i--' + st} aria-current={i === s.cur ? 'step' : undefined} onClick={() => go(i)}>
                <span className="lr-nav__no lr-mono">{st === 'done' ? <LIcon d="M20 6 9 17l-5-5"></LIcon> : x.no}</span>
                <span className="lr-nav__t"><span>{x.nav}</span><span className="lr-sub">{x.pemapar}</span></span>
                <span className="lr-mono lr-sub">{x.menit}′</span>
              </button>); })}
        </nav>

        <main className="lr-main" data-screen-label={'Agenda ' + a.no}>
          <V key={s.cur} a={a} dec={s.dec} setDec={setDec} sel={s.sel} setSel={(id) => setS((p) => ({ ...p, sel: id }))} acts={s.acts} setAct={setAct}></V>
        </main>

        {t.rail ? (
          <aside className="lr-rail">
            <div className="lr-stats">
              <div><span className="lr-k">Keputusan</span><span className="lr-bignum">{decided}<span className="lr-sub">/{RD.keputusan.length}</span></span></div>
              <div><span className="lr-k">Tindakan baru</span><span className="lr-bignum">{RD.aksi.filter((x) => x.asal === 'Rapat ini').length}</span></div>
              <div><span className="lr-k">Risiko tinggi</span><span className="lr-bignum lr-danger">{RD.risiko.filter((r) => r.lvl === 'Tinggi').length}</span></div>
            </div>
            <section className="lr-rail__s">
              <div className="lr-rail__h"><span>Perlu keputusan</span><LBadge tone="warning">{pending.length}</LBadge></div>
              {pending.length ? pending.map((d) => (
                <button type="button" key={d.id} className="lr-rail__item" onClick={() => { setS((p) => ({ ...p, sel: d.id })); go(7); }}>
                  <span className="lr-mono lr-strong">{d.id}</span><span className="lr-rail__t">{d.topik}</span>{s.dec[d.id] === 'Ditunda' ? <LBadge tone="warning" size="sm">Ditunda</LBadge> : null}
                </button>)) : <p className="lr-sub">Semua usulan telah diputuskan.</p>}
            </section>
            <section className="lr-rail__s">
              <div className="lr-rail__h"><span>Tenggat terdekat</span></div>
              {soon.map((x) => (
                <button type="button" key={x.id} className="lr-rail__item" onClick={() => go(8)}>
                  <span className="lr-mono lr-cal">{fmtD(x.target)}</span><span className="lr-rail__t">{x.t}<span className="lr-sub">{x.pic}</span></span>
                </button>))}
            </section>
          </aside>) : null}

        <footer className="lr-foot">
          <div className="lr-timeline" aria-hidden="true">
            {AG.map((x, i) => <div key={x.key} className={'lr-seg' + (i === s.cur ? ' is-cur' : s.done.includes(i) ? ' is-done' : '')} style={{ flexGrow: x.menit }}><span className="lr-mono">{x.no}</span></div>)}
          </div>
          <div className="lr-foot__acts">
            <LButton variant="ghost" onClick={() => go(s.cur - 1)} disabled={s.cur === 0}>← Sebelumnya</LButton>
            <LButton variant="primary" onClick={finish}>{s.done.includes(s.cur) ? 'Lanjut' : 'Selesai dibahas'}{s.cur < AG.length - 1 ? ' →' : ''}</LButton>
          </div>
        </footer>
      </div>
      <TweaksPanel>
        <TweakSection label="Layar"></TweakSection>
        <TweakRadio label="Tema" value={t.theme} options={['light', 'dark']} onChange={(v) => setTweak('theme', v)}></TweakRadio>
        <TweakToggle label="Panel kanan" value={t.rail} onChange={(v) => setTweak('rail', v)}></TweakToggle>
        <TweakToggle label="Timer agenda" value={t.timer} onChange={(v) => setTweak('timer', v)}></TweakToggle>
        <TweakButton label="Reset status rapat" onClick={() => { setS(init); setEnteredAt(Date.now()); }}></TweakButton>
      </TweaksPanel>
    </JupUIProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<JupUIProvider theme="light" storageKey={null} className="lr-outer"><ToastProvider placement="bottom-right"><Stage><Layar></Layar></Stage></ToastProvider></JupUIProvider>);
