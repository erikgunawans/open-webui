import { useRef, useState } from 'react';
import { Button, Input } from '@jup/ui';
import { Plus } from 'lucide-react';

import { kindsFor, type Capture, type CaptureKind } from '../../capture';

// Catat cepat: one line + Enter, while the discussion moves. A Butir lands in this agenda, an Usulan
// in 07, a Tindakan (with its PIC and tenggat) in 08.

const LABEL: Record<CaptureKind, string> = {
	butir: 'Butir',
	usulan: 'Usulan',
	tindakan: 'Tindakan'
};

const PLACEHOLDER: Record<CaptureKind, string> = {
	butir: 'Topik yang dibahas…',
	usulan: 'Usulan yang dimohonkan keputusan Direksi…',
	tindakan: 'Tindakan yang harus dikerjakan…'
};

const WHERE: Record<CaptureKind, string> = {
	butir: 'masuk ke agenda ini',
	usulan: 'masuk ke Agenda 07 untuk diputuskan',
	tindakan: 'masuk ke Agenda 08'
};

export const CaptureStrip = ({
	db,
	onCapture
}: {
	db: number;
	onCapture: (c: Capture) => void;
}) => {
	const kinds = kindsFor(db);
	const [kind, setKind] = useState<CaptureKind>(kinds[0]);
	const [title, setTitle] = useState('');
	const [pic, setPic] = useState('');
	const [due, setDue] = useState('');
	const first = useRef<HTMLInputElement>(null);
	if (!kinds.length) return null;

	const choose = (k: CaptureKind) => {
		setKind(k);
		first.current?.focus();
	};
	const submit = (e: React.FormEvent) => {
		e.preventDefault();
		if (!title.trim()) return;
		onCapture({ kind, from: db, title, pic, due });
		setTitle('');
		setPic('');
		setDue('');
		first.current?.focus();
	};

	return (
		<form className="nt-capture" aria-label="Catat cepat" onSubmit={submit}>
			<div className="nt-capture__kinds" role="group" aria-label="Jenis catatan">
				{kinds.map((k) => (
					<Button
						key={k}
						type="button"
						size="sm"
						variant={k === kind ? 'secondary' : 'ghost'}
						aria-pressed={k === kind}
						iconLeft={<Plus size={14} aria-hidden="true" />}
						onClick={() => choose(k)}
					>
						{LABEL[k]}
					</Button>
				))}
			</div>
			<div className="nt-capture__row">
				<Input
					ref={first}
					className="nt-capture__title"
					value={title}
					onChange={(e) => setTitle(e.target.value)}
					placeholder={PLACEHOLDER[kind]}
					aria-label={LABEL[kind]}
				/>
				{kind === 'tindakan' ? (
					<>
						<Input
							className="nt-capture__pic"
							value={pic}
							onChange={(e) => setPic(e.target.value)}
							placeholder="PIC"
							aria-label="PIC"
							block={false}
						/>
						<Input
							className="nt-capture__due"
							type="date"
							value={due}
							onChange={(e) => setDue(e.target.value)}
							aria-label="Tenggat"
							block={false}
						/>
					</>
				) : null}
				<Button type="submit" size="md" disabled={!title.trim()}>
					Catat
				</Button>
			</div>
			<p className="nt-capture__hint">
				Enter mencatat. {LABEL[kind]} {WHERE[kind]}.
			</p>
		</form>
	);
};
