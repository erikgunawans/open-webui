<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import { getKpi, LeadershipRequestError, type KpiCatalogue } from '$lib/apis/leadership';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import KpiInput from './KpiInput.svelte';
	import { SUPPORTED } from '$lib/leadership/context';
	import {
		CAP,
		PRORATA,
		QUARTERS,
		STATUS_LABEL,
		STORE,
		WARN,
		achievement,
		compute,
		fmt,
		loadRealisasi,
		nf,
		statusOf,
		targetAt,
		type Realisasi,
		type PerspectiveScore,
		type Row,
		type StatusId
	} from '$lib/leadership/kpi';
	import './kpi.css';

	// The KPI 2026 tab, ported from Erik's claude.ai/design "KPI Dashboard 2026" (2026-10-05). The
	// catalogue (targets, weights, definitions) comes from the server on the RKA grant; the
	// realisasi is the design's ILLUSTRATIVE sample, which the reader may overwrite. What they type
	// stays in this browser and is never sent anywhere.

	type State =
		| { kind: 'loading' }
		| { kind: 'denied' | 'unavailable' | 'failed'; message: string }
		| { kind: 'ready'; cat: KpiCatalogue };

	let state: State = { kind: 'loading' };
	let real: Realisasi = {};
	const controller = new AbortController();

	onMount(async () => {
		try {
			const cat = await getKpi(localStorage.token, SUPPORTED.rka.scope, controller.signal);
			let stored: string | null = null;
			try {
				stored = localStorage.getItem(STORE);
			} catch {
				stored = null;
			}
			real = loadRealisasi(cat, stored);
			state = { kind: 'ready', cat };
		} catch (error) {
			if (controller.signal.aborted) return;
			if (error instanceof LeadershipRequestError && error.isAccessDenied)
				state = { kind: 'denied', message: error.message };
			else if (error instanceof LeadershipRequestError && error.isUnavailable)
				state = { kind: 'unavailable', message: error.message };
			else state = { kind: 'failed', message: `${error}` };
		}
	});
	onDestroy(() => controller.abort());

	const save = (next: Realisasi) => {
		real = next;
		try {
			localStorage.setItem(STORE, JSON.stringify(next));
		} catch {
			// A private window or blocked storage: the change holds for this visit only.
		}
	};
	const setReal = (id: string, q: number, v: number | null) => {
		const series = [...(real[id] ?? [null, null, null, null])];
		series[q] = v;
		save({ ...real, [id]: series });
	};

	// The perspective colours: fills only, never text (memory: canonical accents are fills).
	const PCOLOR: Record<string, string> = {
		fin: 'var(--jup-brand)',
		cus: 'var(--jup-blue)',
		ibp: 'var(--kd-gold)',
		lg: 'var(--jup-navy)'
	};
	const TONE: Record<StatusId, string> = { ok: 'up', warn: 'defer', bad: 'down', none: 'neu' };

	let q = 2;
	let fp = 'all';
	let fs: 'all' | StatusId = 'all';
	let search = '';
	let sort: 'default' | 'ach' | 'w' = 'default';
	let openId: string | null = null;
	let confirmReset = false;

	$: cat = state.kind === 'ready' ? state.cat : null;
	$: series = cat ? [0, 1, 2, 3].map((i) => compute(cat!, real, i)) : [];
	$: cur = series[q];
	$: prev = q > 0 ? series[q - 1] : null;
	$: counts = cur
		? cur.rows.reduce((a, r) => ({ ...a, [r.st.id]: a[r.st.id] + 1 }), {
				ok: 0,
				warn: 0,
				bad: 0,
				none: 0
			} as Record<StatusId, number>)
		: { ok: 0, warn: 0, bad: 0, none: 0 };
	$: totalSt = statusOf(cur?.filled ? cur.total / 100 : null);

	$: needle = search.trim().toLowerCase();
	$: filtered = cur
		? cur.rows.filter(
				(r) =>
					(fp === 'all' || r.k.p === fp) &&
					(fs === 'all' || r.st.id === fs) &&
					(!needle || `${r.k.name} ${r.k.so_d} ${r.k.so_k}`.toLowerCase().includes(needle))
			)
		: [];
	$: rows =
		sort === 'ach'
			? [...filtered].sort((a, b) => (a.ach ?? -1) - (b.ach ?? -1))
			: sort === 'w'
				? [...filtered].sort((a, b) => b.k.weight - a.k.weight)
				: filtered;
	// Sorted by perspective, the table groups rows under a perspective head; any other sort is flat.
	type Section = { key: string; head: PerspectiveScore | null; rows: Row[] };
	$: sections =
		cat && cur && sort === 'default'
			? cur.per
					.map(
						(pp): Section => ({
							key: pp.p.id,
							head: pp,
							rows: rows.filter((r) => r.k.p === pp.p.id)
						})
					)
					.filter((g) => g.rows.length > 0)
			: [{ key: 'all', head: null, rows } as Section];

	$: openItem = cat && openId ? (cat.items.find((k) => k.id === openId) ?? null) : null;
	$: openPersp = openItem && cat ? cat.perspectives.find((p) => p.id === openItem!.p) : null;

	const barPct = (v: number | null) => (v == null ? 0 : (Math.min(v, CAP) / CAP) * 100);
	const MARK = (1 / CAP) * 100;

	// The trend: stacked perspective scores per quarter, an unfilled quarter as a dashed frame.
	const W = 560;
	const H = 200;
	const PAD = { l: 34, r: 8, t: 12, b: 26 };
	const BW = 56;
	const IH = H - PAD.t - PAD.b;
	const STEP = (W - PAD.l - PAD.r) / 4;
	const y = (v: number) => PAD.t + IH - (v / 100) * IH;
	const stack = (per: { p: { id: string }; score: number }[]) => {
		let acc = 0;
		return per.map((pp) => {
			const y0 = y(acc + pp.score);
			const h = Math.max(0, y(acc) - y0);
			acc += pp.score;
			return { id: pp.p.id, y: y0, h };
		});
	};

	const rowKey = (e: KeyboardEvent, id: string) => {
		if (e.key === 'Enter') openKpi(id);
	};
	const STATUS_IDS: StatusId[] = ['ok', 'warn', 'bad', 'none'];
	const statusOptions: ('all' | StatusId)[] = ['all', ...STATUS_IDS];

	// The Modal closes itself (Escape, backdrop) through its bound `show`; closing clears the row.
	let showDetail = false;
	const openKpi = (id: string) => {
		openId = id;
		showDetail = true;
	};
	$: if (!showDetail) openId = null;
</script>

{#if state.kind === 'loading'}
	<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{:else if state.kind === 'denied'}
	<div class="jlp-notice">
		<p class="font-medium">Anda tidak memiliki akses ke tampilan ini</p>
		<p class="mt-1 text-sm">{state.message}</p>
	</div>
{:else if state.kind === 'unavailable'}
	<div class="jlp-notice">
		<p class="font-medium">Ruang Pimpinan tidak tersedia</p>
		<p class="mt-1 text-sm">{state.message}</p>
	</div>
{:else if state.kind === 'failed'}
	<div class="jlp-notice jlp-notice-refused">
		<p class="font-medium">KPI tidak dapat dimuat</p>
		<p class="mt-1 text-sm">{state.message}</p>
	</div>
{:else if cat && cur}
	<div class="kd">
		<header class="kd-head">
			<div>
				<div class="kd-eyebrow">PT Jakarta Utilitas Propertindo</div>
				<h2 class="kd-h">Key Performance Indicator {cat.year}</h2>
				<div class="kd-head-meta">
					{#if cat.sample_is_illustrative}<span class="kd-badge kd-badge-outline"
							>Realisasi ILUSTRATIF</span
						>{/if}
					<span class="kd-muted"
						>{cat.items.length} KPI · {cat.perspectives.length} perspektif · sumber: {cat.source}</span
					>
				</div>
			</div>
			<div class="kd-head-ctrl">
				<div class="jup-seg kd-seg" role="group" aria-label="Periode">
					{#each QUARTERS as label, i}
						<button
							type="button"
							class="kd-seg-btn"
							aria-current={q === i ? 'page' : undefined}
							aria-pressed={q === i}
							on:click={() => (q = i)}>{label}</button
						>
					{/each}
				</div>
				<button type="button" class="kd-ghost" on:click={() => (confirmReset = true)}
					>Reset data</button
				>
			</div>
		</header>

		<section class="kd-hero">
			<div class="jlp-surface kd-score">
				<div class="kd-eyebrow">Skor kinerja korporat · {QUARTERS[q]}</div>
				<div class="kd-score-row">
					<span class="kd-score-big">{cur.filled ? nf(cur.total) : '—'}</span>
					<span class="kd-score-of">/ 100</span>
					{#if cur.filled > 0}<span class="kd-badge kd-tone-{TONE[totalSt.id]}"
							>{totalSt.label}</span
						>{/if}
				</div>
				<div class="kd-score-sub">
					{#if prev && prev.filled && cur.filled}
						<span class={cur.total >= prev.total ? 'kd-up' : 'kd-down'}
							>{cur.total >= prev.total ? '▲' : '▼'}
							{nf(Math.abs(cur.total - prev.total))} vs {QUARTERS[q - 1]}</span
						>
					{/if}
					<span class="kd-muted"
						>{cur.filled}/{cat.items.length} KPI terisi · capaian dibatasi {nf(CAP * 100, 0)}%</span
					>
				</div>
				<div class="kd-stack" aria-label="Komposisi skor per perspektif">
					{#each cur.per as pp (pp.p.id)}
						<div class="kd-stack-seg" style="flex: {pp.max}">
							<div
								class="kd-fill"
								style="width: {Math.min(100, (pp.score / pp.max) * 100)}%; background: {PCOLOR[
									pp.p.id
								]}"
							></div>
						</div>
					{/each}
				</div>
				<div class="kd-stats">
					{#each STATUS_IDS as sid}
						<button
							type="button"
							class="kd-stat"
							class:is-on={fs === sid}
							aria-pressed={fs === sid}
							on:click={() => (fs = fs === sid ? 'all' : sid)}
						>
							<span class="kd-dot kd-dot-{TONE[sid]}"></span>
							<span class="kd-stat-n">{counts[sid]}</span>
							<span class="kd-stat-l">{STATUS_LABEL[sid]}</span>
						</button>
					{/each}
				</div>
			</div>

			<div class="jlp-surface">
				<div class="jlp-surface-title">Tren skor per triwulan</div>
				<p class="kd-muted">Kontribusi tiap perspektif terhadap skor total</p>
				<svg
					viewBox="0 0 {W} {H}"
					class="kd-trend"
					role="img"
					aria-label="Skor kinerja per triwulan"
				>
					{#each [0, 25, 50, 75, 100] as g}
						<line x1={PAD.l} x2={W - PAD.r} y1={y(g)} y2={y(g)} class="kd-grid" />
						<text x={PAD.l - 6} y={y(g) + 4} text-anchor="end" class="kd-axis">{g}</text>
					{/each}
					{#each series as s, i}
						{@const x = PAD.l + STEP * i + (STEP - BW) / 2}
						<g opacity={s.filled ? (i === q ? 1 : 0.55) : 1}>
							{#if s.filled}
								{#each stack(s.per) as seg (seg.id)}
									<rect {x} y={seg.y} width={BW} height={seg.h} fill={PCOLOR[seg.id]} />
								{/each}
								<text x={x + BW / 2} y={y(s.total) - 5} text-anchor="middle" class="kd-val"
									>{nf(s.total)}</text
								>
							{:else}
								<rect {x} y={y(100)} width={BW} height={IH} class="kd-empty-bar" />
								<text x={x + BW / 2} y={y(50)} text-anchor="middle" class="kd-axis"
									>Belum ada data</text
								>
							{/if}
							<text
								x={x + BW / 2}
								y={H - 8}
								text-anchor="middle"
								class="kd-axis"
								class:kd-axis-on={i === q}>{QUARTERS[i]}</text
							>
						</g>
					{/each}
				</svg>
				<div class="kd-legend">
					{#each cat.perspectives as p (p.id)}
						<span><i style="background: {PCOLOR[p.id]}"></i>{p.name}</span>
					{/each}
				</div>
			</div>
		</section>

		<section class="kd-persp">
			{#each cur.per as pp (pp.p.id)}
				{@const ratio = pp.score / pp.max}
				<button
					type="button"
					class="kd-pcard"
					class:is-on={fp === pp.p.id}
					aria-pressed={fp === pp.p.id}
					on:click={() => (fp = fp === pp.p.id ? 'all' : pp.p.id)}
				>
					<div class="kd-pcard-top">
						<span class="kd-sw" style="background: {PCOLOR[pp.p.id]}"></span>
						<span class="kd-eyebrow">Bobot {nf(pp.max, 0)}%</span>
					</div>
					<div class="kd-pcard-name">{pp.p.name}</div>
					<div class="kd-pcard-score">
						<span class="kd-pcard-big">{nf(pp.score)}</span>
						<span class="kd-muted">/ {nf(pp.max, 0)}</span>
						<span class="kd-pcard-pct">{nf(ratio * 100, 0)}%</span>
					</div>
					<div class="kd-bar" style="height: 8px">
						<div
							class="kd-fill"
							style="width: {barPct(ratio)}%; background: {PCOLOR[pp.p.id]}"
						></div>
						<div class="kd-bar-mark" style="left: {MARK}%"></div>
					</div>
					<div class="kd-pcard-foot">
						<span
							><i class="kd-dot kd-dot-up"></i>{pp.rows.filter((r) => r.st.id === 'ok')
								.length}</span
						>
						<span
							><i class="kd-dot kd-dot-defer"></i>{pp.rows.filter((r) => r.st.id === 'warn')
								.length}</span
						>
						<span
							><i class="kd-dot kd-dot-down"></i>{pp.rows.filter((r) => r.st.id === 'bad')
								.length}</span
						>
						<span class="kd-muted kd-push">{pp.rows.length} KPI</span>
					</div>
				</button>
			{/each}
		</section>

		<section class="jlp-surface kd-tablecard">
			<div class="kd-toolbar">
				<div>
					<h3 class="jlp-surface-title">Daftar KPI</h3>
					<span class="kd-muted"
						>{rows.length} dari {cat.items.length} · klik baris untuk detail, isi realisasi langsung di
						tabel</span
					>
				</div>
				<div class="kd-toolbar-r">
					<input
						class="kd-control"
						type="search"
						placeholder="Cari KPI…"
						aria-label="Cari KPI"
						bind:value={search}
					/>
					<select class="kd-control" aria-label="Perspektif" bind:value={fp}>
						<option value="all">Semua perspektif</option>
						{#each cat.perspectives as p (p.id)}<option value={p.id}>{p.name}</option>{/each}
					</select>
					<select class="kd-control" aria-label="Status" bind:value={fs}>
						{#each statusOptions as id}
							<option value={id}>{id === 'all' ? 'Semua status' : STATUS_LABEL[id]}</option>
						{/each}
					</select>
					<select class="kd-control" aria-label="Urutkan" bind:value={sort}>
						<option value="default">Urut: perspektif</option>
						<option value="ach">Urut: capaian terendah</option>
						<option value="w">Urut: bobot terbesar</option>
					</select>
				</div>
			</div>
			<div class="kd-tablewrap">
				<table class="kd-table">
					<thead>
						<tr>
							<th>Specific Target</th>
							<th class="kd-r">Target {PRORATA ? QUARTERS[q] : cat.year}</th>
							<th>Realisasi</th>
							<th>Capaian</th>
							<th class="kd-r">Bobot</th>
							<th class="kd-r">Skor</th>
							<th>Status</th>
						</tr>
					</thead>
					{#if !rows.length}
						<tbody
							><tr><td colspan="7" class="kd-empty">Tidak ada KPI yang cocok dengan filter.</td></tr
							></tbody
						>
					{:else}
						{#each sections as section (section.key)}
							<tbody>
								{#if section.head}
									<tr class="kd-group">
										<td colspan="7"
											><span class="kd-sw" style="background: {PCOLOR[section.head.p.id]}"
											></span>Perspektif {section.head.p.name}<span class="kd-group-r"
												>{nf(section.head.score, 2)} / {nf(section.head.max, 0)}</span
											></td
										>
									</tr>
								{/if}
								{#each section.rows as row (row.k.id)}
									<tr
										class="kd-row"
										tabindex="0"
										on:click={() => openKpi(row.k.id)}
										on:keydown={(e) => rowKey(e, row.k.id)}
									>
										<td class="kd-c-name"
											><div class="kd-kname">{row.k.name}</div>
											<div class="kd-ksub">{row.k.so_d}</div></td
										>
										<td class="kd-mono kd-r">{fmt(row.k, row.tg)}</td>
										<td class="kd-c-in"
											><KpiInput
												k={row.k}
												value={row.r}
												onCommit={(v) => setReal(row.k.id, q, v)}
											/></td
										>
										<td class="kd-c-ach"
											><div class="kd-achrow">
												<span class="kd-mono"
													>{row.ach == null ? '—' : `${nf(row.ach * 100)}%`}</span
												>
												<div class="kd-bar" style="height: 6px">
													<div
														class="kd-fill"
														style="width: {barPct(row.ach)}%; background: {PCOLOR[row.k.p]}"
													></div>
													<div class="kd-bar-mark" style="left: {MARK}%"></div>
												</div>
											</div></td
										>
										<td class="kd-mono kd-r">{nf(row.k.weight * 100, 0)}%</td>
										<td class="kd-mono kd-r kd-strong">{nf(row.score, 2)}</td>
										<td><span class="kd-badge kd-tone-{TONE[row.st.id]}">{row.st.label}</span></td>
									</tr>
								{/each}
							</tbody>
						{/each}
					{/if}
				</table>
			</div>
		</section>

		<p class="kd-foot kd-muted">
			Capaian = Realisasi ÷ Target{PRORATA
				? ' (KPI kumulatif dibandingkan dengan target pro-rata triwulan)'
				: ''}. Skor = min(Capaian, {nf(CAP * 100, 0)}%) × Bobot × 100. Status: ≥100% tercapai, ≥{nf(
				WARN * 100,
				0
			)}% perlu perhatian. Perubahan realisasi tersimpan di browser ini saja.
		</p>
	</div>

	{#if openItem && openPersp}
		<Modal size="lg" bind:show={showDetail} ariaLabelledby="kd-detail-title">
			<div class="jlp-root jlp-dialog kd" role="document">
				<div class="jlp-dialog-head">
					<div>
						<h2 class="jlp-dialog-title" id="kd-detail-title">{openItem.name}</h2>
						<p class="kd-muted">
							Perspektif {openPersp.name} · Bobot {nf(openItem.weight * 100, 0)}% · Monitoring {openItem.monitoring}
						</p>
					</div>
					<button type="button" class="jlp-link" on:click={() => (showDetail = false)}>Selesai</button>
				</div>
				<dl class="kd-dl">
					<dt>Strategy Objective Korporasi</dt>
					<dd>{openItem.so_k}</dd>
					<dt>Strategy Objective Divisi/AU</dt>
					<dd>{openItem.so_d}</dd>
					<dt>Pengertian</dt>
					<dd>{openItem.definition}</dd>
					<dt>Formula</dt>
					<dd>{openItem.formula}</dd>
					<dt>Target {cat.year}</dt>
					<dd class="kd-mono">
						{fmt(openItem, openItem.target)} <span class="kd-muted">({openItem.satuan})</span>
					</dd>
				</dl>
				<div class="kd-qgrid">
					{#each QUARTERS as label, qi}
						{@const k = openItem}
						{@const tg = targetAt(k, qi)}
						{@const r = real[k.id]?.[qi] ?? null}
						{@const ach = achievement(r, tg)}
						{@const st = statusOf(ach)}
						<div class="kd-qcell">
							<div class="kd-qcell-head">
								<span class="kd-eyebrow">{label}</span>
								<span class="kd-badge kd-tone-{TONE[st.id]}"
									>{ach == null ? '—' : `${nf(ach * 100)}%`}</span
								>
							</div>
							<label class="kd-qfield">
								<span>Realisasi s.d. periode</span>
								<KpiInput {k} value={r} onCommit={(v) => setReal(k.id, qi, v)} />
								<span class="kd-muted">Target: {fmt(k, tg)}</span>
							</label>
							<div class="kd-bar" style="height: 6px">
								<div class="kd-fill" style="width: {barPct(ach)}%; background: {PCOLOR[k.p]}"></div>
								<div class="kd-bar-mark" style="left: {MARK}%"></div>
							</div>
						</div>
					{/each}
				</div>
				{#if openItem.cum}
					<p class="kd-note">
						{PRORATA
							? 'Target triwulan dihitung pro-rata dari target tahunan (kumulatif).'
							: 'Realisasi kumulatif dibandingkan langsung dengan target tahunan.'}
					</p>
				{/if}
			</div>
		</Modal>
	{/if}

	<ConfirmDialog
		bind:show={confirmReset}
		title="Reset data"
		message="Kembalikan semua realisasi ke data contoh?"
		confirmLabel="Reset"
		cancelLabel="Batal"
		onConfirm={() => save(JSON.parse(JSON.stringify(cat?.sample ?? {})))}
	/>
{/if}
