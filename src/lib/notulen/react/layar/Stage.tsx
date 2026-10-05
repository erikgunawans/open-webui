import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@jup/ui';
import { Maximize2, Minimize2 } from 'lucide-react';

// The fixed 1920×1080 stage, scaled by min(width/1920, height/1080) and centred in a 16:9 frame
// that fills the Ruang Pimpinan panel's width. "Layar penuh" (or F) puts the frame in browser full
// screen for the projector; Esc leaves it. The scale is recomputed on ResizeObserver, window
// resize, visibilitychange, and a 500ms interval (a tab loaded in the background can report 0×0
// until shown). A zero size never sets a zero scale. `overlay` renders in the frame but outside the
// scaled stage (the Layar notice), so it is part of the full-screen element at a readable size.

export const STAGE_W = 1920;
export const STAGE_H = 1080;

export const fitScale = (w: number, h: number): number | null =>
	w > 0 && h > 0 ? Math.min(w / STAGE_W, h / STAGE_H) : null;

export const Stage = ({ children, overlay }: { children: ReactNode; overlay?: ReactNode }) => {
	const [k, setK] = useState(1);
	const [full, setFull] = useState(false);
	const ref = useRef<HTMLDivElement>(null);

	const toggleFull = useCallback(() => {
		if (document.fullscreenElement) void document.exitFullscreen();
		else void ref.current?.requestFullscreen?.();
	}, []);

	useEffect(() => {
		const fit = () => {
			const el = ref.current;
			const next = fitScale(
				el?.clientWidth || window.innerWidth,
				el?.clientHeight || window.innerHeight
			);
			if (next !== null) setK((prev) => (Math.abs(prev - next) > 0.0005 ? next : prev));
		};
		const onFull = () => {
			setFull(document.fullscreenElement === ref.current);
			fit();
		};
		const onKey = (e: KeyboardEvent) => {
			const el = e.target as HTMLElement | null;
			if (el?.closest?.('input,textarea,select,[contenteditable="true"]')) return;
			if (e.metaKey || e.ctrlKey || e.altKey) return;
			if (e.key === 'f' || e.key === 'F') {
				e.preventDefault();
				toggleFull();
			}
		};
		fit();
		const ro = new ResizeObserver(fit);
		if (ref.current) ro.observe(ref.current);
		ro.observe(document.documentElement);
		const iv = window.setInterval(fit, 500);
		window.addEventListener('resize', fit);
		window.addEventListener('keydown', onKey);
		document.addEventListener('visibilitychange', fit);
		document.addEventListener('fullscreenchange', onFull);
		return () => {
			window.clearInterval(iv);
			ro.disconnect();
			window.removeEventListener('resize', fit);
			window.removeEventListener('keydown', onKey);
			document.removeEventListener('visibilitychange', fit);
			document.removeEventListener('fullscreenchange', onFull);
		};
	}, [toggleFull]);

	return (
		<div className="lr-frame">
			<div className="lr-toolbar">
				<span className="lr-toolbar__hint">
					← → atau 0–8: pindah agenda · F: layar penuh · Esc: keluar
				</span>
				<Button
					variant="secondary"
					size="sm"
					iconLeft={
						full ? (
							<Minimize2 size={16} aria-hidden="true" />
						) : (
							<Maximize2 size={16} aria-hidden="true" />
						)
					}
					onClick={toggleFull}
				>
					{full ? 'Keluar layar penuh' : 'Layar penuh'}
				</Button>
			</div>
			<div className="lr-viewport" ref={ref}>
				<div className="lr-stage" style={{ transform: `translate(-50%,-50%) scale(${k})` }}>
					{children}
				</div>
				{overlay}
			</div>
		</div>
	);
};
