<script lang="ts">
	// JUP: the None-JUPe mark (logo 2a) drawn inline so the flower can move. Kembang goyang is the
	// Betawi hair ornament whose flowers sit on springs and sway ("goyang") as the wearer moves; the
	// flower here does the same once when the new-chat screen opens, and again on hover. One damped
	// sway, not a loop, and none at all under reduced motion. Geometry and colours are the design's
	// own (deploy/gcp/brand/none-jupe-mark-small.svg); only the grouping is new.
	export let className = 'size-10';

	let swaying = true;

	const replay = () => {
		swaying = false;
		// Two frames, so the class removal paints before it is added back and the animation restarts.
		requestAnimationFrame(() => requestAnimationFrame(() => (swaying = true)));
	};
</script>

<svg
	viewBox="0 0 100 100"
	class="nj-mark {className}"
	aria-hidden="true"
	focusable="false"
	on:mouseenter={replay}
>
	<path
		class="nj-bubble"
		d="M20 8 H80 Q92 8 92 20 V64 Q92 76 80 76 H40 L22 92 V76 H20 Q8 76 8 64 V20 Q8 8 20 8 Z"
		fill="none"
		stroke-width="8"
		stroke-linejoin="round"
	/>
	<g class="nj-flower" class:nj-sway={swaying} on:animationend={() => (swaying = false)}>
		<polygon points="50,16 60,26 50,36 40,26" fill="#00A550" />
		<polygon points="66,32 76,42 66,52 56,42" fill="#00A550" />
		<polygon class="nj-petal" points="50,48 60,58 50,68 40,58" />
		<polygon class="nj-petal" points="34,32 44,42 34,52 24,42" />
	</g>
</svg>

<style>
	.nj-mark {
		display: block;
		overflow: visible;
	}

	.nj-bubble {
		stroke: #004999;
	}

	.nj-petal {
		fill: #004999;
	}

	:global(.dark) .nj-bubble {
		stroke: #ffffff;
	}

	:global(.dark) .nj-petal {
		fill: #ffffff;
	}

	/* The spring sits under the flower, so the sway pivots at the lowest petal's tip. */
	.nj-flower {
		transform-box: view-box;
		transform-origin: 50px 68px;
	}

	.nj-sway {
		animation: nj-goyang 1.4s cubic-bezier(0.16, 1, 0.3, 1) both;
	}

	/* A spring settling: each swing smaller than the last, ending exactly at rest. */
	@keyframes nj-goyang {
		0% {
			transform: rotate(0deg);
		}
		18% {
			transform: rotate(-7deg);
		}
		38% {
			transform: rotate(5deg);
		}
		56% {
			transform: rotate(-3deg);
		}
		74% {
			transform: rotate(1.2deg);
		}
		100% {
			transform: rotate(0deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.nj-sway {
			animation: none;
		}
	}
</style>
