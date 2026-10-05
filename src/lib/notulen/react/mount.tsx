import { StrictMode, type ComponentType } from 'react';
import { createRoot } from 'react-dom/client';
import { JupUIProvider, ToastProvider, type JupTheme } from '@jup/ui';
import '@jup/ui/styles.css';

// The Rapat Direksi screens are a React island inside the SvelteKit app: they are built from the
// @jup/ui React components, which this app otherwise does not use. A Svelte route page imports
// this module lazily (so React loads only on these routes) and owns the island's lifetime.
//
// The theme starts at `theme` and the reader's own choice is remembered under `storageKey`, which
// the route makes per user and per surface. `theme: 'app'` instead follows the app's own light/dark
// (the `dark` class on <html>), as the other Ruang Pimpinan tabs do: the list and the Notulen sit
// inside the app shell, so a second theme switch there would only disagree with it.

export type Island<P> = { update: (props: P) => void; destroy: () => void };

export const mountIsland = <P extends object>(
	target: HTMLElement,
	App: ComponentType<P>,
	props: P,
	options: { theme: JupTheme | 'app'; storageKey: string | null; className?: string }
): Island<P> => {
	const root = createRoot(target);
	const html = document.documentElement;
	const follow = options.theme === 'app';
	const theme = (): JupTheme =>
		options.theme === 'app' ? (html.classList.contains('dark') ? 'dark' : 'light') : options.theme;
	let current = props;
	const render = (next: P) => {
		current = next;
		root.render(
			<StrictMode>
				<JupUIProvider
					theme={theme()}
					storageKey={follow ? null : options.storageKey}
					className={options.className}
				>
					<ToastProvider placement="bottom-right">
						<App {...next} />
					</ToastProvider>
				</JupUIProvider>
			</StrictMode>
		);
	};
	render(props);
	const watch = follow ? new MutationObserver(() => render(current)) : null;
	watch?.observe(html, { attributes: true, attributeFilter: ['class'] });
	return {
		update: render,
		destroy: () => {
			watch?.disconnect();
			root.unmount();
		}
	};
};
