import { useEffect } from 'react';

// ← / PageUp = previous agenda, → / PageDown = next, 0–8 = jump. Ignored while typing in a field
// and when a modifier is held (so browser shortcuts still work).

export type AgendaKey = { step: -1 | 1 } | { jump: number };

export const agendaKey = (key: string): AgendaKey | null => {
	if (key === 'ArrowRight' || key === 'PageDown') return { step: 1 };
	if (key === 'ArrowLeft' || key === 'PageUp') return { step: -1 };
	return /^[0-8]$/.test(key) ? { jump: Number(key) } : null;
};

export const useAgendaKeys = (current: number, go: (i: number) => void) => {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			const el = e.target as HTMLElement | null;
			if (el?.closest?.('input,textarea,select,[contenteditable="true"]')) return;
			if (e.metaKey || e.ctrlKey || e.altKey) return;
			const k = agendaKey(e.key);
			if (!k) return;
			e.preventDefault();
			go('jump' in k ? k.jump : current + k.step);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [current, go]);
};
