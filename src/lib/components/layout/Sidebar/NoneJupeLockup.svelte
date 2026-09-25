<script lang="ts">
	// JUP: the None-JUPe horizontal lockup (logo system "Logo None-JUPe", option 2a): the kembang
	// goyang in a speech bubble, then "None-" in Space Grotesk 500 and "JUPe" in 700, over the
	// "Asisten AI" descriptor. On light, "JUP" takes Polynesian Blue and the "e" JUP green; on dark
	// the mark and the whole wordmark go single-colour white, as the design's dark panel does. Live
	// text rather than an image, so the name stays sharp and follows the theme. Assets are built by
	// deploy/gcp/brand/build-icons.ts.
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
		<span class="nj-tagline">Asisten AI</span>
	</div>
</div>

<style>
	.nj-lockup {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.nj-mark {
		width: 2rem;
		height: 2rem;
		flex-shrink: 0;
	}

	.nj-type {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.nj-wordmark {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 1.1875rem;
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

	/* The design's text green, not the #00A550 fill in the mark. 4.45:1 on white, which clears
	   the 3:1 large-text bar: the wordmark is 19px bold, and it is a logo. */
	.nj-e {
		font-weight: 700;
		color: #008a43;
	}

	/* The logo system tracks the descriptor at 0.34em beside a 48px wordmark. At sidebar size that
	   overshoots the wordmark, so it tightens to 0.2em and sits flush under "None-JUPe". */
	.nj-tagline {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 0.5625rem;
		font-weight: 500;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		line-height: 1;
		white-space: nowrap;
		color: #3a4a58;
	}

	:global(.dark) .nj-wordmark,
	:global(.dark) .nj-jup,
	:global(.dark) .nj-e {
		color: #ffffff;
	}

	:global(.dark) .nj-tagline {
		color: rgba(255, 255, 255, 0.7);
	}
</style>
