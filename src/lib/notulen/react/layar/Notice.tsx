import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@jup/ui';
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';

// The Layar's own confirmations. @jup/ui toasts portal to <body>, which the browser does not paint
// while the stage frame is in full screen, so the projector never saw "D-02 · Disetujui". This
// notice renders inside the full-screen frame instead, outside the scaled stage so it keeps a
// readable size in both the panel and on the projector. One at a time: a newer one replaces it.

export type NoticeTone = 'success' | 'danger' | 'warning' | 'neutral';

export type NoticeData = {
	title: string;
	description?: string;
	tone?: NoticeTone;
	/** One action, e.g. Urungkan. Keeps the notice up longer. */
	action?: { label: string; onClick: () => void };
	/** 0 keeps it until replaced or closed. */
	duration?: number;
};

type Shown = NoticeData & { id: number };

const ICON = {
	success: CheckCircle2,
	danger: XCircle,
	warning: AlertTriangle,
	neutral: Info
} as const;

export const useNotice = () => {
	const [shown, setShown] = useState<Shown | null>(null);
	const seq = useRef(0);
	const notify = useCallback((n: NoticeData) => setShown({ ...n, id: ++seq.current }), []);
	const close = useCallback(() => setShown(null), []);
	return { shown, notify, close };
};

export const Notice = ({ shown, onClose }: { shown: Shown | null; onClose: () => void }) => {
	useEffect(() => {
		if (!shown) return;
		const ms = shown.duration ?? (shown.action ? 8000 : 4000);
		if (ms === 0) return;
		const t = window.setTimeout(onClose, ms);
		return () => window.clearTimeout(t);
	}, [shown, onClose]);

	const tone = shown?.tone ?? 'neutral';
	const Icon = ICON[tone];
	// The live region stays mounted so screen readers announce each new notice.
	return (
		<div className="lr-notice-region" role="status" aria-live="polite">
			{shown ? (
				<div className={`lr-notice lr-notice--${tone}`} key={shown.id}>
					<Icon className="lr-notice__icon" aria-hidden="true" />
					<div className="lr-notice__body">
						<div className="lr-notice__title">{shown.title}</div>
						{shown.description ? <div className="lr-notice__desc">{shown.description}</div> : null}
					</div>
					{shown.action ? (
						<Button
							variant="secondary"
							size="sm"
							onClick={() => {
								shown.action?.onClick();
								onClose();
							}}
						>
							{shown.action.label}
						</Button>
					) : null}
				</div>
			) : null}
		</div>
	);
};
