<script lang="ts">
	// JUP: the BangJayaOS lockup (BangJayaOS Brand Guidelines, "Lockup"): mark, a 1px divider,
	// then the logotype and tagline, set flat. The mark keeps JUP's identity colours in both
	// themes — Pigment Green outer, Polynesian Blue inner — so only the type and divider invert.
	// Live text rather than an image, so it stays sharp and follows the theme.
	import { WEBUI_BASE_URL } from '$lib/constants';
</script>

<div class="bj-lockup">
	<img src="{WEBUI_BASE_URL}/static/bangjayaos-mark.svg" alt="" class="bj-mark" draggable="false" />
	<span class="bj-divider" aria-hidden="true"></span>
	<div class="bj-type">
		<span class="bj-wordmark">BangJaya<span class="bj-os">OS</span></span>
		<span class="bj-tagline">Enterprise Agentic OS</span>
	</div>
</div>

<style>
	.bj-lockup {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	.bj-mark {
		width: 2rem;
		height: 2rem;
		flex-shrink: 0;
	}

	.bj-divider {
		width: 1px;
		height: 1.75rem;
		background: #ced4da;
	}

	.bj-type {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	/* 19px bold is large text under WCAG, so the guideline's #008A43 needs 3:1, not 4.5:1. */
	.bj-wordmark {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 1.1875rem;
		font-weight: 700;
		letter-spacing: -0.02em;
		line-height: 1;
		color: #011627;
	}

	.bj-os {
		color: #008a43;
	}

	.bj-tagline {
		font-family: 'Space Grotesk', sans-serif;
		font-size: 0.5625rem;
		font-weight: 500;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		line-height: 1;
		color: #536679;
	}

	:global(.dark) .bj-divider {
		background: rgba(255, 255, 255, 0.24);
	}

	:global(.dark) .bj-wordmark {
		color: #ffffff;
	}

	:global(.dark) .bj-os {
		color: #4ac287;
	}

	:global(.dark) .bj-tagline {
		color: rgba(255, 255, 255, 0.76);
	}
</style>
