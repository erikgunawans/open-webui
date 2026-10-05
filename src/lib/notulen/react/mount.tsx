import { StrictMode, type ComponentType } from 'react';
import { createRoot } from 'react-dom/client';
import { JupUIProvider, ToastProvider, type JupTheme } from '@jup/ui';
import '@jup/ui/styles.css';

// The Rapat Direksi screens are a React island inside the SvelteKit app: they are built from the
// @jup/ui React components, which this app otherwise does not use. A Svelte route page imports
// this module lazily (so React loads only on these routes) and owns the island's lifetime.
//
// The theme starts at `theme` and the reader's own choice is remembered under `storageKey`, which
// the route makes per user and per surface (Notulen and Layar are toggled separately).

export type Island<P> = { update: (props: P) => void; destroy: () => void };

export const mountIsland = <P extends object>(
	target: HTMLElement,
	App: ComponentType<P>,
	props: P,
	options: { theme: JupTheme; storageKey: string; className?: string }
): Island<P> => {
	const root = createRoot(target);
	const render = (next: P) =>
		root.render(
			<StrictMode>
				<JupUIProvider
					theme={options.theme}
					storageKey={options.storageKey}
					className={options.className}
				>
					<ToastProvider placement="bottom-right">
						<App {...next} />
					</ToastProvider>
				</JupUIProvider>
			</StrictMode>
		);
	render(props);
	return { update: render, destroy: () => root.unmount() };
};
