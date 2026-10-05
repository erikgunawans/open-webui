import { useState } from 'react';
import { Alert, Button, Dialog, useToast } from '@jup/ui';
import { Plus } from 'lucide-react';

import { AGENDAS } from '../../agendas';
import { record } from '../../seed';
import { DBS, text, titleField, type NotulenRecord } from '../../types';
import { RecordCard } from './RecordCard';

// One database (Informasi Rapat or an agenda): its header, its records, add and delete.

type Props = {
	db: number;
	records: NotulenRecord[];
	setRecords: (next: NotulenRecord[]) => void;
	showTypes: boolean;
	/** Print mode: every record open, no per-record controls. */
	printing?: boolean;
	expandAll?: boolean;
};

export const AgendaView = ({ db, records, setRecords, showTypes, printing, expandAll }: Props) => {
	const { toast } = useToast();
	const a = AGENDAS[db];
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
		const r = record({}, '', 'Record baru');
		setRecords([...records, r]);
		setOpenIds(new Set([...openIds, r.id]));
		toast({ title: 'Record ditambahkan', description: a.nav, tone: 'success' });
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
		toast({ title: 'Record dihapus', tone: 'neutral' });
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
						{DBS[db].fields.length} properti · {records.length} record
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
							Tambah record
						</Button>
					</div>
				</div>
			</header>
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
						showTypes={showTypes}
						open={!!printing || openIds.has(r.id)}
						onToggle={() => toggle(r.id)}
						onChange={(nr) => setRecords(records.map((x) => (x.id === r.id ? nr : x)))}
						onDelete={() => setToDelete(r)}
					/>
				))}
				{!records.length ? (
					<div className="nt-empty">
						Belum ada record. Gunakan <strong>Tambah record</strong>.
					</div>
				) : null}
			</div>
			<Dialog
				open={!!toDelete}
				onClose={() => setToDelete(null)}
				title="Hapus record?"
				description={
					toDelete
						? `${text(toDelete.values[titleField(db).name]) || 'Record tanpa judul'} akan dihapus dari ${a.nav}.`
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
