const { Field, Input, Textarea, Select, Checkbox, Tag } = window.JupUI;

const LUCIDE = {
  plus: ['M5 12h14', 'M12 5v14'],
  trash: ['M3 6h18', 'M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6', 'M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2'],
  chevron: ['m6 9 6 6 6-6'],
  printer: ['M6 9V2h12v7', 'M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2', 'M6 14h12v8H6z'],
  download: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'm7 10 5 5 5-5', 'M12 15V3'],
  reset: ['M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8', 'M3 3v5h5'],
  check: ['M20 6 9 17l-5-5'],
};
function Icon({ name, size = 16 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{LUCIDE[name].map((d, i) => <path key={i} d={d}></path>)}</svg>;
}

const TYPE_LABEL = { title: 'title', rich_text: 'teks', people: 'person', files: 'files', checkbox: 'checkbox', select: 'select', status: 'status', multi_select: 'multi-select', date: 'date', number: 'number', url: 'url' };

function FieldLabel({ f, showType }) {
  return <span className="nt-label">{f.name}{showType ? <span className="nt-type">{TYPE_LABEL[f.type] || f.type}</span> : null}</span>;
}

function DateField({ f, value, timeOn, onChange, onTime, showType }) {
  const v = value || { start: '', end: '' };
  const type = timeOn ? 'datetime-local' : 'date';
  const conv = (x) => !x ? '' : timeOn ? (x.length === 10 ? x + 'T00:00' : x) : x.slice(0, 10);
  return (
    <div className="nt-date">
      <div className="nt-date__label"><FieldLabel f={f} showType={showType}></FieldLabel></div>
      <div className="nt-date__row">
        <Field label="Mulai"><Input type={type} value={conv(v.start)} onChange={(e) => onChange({ ...v, start: e.target.value })}></Input></Field>
        <Field label="Selesai (opsional)"><Input type={type} value={conv(v.end)} onChange={(e) => onChange({ ...v, end: e.target.value })}></Input></Field>
      </div>
      <Checkbox label="Sertakan waktu · Asia/Jakarta" checked={!!timeOn} onChange={(e) => {
        const on = e.target.checked;
        const c = (x) => !x ? '' : on ? x.slice(0, 10) + 'T00:00' : x.slice(0, 10);
        onChange({ start: c(v.start), end: c(v.end) }); onTime(on);
      }}></Checkbox>
      {f.description ? <p className="nt-hint">{f.description}</p> : null}
    </div>
  );
}

function PropField({ f, value, timeOn, onChange, onTime, showType }) {
  const label = <FieldLabel f={f} showType={showType}></FieldLabel>;
  const hint = f.description || undefined;
  switch (f.type) {
    case 'checkbox':
      return <div className="nt-check"><Checkbox label={f.name} checked={!!value} onChange={(e) => onChange(e.target.checked)}></Checkbox></div>;
    case 'date':
      return <DateField f={f} value={value} timeOn={timeOn} onChange={onChange} onTime={onTime} showType={showType}></DateField>;
    case 'select': case 'status':
      return <Field label={label} hint={hint}><Select value={value || ''} onChange={(e) => onChange(e.target.value)} options={[{ value: '', label: '— Pilih —' }, ...f.options.map((o) => ({ value: o, label: o }))]}></Select></Field>;
    case 'multi_select': {
      const arr = value || [];
      return (
        <div className="nt-multi">
          <div className="nt-date__label">{label}</div>
          <div className="nt-tags" role="group" aria-label={f.name}>
            {f.options.map((o) => <Tag key={o} selected={arr.includes(o)} onClick={() => onChange(arr.includes(o) ? arr.filter((x) => x !== o) : [...arr, o])}>{o}</Tag>)}
          </div>
          <p className="nt-hint">Pilih satu atau lebih.</p>
        </div>
      );
    }
    case 'number': {
      const pct = /persen/i.test(f.name), rp = /Rp$/.test(f.name);
      return <Field label={label} hint={hint}><Input type="number" inputMode="decimal" value={value ?? ''} prefix={rp ? 'Rp' : undefined} suffix={pct ? '%' : undefined} placeholder="0" onChange={(e) => onChange(e.target.value)}></Input></Field>;
    }
    case 'url':
      return <Field label={label} hint={hint}><Input type="url" value={value || ''} placeholder="https://" onChange={(e) => onChange(e.target.value)}></Input></Field>;
    case 'people':
      return <Field label={label} hint={hint}><Input value={value || ''} placeholder="Nama orang" onChange={(e) => onChange(e.target.value)}></Input></Field>;
    case 'files':
      return <Field label={label} hint={hint || 'Nama dokumen dan tautan — bukan unggahan file.'}><Textarea rows={2} autoResize value={value || ''} placeholder="Nama dokumen dan tautan file" onChange={(e) => onChange(e.target.value)}></Textarea></Field>;
    case 'rich_text':
      return <Field label={label} hint={hint}><Textarea rows={3} autoResize maxRows={14} value={value || ''} placeholder="Isi catatan…" onChange={(e) => onChange(e.target.value)}></Textarea></Field>;
    default:
      return <Field label={label} hint={hint}><Input value={value || ''} placeholder="Isi…" onChange={(e) => onChange(e.target.value)}></Input></Field>;
  }
}

Object.assign(window, { Icon, PropField });
