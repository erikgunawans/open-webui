import adapter from '@sveltejs/adapter-static';
import * as child_process from 'node:child_process';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import fs from 'node:fs';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://kit.svelte.dev/docs/integrations#preprocessors
	// for more information about preprocessors
	preprocess: vitePreprocess(),
	kit: {
		// adapter-auto only supports some environments, see https://kit.svelte.dev/docs/adapter-auto for a list.
		// If your environment is not supported or you settled on a specific environment, switch out the adapter.
		// See https://kit.svelte.dev/docs/adapters for more information about adapters.
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html'
		}),
		// poll for new version name every 60 seconds (to trigger reload mechanic in +layout.svelte)
		version: {
			name: (() => {
				// JUP: the image build has no .git (.dockerignore), so `git rev-parse` failed and every
				// deploy shipped the package.json version — the same name each time. `updated` never
				// fired, and a tab opened before a deploy hit "500: Internal Error" on its next
				// navigation (its old chunks are gone). deploy.sh builds with `gcloud builds submit --tag`,
				// which passes no build args (APP_BUILD_HASH stays 'dev-build'), so it writes the commit
				// to .build-hash for the build instead; APP_BUILD_HASH covers a build that does pass it.
				try {
					const fromDeploy = fs
						.readFileSync(new URL('./.build-hash', import.meta.url), 'utf8')
						.trim();
					if (fromDeploy) return fromDeploy;
				} catch {
					// not a deploy build
				}
				const buildHash = process.env.APP_BUILD_HASH;
				if (buildHash && buildHash !== 'dev-build') return buildHash;
				try {
					return child_process.execSync('git rev-parse HEAD').toString().trim();
				} catch {
					// if git is not available, fallback to package.json version
					// or current timestamp
					try {
						return (
							JSON.parse(fs.readFileSync(new URL('./package.json', import.meta.url), 'utf8'))
								?.version || Date.now().toString()
						);
					} catch {
						return Date.now().toString();
					}
				}
			})(),
			pollInterval: 60000
		}
	},
	vitePlugin: {
		// inspector: {
		// 	toggleKeyCombo: 'meta-shift', // Key combination to open the inspector
		// 	holdMode: false, // Enable or disable hold mode
		// 	showToggleButton: 'always', // Show toggle button ('always', 'active', 'never')
		// 	toggleButtonPos: 'bottom-right' // Position of the toggle button
		// }
	},
	onwarn: (warning, handler) => {
		const { code } = warning;
		if (code === 'css-unused-selector') return;

		handler(warning);
	}
};

export default config;
