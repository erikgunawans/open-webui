<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import {
		approveContract,
		contractPdfUrl,
		ContractsRequestError,
		editContractField,
		getContractQueue,
		getContractReview,
		getContractReviewPages,
		linkContract,
		returnContract,
		setContractDates,
		setContractParties,
		setContractUnits,
		unlinkContract,
		type ContractDetail,
		type ContractField,
		type ContractFlag,
		type ContractPage,
		type ContractQueue,
		type ContractState,
		type ContractSummary
	} from '$lib/apis/contracts';
	import { formatEventTimeId } from '$lib/leadership/format';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The server decides everything here (backend/jup/contracts/review.py): the `review` grant, the
	// version every change is made against, the hash approve checks. This screen only shows the card
	// and sends what Legal changed; a refusal comes back with a stable code.

	const PAGE_SIZE = 25;
	const STATES: ContractState[] = ['draft', 'approved', 'returned'];
	const REASON_MAX = 2000;
	const FIELDS = [
		'mitra',
		'nomor_pks',
		'judul',
		'tanggal_tanda_tangan',
		'jenis_dokumen',
		'hak_kewajiban_lingkup',
		'nilai_dan_pembayaran',
		'jangka_waktu_perpanjangan',
		'pengakhiran',
		'wanprestasi_ganti_rugi',
		'kerahasiaan_hki',
		'keadaan_kahar',
		'penyelesaian_sengketa',
		'keabsahan',
		'hubungan_dokumen'
	] as const;

	let LABEL: Record<string, string>;
	$: LABEL = {
		mitra: $i18n.t('Partner'),
		nomor_pks: $i18n.t('Contract number'),
		judul: $i18n.t('Title'),
		tanggal_tanda_tangan: $i18n.t('Signing date'),
		jenis_dokumen: $i18n.t('Document type'),
		hak_kewajiban_lingkup: $i18n.t('Rights, obligations and scope'),
		nilai_dan_pembayaran: $i18n.t('Value and payment'),
		jangka_waktu_perpanjangan: $i18n.t('Term and renewal'),
		pengakhiran: $i18n.t('Termination'),
		wanprestasi_ganti_rugi: $i18n.t('Breach and damages'),
		kerahasiaan_hki: $i18n.t('Confidentiality and IP'),
		keadaan_kahar: $i18n.t('Force majeure'),
		penyelesaian_sengketa: $i18n.t('Dispute resolution'),
		keabsahan: $i18n.t('Validity'),
		hubungan_dokumen: $i18n.t('Relation to other documents')
	};

	let STATE_LABEL: Record<ContractState, string>;
	$: STATE_LABEL = {
		draft: $i18n.t('Draft, not yet reviewed'),
		approved: $i18n.t('Approved by Legal'),
		returned: $i18n.t('Returned for correction')
	};

	let EVENT_LABEL: Record<string, string>;
	$: EVENT_LABEL = {
		imported: $i18n.t('Imported'),
		redrafted: $i18n.t('Redrafted'),
		redraft_held: $i18n.t('New draft held beside the reviewed card'),
		field_edited: $i18n.t('Field edited'),
		approved: $i18n.t('Approved'),
		returned: $i18n.t('Returned'),
		units_set: $i18n.t('Units set'),
		dates_set: $i18n.t('Dates read from the card'),
		dates_edited: $i18n.t('Dates edited'),
		parties_set: $i18n.t('Individuals corrected'),
		link_added: $i18n.t('Link added'),
		link_removed: $i18n.t('Link removed')
	};

	let ERROR_TEXT: Record<string, string>;
	$: ERROR_TEXT = {
		review_required: $i18n.t('Reviewing contract cards needs the review grant (Legal).'),
		names_required: $i18n.t('Correcting the individuals needs the names grant.'),
		conflict: $i18n.t(
			'This card changed since it was opened. It has been reloaded; redo the change.'
		),
		not_found: $i18n.t('The contract was not found.'),
		pages_not_found: $i18n.t('The OCR text of this contract is not available.'),
		schema_not_ready: $i18n.t('The contract tables are not ready. Report it to an admin.')
	};

	const errorText = (error: unknown) => {
		if (error instanceof ContractsRequestError) {
			return (error.code && ERROR_TEXT[error.code]) || error.message;
		}
		return error instanceof Error ? error.message : `${error ?? ''}`;
	};

	// --- Queue ------------------------------------------------------------------------------------

	let flag: ContractFlag | undefined = undefined;
	let stateFilter: ContractState | undefined = undefined;
	let q = '';
	let offset = 0;
	let queue: ContractQueue | null = null;
	let loading = true;
	let loadProblem: unknown = null;
	let queueController: AbortController | null = null;

	const load = async () => {
		queueController?.abort();
		const own = new AbortController();
		queueController = own;
		loading = true;
		try {
			const result = await getContractQueue(
				localStorage.token,
				{ flag, state: stateFilter, q: q.trim() || undefined, limit: PAGE_SIZE, offset },
				own.signal
			);
			if (own.signal.aborted) return;
			queue = result;
			loadProblem = null;
		} catch (caught) {
			if (!own.signal.aborted) loadProblem = caught;
		} finally {
			if (!own.signal.aborted) loading = false;
		}
	};

	onMount(load);

	const setFlag = (value: ContractFlag | undefined) => {
		flag = value;
		offset = 0;
		load();
	};

	const setState = (value: ContractState | undefined) => {
		stateFilter = value;
		offset = 0;
		load();
	};

	const search = () => {
		offset = 0;
		load();
	};

	const page = (step: number) => {
		offset = Math.max(0, offset + step * PAGE_SIZE);
		load();
	};

	const reference = (item: { run: string; number: string }) =>
		item.run === 'full' ? item.number : `${item.run}-${item.number}`;

	// --- One card ---------------------------------------------------------------------------------

	let show = false;
	let detail: ContractDetail | null = null;
	let pages: ContractPage[] = [];
	let pagesProblem: unknown = null;
	let opening = false;
	let problem: unknown = null;
	let busy = false;
	let openId: string | null = null;

	const reload = async () => {
		if (!openId) return;
		detail = await getContractReview(localStorage.token, openId);
	};

	const open = async (item: ContractSummary) => {
		openId = item.id;
		detail = null;
		pages = [];
		pagesProblem = null;
		problem = null;
		editing = null;
		returning = false;
		show = true;
		opening = true;
		try {
			await reload();
			resetForms();
		} catch (caught) {
			problem = caught;
		} finally {
			opening = false;
		}
		try {
			pages = (await getContractReviewPages(localStorage.token, item.id)).pages;
		} catch (caught) {
			pagesProblem = caught;
		}
	};

	$: if (!show && openId) {
		openId = null;
		load();
	}

	// Every write: send, then re-read the card so the version and hash are the server's. A conflict
	// re-reads too, so the reviewer sees what changed before redoing it.
	const write = async (call: (version: number) => Promise<unknown>) => {
		if (!detail) return false;
		problem = null;
		busy = true;
		try {
			await call(detail.contract.version);
			await reload();
			resetForms();
			return true;
		} catch (caught) {
			problem = caught;
			if (caught instanceof ContractsRequestError && caught.code === 'conflict') {
				await reload().catch(() => undefined);
				resetForms();
			}
			return false;
		} finally {
			busy = false;
		}
	};

	const field = (name: string): ContractField | null => {
		const value = detail?.card?.[name];
		return value && !Array.isArray(value) ? (value as ContractField) : null;
	};

	// Field edit.
	let editing: string | null = null;
	let editText = '';
	let editPages = '';

	const startEdit = (name: string) => {
		const current = field(name);
		editing = name;
		editText = current?.isi ?? '';
		editPages = (current?.halaman ?? []).join(', ');
	};

	const parsePages = (text: string) =>
		text
			.split(/[,\s]+/)
			.filter(Boolean)
			.map((part) => Number(part))
			.filter((n) => Number.isInteger(n));

	const saveEdit = async () => {
		if (!detail || !editing) return;
		const name = editing;
		const done = await write((version) =>
			editContractField(localStorage.token, detail!.contract.id, {
				version,
				field: name,
				text: editText,
				pages: parsePages(editPages)
			})
		);
		if (done) editing = null;
	};

	// Approve and return.
	let returning = false;
	let reason = '';

	const approve = () =>
		write((version) =>
			approveContract(localStorage.token, detail!.contract.id, version, detail!.card_sha256 ?? '')
		);

	const sendBack = async () => {
		if (!reason.trim()) {
			problem = $i18n.t('Returning a card needs a reason.');
			return;
		}
		const done = await write((version) =>
			returnContract(localStorage.token, detail!.contract.id, version, reason.trim())
		);
		if (done) {
			returning = false;
			reason = '';
		}
	};

	// Dates, units, individuals, links: each its own small form, reset from the card after a write.
	let start = '';
	let end = '';
	let renewal: 'unknown' | 'yes' | 'no' = 'unknown';
	let units = '';
	let names = '';
	let linkRef = '';
	let linkKind: 'addendum' | 'related' = 'addendum';

	const resetForms = () => {
		if (!detail) return;
		start = detail.contract.start_date ?? '';
		end = detail.contract.end_date ?? '';
		renewal =
			detail.contract.auto_renewal === null
				? 'unknown'
				: detail.contract.auto_renewal
					? 'yes'
					: 'no';
		units = detail.contract.units.join(', ');
		names = detail.parties.map((p) => p.name ?? '').join('\n');
	};

	const saveDates = () =>
		write((version) =>
			setContractDates(localStorage.token, detail!.contract.id, {
				version,
				start: start || null,
				end: end || null,
				auto_renewal: renewal === 'unknown' ? null : renewal === 'yes'
			})
		);

	const saveUnits = () =>
		write((version) =>
			setContractUnits(
				localStorage.token,
				detail!.contract.id,
				version,
				units
					.split(',')
					.map((u) => u.trim().toLowerCase())
					.filter(Boolean)
			)
		);

	const saveNames = () =>
		write((version) =>
			setContractParties(
				localStorage.token,
				detail!.contract.id,
				version,
				names
					.split('\n')
					.map((n) => n.trim())
					.filter(Boolean)
			)
		);

	const addLink = async () => {
		if (!detail || !linkRef.trim()) return;
		problem = null;
		let target: ContractSummary | undefined;
		try {
			const found = await getContractQueue(localStorage.token, { q: linkRef.trim(), limit: 10 });
			const wanted = linkRef.trim().replace(/^0+/, '');
			target = found.items.find(
				(item) => item.number.replace(/^0+/, '') === wanted || reference(item) === linkRef.trim()
			);
		} catch (caught) {
			problem = caught;
			return;
		}
		if (!target) {
			problem = $i18n.t('No contract with number {{ref}}.', { ref: linkRef.trim() });
			return;
		}
		const related = target.id;
		const done = await write((version) =>
			linkContract(localStorage.token, detail!.contract.id, version, related, linkKind)
		);
		if (done) linkRef = '';
	};

	const removeLink = (relatedId: string) =>
		write((version) => unlinkContract(localStorage.token, detail!.contract.id, relatedId, version));

	$: hasNames = !!detail && detail.parties.every((p) => p.name !== null);
</script>

<section class="jlp-surface mt-4" aria-labelledby="kk-title">
	<h2 id="kk-title" class="jlp-surface-title">{$i18n.t('Contract cards')}</h2>
	<p class="jlp-meta">
		{$i18n.t(
			'Cards drafted from SCAN PERJANJIAN. Open one to check it against its pages, correct fields, then approve it or return it with a reason. Asisten JUP answers from every card and says whether Legal approved it.'
		)}
	</p>

	<div class="jlp-row-buttons mt-2" role="group" aria-label={$i18n.t('Filter cards')}>
		<button type="button" class="jlp-link" aria-pressed={!flag} on:click={() => setFlag(undefined)}
			>{$i18n.t('All')}{#if queue}&nbsp;({(queue.counts.draft ?? 0) +
					(queue.counts.approved ?? 0) +
					(queue.counts.returned ?? 0)}){/if}</button
		>
		<button
			type="button"
			class="jlp-link"
			aria-pressed={flag === 'perorangan'}
			on:click={() => setFlag('perorangan')}
			>{$i18n.t('Individuals')}{#if queue}&nbsp;({queue.counts.perorangan}){/if}</button
		>
		<button
			type="button"
			class="jlp-link"
			aria-pressed={flag === 'manual'}
			on:click={() => setFlag('manual')}
			>{$i18n.t('Manual check')}{#if queue}&nbsp;({queue.counts.manual}){/if}</button
		>
		<button
			type="button"
			class="jlp-link"
			aria-pressed={flag === 'low_ocr'}
			on:click={() => setFlag('low_ocr')}
			>{$i18n.t('Low OCR confidence')}{#if queue}&nbsp;({queue.counts.low_ocr}){/if}</button
		>
	</div>

	<div class="jlp-row-buttons mt-1" role="group" aria-label={$i18n.t('Filter by state')}>
		<button
			type="button"
			class="jlp-link"
			aria-pressed={!stateFilter}
			on:click={() => setState(undefined)}>{$i18n.t('Every state')}</button
		>
		{#each STATES as value (value)}
			<button
				type="button"
				class="jlp-link"
				aria-pressed={stateFilter === value}
				on:click={() => setState(value)}
				>{STATE_LABEL[value]}{#if queue}&nbsp;({queue.counts[value]}){/if}</button
			>
		{/each}
	</div>

	<form class="jlp-form mt-2" role="search" on:submit|preventDefault={search}>
		<label class="jlp-field">
			<span>{$i18n.t('Search partner, number or title')}</span>
			<input type="text" bind:value={q} maxlength="200" />
		</label>
	</form>

	{#if loading && !queue}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if loadProblem}
		<p class="jlp-notice jlp-notice-refused mt-2">{errorText(loadProblem)}</p>
	{:else if queue && queue.items.length === 0}
		<p class="jlp-meta mt-2">{$i18n.t('No cards match.')}</p>
	{:else if queue}
		<ul class="jlp-mini-list mt-2" aria-busy={loading}>
			{#each queue.items as item (item.id)}
				<li class="jlp-mini">
					<strong>[{reference(item)}] {item.partner ?? '—'}</strong>
					<span class="jlp-meta jlp-block">{item.title ?? '—'} · {item.contract_number ?? '—'}</span
					>
					<span class="jlp-status">{STATE_LABEL[item.state]}</span>
					<span class="jlp-meta">
						{#if item.individuals}· {$i18n.t('{{count}} individuals', {
								count: item.individuals
							})}{/if}
						{#if item.manual_pages}· {$i18n.t('{{count}} pages to check by hand', {
								count: item.manual_pages
							})}{/if}
						{#if item.low_ocr_pages}· {$i18n.t('{{count}} low-confidence OCR pages', {
								count: item.low_ocr_pages
							})}{/if}
					</span>
					<button
						type="button"
						class="jlp-link"
						aria-label={$i18n.t('Open card {{ref}}', { ref: reference(item) })}
						on:click={() => open(item)}>{$i18n.t('Open')}</button
					>
				</li>
			{/each}
		</ul>
		<div class="jlp-row-buttons mt-2">
			<span class="jlp-meta"
				>{$i18n.t('{{from}}–{{to}} of {{total}}', {
					from: queue.offset + 1,
					to: queue.offset + queue.items.length,
					total: queue.total
				})}</span
			>
			<button type="button" class="jlp-link" disabled={offset === 0} on:click={() => page(-1)}
				>{$i18n.t('Previous')}</button
			>
			<button
				type="button"
				class="jlp-link"
				disabled={queue.offset + queue.items.length >= queue.total}
				on:click={() => page(1)}>{$i18n.t('Next')}</button
			>
		</div>
	{/if}
</section>

<Modal size="full" bind:show ariaLabelledby="kk-detail-title">
	<div class="jlp-root jlp-dialog" role="document">
		<div class="jlp-dialog-head">
			<h2 class="jlp-dialog-title" id="kk-detail-title">
				{#if detail}[{reference(detail.contract)}] {detail.contract.partner ?? '—'}{:else}{$i18n.t(
						'Contract card'
					)}{/if}
			</h2>
			<button type="button" class="jlp-link" on:click={() => (show = false)}
				>{$i18n.t('Close')}</button
			>
		</div>

		<div aria-live="polite">
			{#if problem}
				<p class="jlp-notice jlp-notice-refused mt-2">{errorText(problem)}</p>
			{/if}
		</div>

		{#if opening}
			<div class="flex justify-center py-6"><Spinner className="size-5" /></div>
		{:else if detail}
			<div class="mt-2 flex flex-wrap items-center gap-2">
				<span class="jlp-status">{STATE_LABEL[detail.contract.state]}</span>
				<span class="jlp-meta"
					>{$i18n.t('Version {{version}}', { version: detail.contract.version })} · {$i18n.t(
						'{{count}} pages',
						{ count: detail.contract.page_count }
					)}</span
				>
				<a
					class="jlp-link"
					href={contractPdfUrl(detail.contract.run, detail.contract.number)}
					target="_blank"
					rel="noopener">{$i18n.t('Open the PDF')}</a
				>
			</div>
			{#if detail.draft_card}
				<p class="jlp-notice mt-2">
					{$i18n.t(
						'A later drafting run produced a different card. It is kept beside this one; the reviewed card is unchanged.'
					)}
				</p>
			{/if}

			<div class="mt-3 grid gap-4 lg:grid-cols-2">
				<div>
					<h3 class="jlp-group-title">{$i18n.t('Card')}</h3>
					<dl class="jlp-dl">
						{#each FIELDS as name (name)}
							<dt>{LABEL[name]}</dt>
							<dd>
								{#if editing === name}
									<form class="jlp-form" on:submit|preventDefault={saveEdit}>
										<label class="jlp-field">
											<span class="sr-only">{LABEL[name]}</span>
											<textarea rows="4" bind:value={editText} required></textarea>
										</label>
										<label class="jlp-field">
											<span>{$i18n.t('Pages (e.g. 2, 3)')}</span>
											<input type="text" bind:value={editPages} />
										</label>
										<span class="jlp-row-buttons">
											<button type="submit" class="jlp-button" disabled={busy}
												>{$i18n.t('Save')}</button
											>
											<button
												type="button"
												class="jlp-link"
												disabled={busy}
												on:click={() => (editing = null)}>{$i18n.t('Cancel')}</button
											>
										</span>
									</form>
								{:else}
									<span class="whitespace-pre-wrap">{field(name)?.isi ?? '—'}</span>
									{#if field(name)?.halaman?.length}
										<span class="jlp-meta"
											>({$i18n.t('p. {{pages}}', {
												pages: field(name)?.halaman.join(', ')
											})})</span
										>
									{/if}
									<button
										type="button"
										class="jlp-link"
										disabled={busy || editing !== null}
										aria-label={$i18n.t('Edit {{field}}', { field: LABEL[name] })}
										on:click={() => startEdit(name)}>{$i18n.t('Edit')}</button
									>
								{/if}
							</dd>
						{/each}
					</dl>
				</div>

				<div>
					<h3 class="jlp-group-title" id="kk-pages-title">{$i18n.t('OCR pages')}</h3>
					{#if pagesProblem}
						<p class="jlp-notice jlp-notice-refused mt-1">{errorText(pagesProblem)}</p>
					{:else if pages.length === 0}
						<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
					{:else}
						<div
							class="max-h-[70vh] overflow-auto"
							tabindex="0"
							role="region"
							aria-labelledby="kk-pages-title"
						>
							{#each pages as page (page.halaman)}
								<h4 class="jlp-meta mt-2 font-medium">
									{$i18n.t('Page {{n}}', { n: page.halaman })}
									{#if page.ocr_rendah}<span class="jlp-negative"
											>· {$i18n.t('low OCR confidence')}</span
										>{/if}
									{#if detail.contract.manual_check_pages.includes(page.halaman)}<span
											class="jlp-negative">· {$i18n.t('check by hand')}</span
										>{/if}
								</h4>
								<pre class="jlp-meta whitespace-pre-wrap">{page.teks}</pre>
							{/each}
						</div>
					{/if}
				</div>
			</div>

			<div class="mt-4 grid gap-4 lg:grid-cols-2">
				<form class="jlp-form" on:submit|preventDefault={saveDates}>
					<h3 class="jlp-group-title">{$i18n.t('Dates')}</h3>
					<label class="jlp-field">
						<span>{$i18n.t('Start')}</span>
						<input type="date" bind:value={start} />
					</label>
					<label class="jlp-field">
						<span>{$i18n.t('End')}</span>
						<input type="date" bind:value={end} />
					</label>
					<label class="jlp-field">
						<span>{$i18n.t('Automatic renewal')}</span>
						<select bind:value={renewal}>
							<option value="unknown">{$i18n.t('Unknown')}</option>
							<option value="yes">{$i18n.t('Yes')}</option>
							<option value="no">{$i18n.t('No')}</option>
						</select>
					</label>
					<button type="submit" class="jlp-button" disabled={busy}>{$i18n.t('Save dates')}</button>
				</form>

				<form class="jlp-form" on:submit|preventDefault={saveUnits}>
					<h3 class="jlp-group-title">{$i18n.t('Units')}</h3>
					<label class="jlp-field">
						<span>{$i18n.t('Unit codes, separated by commas')}</span>
						<input type="text" bind:value={units} />
					</label>
					<button type="submit" class="jlp-button" disabled={busy}>{$i18n.t('Save units')}</button>
				</form>

				<form class="jlp-form" on:submit|preventDefault={saveNames}>
					<h3 class="jlp-group-title">{$i18n.t('Individuals (masked in answers)')}</h3>
					{#if hasNames}
						<label class="jlp-field">
							<span>{$i18n.t('One name per line. Company signatories are not listed here.')}</span>
							<textarea rows="4" bind:value={names}></textarea>
						</label>
						<span class="jlp-meta"
							>{detail.parties.map((p) => `${p.code}: ${p.name}`).join(' · ') || '—'}</span
						>
						<button type="submit" class="jlp-button" disabled={busy}
							>{$i18n.t('Save individuals')}</button
						>
					{:else}
						<span class="jlp-meta">{detail.parties.map((p) => p.code).join(', ') || '—'}</span>
					{/if}
				</form>

				<form class="jlp-form" on:submit|preventDefault={addLink}>
					<h3 class="jlp-group-title">{$i18n.t('Linked documents')}</h3>
					{#if detail.links.length}
						<ul class="jlp-mini-list">
							{#each detail.links as linked (linked.id)}
								<li class="jlp-mini">
									[{reference(linked)}] {linked.title ?? '—'}
									<span class="jlp-meta"
										>· {linked.kind === 'addendum'
											? $i18n.t('addendum')
											: $i18n.t('related')}{linked.direction === 'main'
											? ` · ${$i18n.t('this card is linked from it')}`
											: ''}</span
									>
									{#if linked.direction === 'related'}
										<button
											type="button"
											class="jlp-link"
											disabled={busy}
											on:click={() => removeLink(linked.id)}>{$i18n.t('Remove')}</button
										>
									{/if}
								</li>
							{/each}
						</ul>
					{/if}
					<label class="jlp-field">
						<span>{$i18n.t('Card number to link')}</span>
						<input type="text" bind:value={linkRef} />
					</label>
					<label class="jlp-field">
						<span>{$i18n.t('Kind')}</span>
						<select bind:value={linkKind}>
							<option value="addendum">{$i18n.t('addendum')}</option>
							<option value="related">{$i18n.t('related')}</option>
						</select>
					</label>
					<button type="submit" class="jlp-button" disabled={busy}>{$i18n.t('Add link')}</button>
				</form>
			</div>

			<h3 class="jlp-group-title mt-4">{$i18n.t('History')}</h3>
			<ul class="jlp-mini-list">
				{#each [...detail.events].reverse() as event (event.id)}
					<li class="jlp-mini">
						{EVENT_LABEL[event.kind] ?? event.kind}
						{#if event.kind === 'field_edited' && typeof event.payload.field === 'string'}
							· {LABEL[event.payload.field] ?? event.payload.field}{/if}
						<span class="jlp-meta jlp-block"
							>v{event.version} · {formatEventTimeId(event.at)}{#if event.reason}
								· {event.reason}{/if}</span
						>
					</li>
				{/each}
			</ul>

			<div class="mt-4">
				{#if returning}
					<form class="jlp-form" on:submit|preventDefault={sendBack}>
						<label class="jlp-field">
							<span>{$i18n.t('Reason for returning')}</span>
							<textarea rows="3" maxlength={REASON_MAX} bind:value={reason} required></textarea>
						</label>
						<span class="jlp-row-buttons">
							<button type="submit" class="jlp-button" disabled={busy}
								>{$i18n.t('Return card')}</button
							>
							<button
								type="button"
								class="jlp-link"
								disabled={busy}
								on:click={() => (returning = false)}>{$i18n.t('Cancel')}</button
							>
						</span>
					</form>
				{:else}
					<span class="jlp-row-buttons">
						{#if detail.contract.state !== 'approved'}
							<button
								type="button"
								class="jlp-button"
								disabled={busy || editing !== null || !detail.card_sha256}
								on:click={approve}>{$i18n.t('Approve this card')}</button
							>
						{/if}
						<button
							type="button"
							class="jlp-link"
							disabled={busy}
							on:click={() => (returning = true)}>{$i18n.t('Return with a reason')}</button
						>
					</span>
				{/if}
			</div>
		{/if}
	</div>
</Modal>
