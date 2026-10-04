<script lang="ts">
	// JUP: the None-JUPe horizontal lockup (logo system "Logo None-JUPe", option 2a): the kembang
	// goyang in a speech bubble, then "None-" in Space Grotesk 500 and "JUPe" in 700, over the
	// "Asisten AI" descriptor. On light, "JUP" takes Polynesian Blue and the "e" JUP green; on dark
	// the mark and the whole wordmark go single-colour white, as the design's dark panel does. Live
	// text rather than an image, so the name stays sharp and follows the theme. Assets are built by
	// deploy/gcp/brand/build-icons.ts. The descriptor row ends in the JUP endorsement (Erik,
	// 2026-10-05): JUP's own compact lockup as an image, since it must never be re-typeset.
	import { WEBUI_BASE_URL } from '$lib/constants';
</script>

<div class="nj-lockup">
	<img
		src="{WEBUI_BASE_URL}/static/none-jupe-mark.png"
		alt=""
		class="nj-mark dark:hidden"
		draggable="false"
	/>
	<img
		src="{WEBUI_BASE_URL}/static/none-jupe-mark-white.png"
		alt=""
		class="nj-mark hidden dark:block"
		draggable="false"
	/>
	<div class="nj-type">
		<span class="nj-wordmark"
			><span class="nj-none">None-</span><span class="nj-jup">JUP</span><span class="nj-e">e</span
			></span
		>
		<span class="nj-descriptor">
			<span class="nj-tagline">Asisten AI</span>
			<img
				src="{WEBUI_BASE_URL}/static/jup-endorsement.png"
				alt="JUP"
				class="nj-endorsement dark:hidden"
				draggable="false"
			/>
			<img
				src="{WEBUI_BASE_URL}/static/jup-endorsement-white.png"
				alt="JUP"
				class="nj-endorsement hidden dark:block"
				draggable="false"
			/>
		</span>
	</div>
</div>

<style>
	/* Sized up 2026-09-29 (Erik): 40px mark, 24px wordmark. It fits the 245px panel beside the
	   collapse button with room to spare (mark + gap + wordmark = 40 + 12 + ~124px). */
	.nj-lockup {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.nj-mark {
		width: 2.5rem;
		height: 2.5rem;
		flex-shrink: 0;
	}

	.nj-type {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.nj-wordmark {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 1.5rem;
		letter-spacing: -0.025em;
		line-height: 1;
		white-space: nowrap;
		color: #011627;
	}

	.nj-none {
		font-weight: 500;
	}

	/* Polynesian Blue on white measures 8.70:1. */
	.nj-jup {
		font-weight: 700;
		color: #004999;
	}

	/* The design's text green, not the #00A550 fill in the mark. 4.45:1 on white and 3.93:1 on the
	   sidebar paper (measured 2026-09-29), which clears the 3:1 large-text bar: the wordmark is
	   24px bold, and it is a logo. */
	.nj-e {
		font-weight: 700;
		color: #008a43;
	}

	/* The logo system tracks the descriptor at 0.34em beside a 48px wordmark. At sidebar size that
	   overshoots the wordmark, so it tightens to 0.24em and sits flush under "None-JUPe". */
	.nj-tagline {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.24em;
		text-transform: uppercase;
		line-height: 1;
		white-space: nowrap;
		color: #3a4a58;
	}

	.nj-descriptor {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	/* 14px is the JUP logogram's minimum on screen (JUP Design System, DESIGN.md). */
	.nj-endorsement {
		height: 0.875rem;
		width: auto;
		flex-shrink: 0;
	}

	:global(.dark) .nj-wordmark,
	:global(.dark) .nj-jup {
		color: #ffffff;
	}

	/* The "e" keeps the wordmark's one green in dark: green-300, 8.17:1 on the dark paper. */
	:global(.dark) .nj-e {
		color: var(--jup-brand-text, #4ac287);
	}

	:global(.dark) .nj-tagline {
		color: rgba(255, 255, 255, 0.7);
	}
</style>
