<script lang="ts">
	import type { KpiItem } from '$lib/apis/leadership';
	import { SUFFIX, fromInput, toInput } from '$lib/leadership/kpi';

	// One realisasi cell: the reader types rupiah in miliar or a percent, and the value commits on
	// blur or Enter. Text that is not a number puts the previous value back.
	export let k: KpiItem;
	export let value: number | null;
	export let onCommit: (v: number | null) => void;

	let text = toInput(k, value);
	$: text = toInput(k, value);

	const commit = () => {
		const next = fromInput(k, text);
		if (next === undefined) text = toInput(k, value);
		else onCommit(next);
	};
</script>

<span class="kd-num">
	<input
		type="text"
		inputmode="decimal"
		placeholder="—"
		aria-label="Realisasi {k.name}"
		bind:value={text}
		on:click|stopPropagation
		on:keydown|stopPropagation={(e) => {
			if (e.key === 'Enter') e.currentTarget.blur();
		}}
		on:blur={commit}
	/>
	{#if SUFFIX[k.unit]}<span class="kd-num-suffix">{SUFFIX[k.unit]}</span>{/if}
</span>
