<script context="module" lang="ts">
	import { writable } from 'svelte/store';

	import { getContractTitles, type ContractTitle, type ContractTitles } from '$lib/apis/contracts';

	// One request for the whole user list, however many rows mount. Cleared on failure so the next
	// mount tries again.
	const titles = writable<ContractTitles | null>(null);
	let pending: Promise<void> | null = null;

	const loadTitles = () => {
		pending ??= getContractTitles(localStorage.token)
			.then((value) => titles.set(value))
			.catch(() => {
				pending = null;
			});
		return pending;
	};

	const setHeld = (userId: string, held: ContractTitle[]) =>
		titles.update((value) =>
			value ? { ...value, users: { ...value.users, [userId]: held } } : value
		);
</script>

<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { toast } from 'svelte-sonner';

	import { setContractTitle } from '$lib/apis/contracts';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The row's user. Admin is not a title (ADR-0012); an admin can hold one like anyone else.
	export let userId: string;
	export let userName = '';

	let saving = false;

	onMount(loadTitles);

	$: held = $titles?.users[userId] ?? [];
	// Several titles means a group was edited by hand; the select shows the first, and choosing any
	// value leaves exactly one.
	$: current = held[0] ?? '';

	const change = async (event: Event) => {
		const select = event.currentTarget as HTMLSelectElement;
		const next = (select.value || null) as ContractTitle | null;
		saving = true;
		try {
			const result = await setContractTitle(localStorage.token, userId, next);
			setHeld(userId, result.titles);
			toast.success($i18n.t('Title group updated'));
		} catch {
			select.value = current;
			toast.error($i18n.t('Could not update the title group'));
		} finally {
			saving = false;
		}
	};
</script>

{#if $titles}
	<select
		class="jup-title-select bg-transparent text-xs outline-hidden"
		value={current}
		disabled={saving}
		aria-label={`${$i18n.t('Title group')}: ${userName}`}
		on:change={change}
	>
		<option value="">{$i18n.t('No title')}</option>
		{#each $titles.titles as title (title.key)}
			<option value={title.key}>{title.label}</option>
		{/each}
	</select>
	{#if held.length > 1}
		<span class="text-xs text-amber-700 dark:text-amber-400">+{held.length - 1}</span>
	{/if}
{/if}
