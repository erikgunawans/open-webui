import { useState } from 'react';
import { Alert, Button, Checkbox, Dialog, Textarea, type ToastContextValue } from '@jup/ui';
import { Plus } from 'lucide-react';

import { AGENDAS, ITEM_NOUN } from '../../agendas';
import { record } from '../../seed';
import type { Capture } from '../../capture';
import { text, titleField, type AgendaNotes, type NotulenRecord } from '../../types';
import { CaptureStrip } from './CaptureStrip';
import { RecordCard } from './RecordCard';

// One database (Informasi Rapat or an agenda): its header, its entries, add and delete.

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

type Props = {
	db: number;
	records: NotulenRecord[];
	setRecords: (next: NotulenRecord[]) => void;
	/** Print mode: every record open, no per-record controls. */
	printing?: boolean;
	expandAll?: boolean;
	/** From the caller: the snapshot renders without a ToastProvider, whose portal the server renderer rejects. */
	toast: ToastContextValue['toast'];
	/** Live meeting only (absent in the snapshot): the Catat cepat strip and the Catatan pembahasan. */
	live?: {
		onCapture: (c: Capture) => void;
		notes: AgendaNotes;
		onNotes: (n: AgendaNotes) => void;
	};
};

export const AgendaView = ({
	db,
	records,
	setRecords,
	printing,
	expandAll,
	toast,
	live
}: Props) => {
	const a = AGENDAS[db];
	const noun = ITEM_NOUN[db];
	const [openIds, setOpenIds] = useState<Set<string>>(
		() =>
			new Set(
				records.length <= 2 || expandAll
					? records.map((r) => r.id)
					: records[0]
						? [records[0].id]
						: []
			)
	);
	const [toDelete, setToDelete] = useState<NotulenRecord | null>(null);
	const allOpen = records.every((r) => openIds.has(r.id));

	const add = () => {
		const r = record({}, '', 'Baru');
		setRecords([...records, r]);
		setOpenIds(new Set([...openIds, r.id]));
		toast({ title: `${cap(noun)} ditambahkan`, description: a.nav, tone: 'success' });
	};
	const toggle = (id: string) => {
		const next = new Set(openIds);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		setOpenIds(next);
	};
	const remove = () => {
		if (!toDelete) return;
		setRecords(records.filter((x) => x.id !== toDelete.id));
		setToDelete(null);
		toast({ title: `${cap(noun)} dihapus`, tone: 'neutral' });
	};

	return (
		<section className="nt-agenda" aria-labelledby={`nt-h-${db}`}>
			<header className="nt-ahead">
				<div className="nt-eyebrow">{a.eyebrow}</div>
				<h2 className="nt-h2" id={`nt-h-${db}`}>
					{a.title}
				</h2>
				<p className="nt-focus">
					<strong>Fokus:</strong> {a.focus}
					{a.unit ? <span> — {a.unit}.</span> : null}
				</p>
				<div className="nt-ahead__row">
					<span className="nt-mono nt-muted">
						{records.length} {noun}
					</span>
					<div className="nt-actions">
						{records.length > 1 ? (
							<Button
								variant="ghost"
								size="sm"
								onClick={() => setOpenIds(allOpen ? new Set() : new Set(records.map((r) => r.id)))}
							>
								{allOpen ? 'Tutup semua' : 'Buka semua'}
							</Button>
						) : null}
						<Button
							variant="secondary"
							size="sm"
							iconLeft={<Plus size={16} aria-hidden="true" />}
							onClick={add}
						>
							Tambah {noun}
						</Button>
					</div>
				</div>
			</header>
			{live && db >= 1 ? (
				<>
					<CaptureStrip db={db} onCapture={live.onCapture} />
					<section className="nt-notes" aria-labelledby={`nt-notes-${db}`}>
						<div className="nt-notes__head">
							<h3 className="nt-group__h" id={`nt-notes-${db}`}>
								Catatan pembahasan
							</h3>
							<Checkbox
								label="Sertakan di Risalah"
								checked={live.notes.risalah}
								onChange={(e) => live.onNotes({ ...live.notes, risalah: e.target.checked })}
							/>
						</div>
						<Textarea
							rows={3}
							autoResize
							maxRows={16}
							value={live.notes.text}
							placeholder="Jalannya pembahasan agenda ini, apa adanya…"
							aria-labelledby={`nt-notes-${db}`}
							onChange={(e) => live.onNotes({ ...live.notes, text: e.target.value })}
						/>
					</section>
				</>
			) : null}
			{db === 2 ? (
				<Alert tone="info" title="Catatan angka">
					Deviasi dan progres diisi manual, bukan dihitung otomatis. Masukkan angka persen langsung:
					10 berarti 10%.
				</Alert>
			) : null}
			<div className="nt-records">
				{records.map((r, i) => (
					<RecordCard
						key={r.id}
						db={db}
						r={r}
						index={i}
						total={records.length}
						open={!!printing || openIds.has(r.id)}
						onToggle={() => toggle(r.id)}
						onChange={(nr) => setRecords(records.map((x) => (x.id === r.id ? nr : x)))}
						onDelete={() => setToDelete(r)}
					/>
				))}
				{!records.length ? (
					<div className="nt-empty">
						Belum ada {noun}. Gunakan <strong>Tambah {noun}</strong>.
					</div>
				) : null}
			</div>
			<Dialog
				open={!!toDelete}
				onClose={() => setToDelete(null)}
				title={`Hapus ${noun}?`}
				description={
					toDelete
						? `${text(toDelete.values[titleField(db).name]) || `${cap(noun)} tanpa judul`} akan dihapus dari ${a.nav}.`
						: ''
				}
				footer={
					<>
						<Button variant="ghost" onClick={() => setToDelete(null)}>
							Batal
						</Button>
						<Button variant="danger" onClick={remove}>
							Hapus
						</Button>
					</>
				}
			/>
		</section>
	);
};
