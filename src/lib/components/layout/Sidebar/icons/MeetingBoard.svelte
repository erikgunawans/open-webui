<script lang="ts">
	// JUP: the Ruang Pimpinan entry. A presentation board on a stand, with a line across it: the
	// meeting room where performance is reviewed.
	export let className = 'size-4';
	export let strokeWidth = '1.5';
</script>

<svg
	class={className}
	aria-hidden="true"
	xmlns="http://www.w3.org/2000/svg"
	viewBox="0 0 24 24"
	stroke-width={strokeWidth}
	fill="none"
>
	<path d="M3 4H21V15H3Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" />
	<path d="M12 15V19" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" />
	<path
		d="M8 21L12 19L16 21"
		stroke="currentColor"
		stroke-linecap="round"
		stroke-linejoin="round"
	/>
	<path
		d="M7 11L10 8.5L13 10L17 7"
		stroke="currentColor"
		stroke-linecap="round"
		stroke-linejoin="round"
	/>
</svg>
