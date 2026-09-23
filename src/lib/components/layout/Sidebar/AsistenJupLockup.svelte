<script lang="ts">
	// JUP: the Asisten JUP horizontal lockup (logo system "Logo Asisten JUP", panel 1a): the official
	// JUP logogram, then "Asisten" in Space Grotesk 500 and "JUP" in 700, over the "Jakarta
	// Utilitas" descriptor. The logogram is the official raster, never redrawn or recoloured. On
	// light it is full colour and "JUP" takes Polynesian Blue; on dark both go single-colour white,
	// the logo system's only permitted alternative. Live text rather than an image, so the name stays
	// sharp and follows the theme. Assets are built by deploy/gcp/brand/build-icons.ts.
	import { WEBUI_BASE_URL } from '$lib/constants';
</script>

<div class="aj-lockup">
	<img
		src="{WEBUI_BASE_URL}/static/asisten-jup-mark.png"
		alt=""
		class="aj-mark dark:hidden"
		draggable="false"
	/>
	<img
		src="{WEBUI_BASE_URL}/static/asisten-jup-mark-white.png"
		alt=""
		class="aj-mark hidden dark:block"
		draggable="false"
	/>
	<div class="aj-type">
		<span class="aj-wordmark"
			><span class="aj-asisten">Asisten</span> <span class="aj-jup">JUP</span></span
		>
		<span class="aj-tagline">Jakarta Utilitas</span>
	</div>
</div>

<style>
	.aj-lockup {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.aj-mark {
		width: 2rem;
		height: 2rem;
		flex-shrink: 0;
	}

	.aj-type {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.aj-wordmark {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 1.1875rem;
		letter-spacing: -0.025em;
		line-height: 1;
		white-space: nowrap;
		color: #011627;
	}

	.aj-asisten {
		font-weight: 500;
	}

	/* Polynesian Blue on white measures 8.70:1. */
	.aj-jup {
		font-weight: 700;
		color: #004999;
	}

	/* The logo system tracks the descriptor at 0.34em beside a 48px wordmark. At sidebar size that
	   overshoots the wordmark, so it tightens to 0.2em and sits flush under "Asisten JUP". */
	.aj-tagline {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 0.5625rem;
		font-weight: 500;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		line-height: 1;
		white-space: nowrap;
		color: #3a4a58;
	}

	:global(.dark) .aj-wordmark,
	:global(.dark) .aj-jup {
		color: #ffffff;
	}

	:global(.dark) .aj-tagline {
		color: rgba(255, 255, 255, 0.7);
	}
</style>
