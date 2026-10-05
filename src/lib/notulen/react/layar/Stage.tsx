import { useEffect, useRef, useState, type ReactNode } from 'react';

// The fixed 1920×1080 stage, scaled by min(width/1920, height/1080) and centred. The scale is
// recomputed on ResizeObserver, window resize, visibilitychange, and a 500ms interval (a tab
// loaded in the background can report 0×0 until shown). A zero size never sets a zero scale.

export const STAGE_W = 1920;
export const STAGE_H = 1080;

export const fitScale = (w: number, h: number): number | null =>
	w > 0 && h > 0 ? Math.min(w / STAGE_W, h / STAGE_H) : null;

export const Stage = ({ children }: { children: ReactNode }) => {
	const [k, setK] = useState(1);
	const ref = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const fit = () => {
			const el = ref.current;
			const next = fitScale(
				el?.clientWidth || window.innerWidth,
				el?.clientHeight || window.innerHeight
			);
			if (next !== null) setK((prev) => (Math.abs(prev - next) > 0.0005 ? next : prev));
		};
		fit();
		const ro = new ResizeObserver(fit);
		if (ref.current) ro.observe(ref.current);
		ro.observe(document.documentElement);
		const iv = window.setInterval(fit, 500);
		window.addEventListener('resize', fit);
		document.addEventListener('visibilitychange', fit);
		return () => {
			window.clearInterval(iv);
			ro.disconnect();
			window.removeEventListener('resize', fit);
			document.removeEventListener('visibilitychange', fit);
		};
	}, []);

	return (
		<div className="lr-viewport" ref={ref}>
			<div className="lr-stage" style={{ transform: `translate(-50%,-50%) scale(${k})` }}>
				{children}
			</div>
		</div>
	);
};
