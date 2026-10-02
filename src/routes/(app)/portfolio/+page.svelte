<script lang="ts">
	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { showSidebar, WEBUI_NAME } from '$lib/stores';
	import {
		getPortfolio,
		PortfolioRequestError,
		type Engagement,
		type EvidenceItem,
		type Portfolio,
		type PortfolioProject
	} from '$lib/apis/portfolio';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import MobileSidebarToggle from '$lib/components/jup/MobileSidebarToggle.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The fail-closed stage gates, in ladder order. Rendering the whole ladder rather than only the
	// gate reached is what makes Current Gate legible as a derivation instead of a status field.
	const GATES = ['G1', 'G2', 'G3', 'G4'];

	// The Engagement Stage ladder (ADR-0008), lowest rung first. Rendering the whole ladder
	// rather than only the rung reached is what makes a stage read as a position on a scale
	// — and what makes `No contact` legible as a recorded position rather than an absence.
	const STAGES = ['no-contact', 'contacted', 'in-discussion', 'written-intent', 'executed'];

	// The projection (backend/jup/portfolio.py) writes its labels and sentences in English and
	// stays the single source of what they say. They are translated here, at render time, keyed
	// by the slug or tier code the payload already carries, or by the English sentence itself.
	// Every key is written out as a literal translate call so `i18n:parse` keeps it; a sentence the backend
	// rewords misses the map and renders in its English, never as a stale translation.
	// tests/test_portfolio_i18n.py fails when that happens.
	$: stageLabels = {
		'no-contact': $i18n.t('No contact'),
		contacted: $i18n.t('Contacted'),
		'in-discussion': $i18n.t('In discussion'),
		'written-intent': $i18n.t('Written intent'),
		executed: $i18n.t('Executed')
	} as Record<string, string>;

	$: tierLabels = {
		FAKTA: $i18n.t('Tier 1 · FAKTA'),
		POTENSI: $i18n.t('Tier 2 · POTENSI'),
		ILUSTRATIF: $i18n.t('Tier 3 · ILUSTRATIF')
	} as Record<string, string>;

	$: tierMeanings = {
		FAKTA: $i18n.t('Feasibility economics — NPV, IRR and payback from the business plan.'),
		POTENSI: $i18n.t('Top-line revenue potential. Never margin: B-to-G prices are government-set.'),
		ILUSTRATIF: $i18n.t('Order-of-magnitude sizing from capacity targets and unit costs.')
	} as Record<string, string>;

	$: serverText = {
		'This shows what was assessed, not whether the assessment was right. It cannot detect a record that is well-formed and wrong.':
			$i18n.t(
				'This shows what was assessed, not whether the assessment was right. It cannot detect a record that is well-formed and wrong.'
			),
		'A project with no assessment has not been evaluated. It has not passed, and it has not failed.':
			$i18n.t(
				'A project with no assessment has not been evaluated. It has not passed, and it has not failed.'
			),
		'Current Gate says a gate was passed on the day it was signed. It is not a statement about the project today.':
			$i18n.t(
				'Current Gate says a gate was passed on the day it was signed. It is not a statement about the project today.'
			),
		'Figures carry the basis they rest on and are never combined across bases (D11). Nothing here totals a portfolio.':
			$i18n.t(
				'Figures carry the basis they rest on and are never combined across bases (D11). Nothing here totals a portfolio.'
			),
		'An engagement sits on the rung its artefact evidences. This states where it stands — never whether it will close (ADR-0009).':
			$i18n.t(
				'An engagement sits on the rung its artefact evidences. This states where it stands — never whether it will close (ADR-0009).'
			),
		"A rung records a document, not a counterparty's intent. Judgement about intent stays with the Director and outside this system.":
			$i18n.t(
				"A rung records a document, not a counterparty's intent. Judgement about intent stays with the Director and outside this system."
			),
		'No records directory is configured, so no projects were read.': $i18n.t(
			'No records directory is configured, so no projects were read.'
		),
		'Gate state is restricted to the operating layer. This account is signed in but is not a member of it.':
			$i18n.t(
				'Gate state is restricted to the operating layer. This account is signed in but is not a member of it.'
			)
	} as Record<string, string>;

	let loaded = false;
	let portfolio: Portfolio | null = null;
	let loadError: string | null = null;
	// Kept apart from `loadError`: one says the reader may not see gate state, the other says
	// the records themselves could not be trusted. Rendering them alike would tell a member
	// without access to go and fix a record.
	let accessDenied: string | null = null;

	const gateIsHeld = (project: PortfolioProject, gate: string) =>
		project.assessments.some((a) => a.gate === gate && a.verdict === 'pass');

	const gateWasRefused = (project: PortfolioProject, gate: string) =>
		project.assessments.some((a) => a.gate === gate && a.verdict === 'fail');

	// One record per engagement, looked up by the id a gate cites (ADR-0008). Resolving here
	// rather than embedding each engagement in its citation is what stops a counterparty's
	// stage being current in one place and stale in another.
	$: engagementsById = new Map((portfolio?.engagements ?? []).map((item) => [item.id, item]));

	const engagementOf = (id: string): Engagement | undefined => engagementsById.get(id);

	// The rung in the reader's language. `labels` is passed in rather than read from scope so the
	// template re-renders when the language changes.
	const stageOf = (engagement: Engagement | undefined, labels: Record<string, string>) =>
		engagement ? (labels[engagement.stage] ?? engagement.stage_label) : undefined;

	// What the record cites the requirement against — an artefact path or an Engagement id. The
	// parser has already refused any item carrying neither, so there is no empty case to render.
	const citation = (item: EvidenceItem) => item.artefact ?? item.engagement ?? '';

	const citationKind = (item: EvidenceItem) =>
		item.artefact ? $i18n.t('Artefact') : $i18n.t('Engagement');

	// The view lives in the query string, so a filtered view is a link the Director can send.
	// Each card also carries an id (#project-…, #engagement-…) to land on one record.
	const STATUSES = ['all', 'blocked', 'passed', 'refused', 'unassessed'] as const;
	// There is deliberately no sort by a figure. Ranking projects by an amount compares values
	// across tiers, which is the one comparison D11 prohibits.
	const SORTS = ['record', 'name', 'gate', 'blocked'] as const;
	type Status = (typeof STATUSES)[number];
	type Sort = (typeof SORTS)[number];

	const pick = <T extends string>(value: string | null, allowed: readonly T[], fallback: T): T =>
		allowed.includes(value as T) ? (value as T) : fallback;

	$: query = $page.url.searchParams.get('q') ?? '';
	$: pillar = $page.url.searchParams.get('pillar') ?? '';
	$: statusFilter = pick<Status>($page.url.searchParams.get('status'), STATUSES, 'all');
	$: sortBy = pick<Sort>($page.url.searchParams.get('sort'), SORTS, 'record');

	const setParam = (key: string, value: string, fallback = '') => {
		const url = new URL($page.url);
		if (value && value !== fallback) url.searchParams.set(key, value);
		else url.searchParams.delete(key);
		goto(url, { replaceState: true, keepFocus: true, noScroll: true });
	};

	const clearFilters = () => {
		const url = new URL($page.url);
		['q', 'pillar', 'status'].forEach((key) => url.searchParams.delete(key));
		goto(url, { replaceState: true, keepFocus: true, noScroll: true });
	};

	$: filtersActive = query !== '' || pillar !== '' || statusFilter !== 'all';

	$: pillars = [
		...new Set(
			[...(portfolio?.projects ?? []), ...(portfolio?.engagements ?? [])]
				.map((item) => item.pillar)
				.filter((value): value is string => !!value)
		)
	].sort((a, b) => a.localeCompare(b));

	const matchesText = (needle: string, ...fields: (string | null | undefined)[]) =>
		!needle || fields.some((field) => field?.toLowerCase().includes(needle));

	const statusOf = (project: PortfolioProject): Exclude<Status, 'all' | 'blocked'> =>
		project.current_gate ? 'passed' : project.has_assessments ? 'refused' : 'unassessed';

	// Highest gate held first; a refusal outranks never-assessed, because a stop is a decision.
	const gateRank = (project: PortfolioProject) =>
		project.current_gate
			? 10 + GATES.indexOf(project.current_gate)
			: project.has_assessments
				? 1
				: 0;

	const sortProjects = (projects: PortfolioProject[], by: Sort) => {
		const sorted = [...projects];
		if (by === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name));
		if (by === 'gate') sorted.sort((a, b) => gateRank(b) - gateRank(a));
		if (by === 'blocked')
			sorted.sort((a, b) => b.blocking_requirements.length - a.blocking_requirements.length);
		return sorted;
	};

	$: needle = query.trim().toLowerCase();

	// Searching a counterparty should find the projects waiting on it, not only its engagement card.
	const counterpartiesOf = (project: PortfolioProject) =>
		[
			...project.awaiting_engagements,
			...project.blocking_requirements.map((item) => item.engagement ?? '')
		].flatMap((id) => engagementOf(id)?.counterparty ?? []);

	// Drives the highlight on a deep-linked card. CSS :target cannot: it is resolved when the page
	// loads, and the cards only render after the data arrives.
	$: targetId = decodeURIComponent($page.url.hash.slice(1));

	$: visibleProjects = sortProjects(
		(portfolio?.projects ?? []).filter(
			(project) =>
				(!pillar || project.pillar === pillar) &&
				(statusFilter === 'all' ||
					(statusFilter === 'blocked'
						? project.blocking_requirements.length > 0
						: statusOf(project) === statusFilter)) &&
				matchesText(needle, project.name, project.id, project.pillar, ...counterpartiesOf(project))
		),
		sortBy
	);

	// The status filter is about gates, which engagements do not have, so it leaves them alone.
	$: visibleEngagements = (portfolio?.engagements ?? []).filter(
		(engagement) =>
			(!pillar || engagement.pillar === pillar) &&
			matchesText(
				needle,
				engagement.id,
				engagement.pillar,
				engagement.purpose,
				...engagement.counterparty
			)
	);

	const cardId = (kind: 'project' | 'engagement', id: string) => `${kind}-${id}`;

	onMount(async () => {
		try {
			portfolio = await getPortfolio(localStorage.token);
		} catch (error) {
			if (error instanceof PortfolioRequestError && error.isAccessDenied) {
				// Signed in, and not in the operating layer. Kept apart from the refusal below: a
				// permission answer is about this reader, and saying the records cannot be trusted
				// would send them to fix something that is not broken.
				accessDenied = error.message;
			} else {
				// A record the projection refuses to trust surfaces here. Saying so is the point: a gate
				// that cannot verify its own records must stop rather than render a confident blank.
				loadError = `${error}`;
				toast.error(loadError);
			}
		}

		loaded = true;

		// The cards render only after the data arrives, which is after the browser has already
		// tried and failed to find the fragment, so land on it here.
		if (location.hash) {
			await tick();
			document
				.getElementById(decodeURIComponent(location.hash.slice(1)))
				?.scrollIntoView({ block: 'start' });
		}
	});
</script>

<svelte:head>
	<title>{$i18n.t('Portfolio')} / {$WEBUI_NAME}</title>
</svelte:head>

<div
	class="jup-portfolio flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} max-w-full"
>
	<div class="flex-1 max-h-full overflow-y-auto">
		<div class="mx-auto w-full max-w-4xl px-5 pt-8 pb-16">
			<MobileSidebarToggle />
			<header class="mb-7">
				<p class="jup-eyebrow">Jakarta Utilitas Propertindo</p>
				<h1 class="jup-title text-2xl font-semibold">{$i18n.t('Portfolio')}</h1>
				<p class="jup-subtitle mt-1.5 text-sm">
					{$i18n.t(
						'Current Gate is derived from a project’s Gate Assessments. It is not stored, and nothing can set it.'
					)}
				</p>
			</header>

			{#if !loaded}
				<div class="flex justify-center py-16">
					<Spinner className="size-5" />
				</div>
			{:else if accessDenied}
				<div class="jup-notice">
					<p class="font-medium">{$i18n.t('Gate state is restricted to the operating layer')}</p>
					<p class="mt-1 text-sm">{serverText[accessDenied] ?? accessDenied}</p>
				</div>
			{:else if loadError}
				<div class="jup-notice jup-notice-refused">
					<p class="font-medium">{$i18n.t('The portfolio was refused, not emptied.')}</p>
					<p class="mt-1 text-sm">{loadError}</p>
				</div>
			{:else if portfolio?.unavailable_reason}
				<div class="jup-notice">
					<p class="font-medium">{$i18n.t('No records available')}</p>
					<p class="mt-1 text-sm">
						{serverText[portfolio.unavailable_reason] ?? portfolio.unavailable_reason}
					</p>
				</div>
			{:else if (portfolio?.projects ?? []).length === 0}
				<div class="jup-notice">
					<p class="font-medium">{$i18n.t('No projects are recorded')}</p>
					<p class="mt-1 text-sm">
						{$i18n.t('The records directory was read and holds no project.')}
					</p>
				</div>
			{:else}
				<form class="jup-controls" role="search" on:submit|preventDefault>
					<label class="jup-control jup-control-search">
						<span class="jup-control-label">{$i18n.t('Search')}</span>
						<input
							type="search"
							class="jup-input"
							value={query}
							placeholder={$i18n.t('Project, id or counterparty')}
							on:input={(event) => setParam('q', event.currentTarget.value)}
						/>
					</label>
					{#if pillars.length > 0}
						<label class="jup-control">
							<span class="jup-control-label">{$i18n.t('Pillar')}</span>
							<select
								class="jup-input"
								value={pillar}
								on:change={(event) => setParam('pillar', event.currentTarget.value)}
							>
								<option value="">{$i18n.t('All pillars')}</option>
								{#each pillars as option (option)}
									<option value={option}>{option}</option>
								{/each}
							</select>
						</label>
					{/if}
					<label class="jup-control">
						<span class="jup-control-label">{$i18n.t('Gate status')}</span>
						<select
							class="jup-input"
							value={statusFilter}
							on:change={(event) => setParam('status', event.currentTarget.value, 'all')}
						>
							<option value="all">{$i18n.t('All projects')}</option>
							<option value="blocked">{$i18n.t('Has blockers')}</option>
							<option value="passed">{$i18n.t('Gate passed')}</option>
							<option value="refused">{$i18n.t('No gate passed')}</option>
							<option value="unassessed">{$i18n.t('No assessment')}</option>
						</select>
					</label>
					<label class="jup-control">
						<span class="jup-control-label">{$i18n.t('Sort by')}</span>
						<select
							class="jup-input"
							value={sortBy}
							on:change={(event) => setParam('sort', event.currentTarget.value, 'record')}
						>
							<option value="record">{$i18n.t('Record order')}</option>
							<option value="name">{$i18n.t('Name')}</option>
							<option value="gate">{$i18n.t('Highest gate first')}</option>
							<option value="blocked">{$i18n.t('Most blockers first')}</option>
						</select>
					</label>
				</form>

				<p class="jup-meta jup-count text-xs" aria-live="polite">
					{$i18n.t('Showing {{shown}} of {{total}} projects', {
						shown: visibleProjects.length,
						total: portfolio?.projects.length ?? 0
					})}
					{#if filtersActive}
						&nbsp;·&nbsp;<button type="button" class="jup-link" on:click={clearFilters}
							>{$i18n.t('Clear filters')}</button
						>
					{/if}
				</p>

				{#if visibleProjects.length === 0}
					<div class="jup-notice">
						<p class="font-medium">{$i18n.t('No project matches these filters')}</p>
						<p class="mt-1 text-sm">
							{$i18n.t('The projects are still recorded; the filters above hide them.')}
						</p>
					</div>
				{/if}

				<ul class="flex flex-col gap-4">
					{#each visibleProjects as project (project.id)}
						<li
							class="jup-card"
							class:jup-card-target={targetId === cardId('project', project.id)}
							id={cardId('project', project.id)}
						>
							<div class="flex flex-wrap items-start justify-between gap-3">
								<div>
									<h2 class="jup-project-name text-base font-semibold">
										{project.name}
										<a
											class="jup-anchor"
											href="#{cardId('project', project.id)}"
											aria-label={$i18n.t('Link to this project')}>#</a
										>
									</h2>
									<p class="jup-meta mt-0.5 text-xs">
										{project.id}{#if project.pillar}&nbsp;·&nbsp;{project.pillar}{/if}
									</p>
								</div>

								{#if project.current_gate}
									<span class="jup-pill jup-pill-gate">
										{$i18n.t('Current Gate')}&nbsp;<strong>{project.current_gate}</strong>
									</span>
								{:else if project.has_assessments}
									<!-- Assessed and refused. Deliberately not the same pill as "never assessed":
									     a stop is a decision, and it must read as one. -->
									<span class="jup-pill jup-pill-refused">{$i18n.t('No gate passed')}</span>
								{:else}
									<!-- Never assessed. Absence of a record must never read as progress. -->
									<span class="jup-pill jup-pill-none">{$i18n.t('No assessment')}</span>
								{/if}
							</div>

							{#if project.blocking_requirements.length > 0}
								<!-- The field that replaces the conversation. These come only from refused
								     assessments: a requirement left unmet under a passing verdict is a waiver
								     the board granted, and naming it here would overrule a decision taken. -->
								<div class="jup-blocking">
									<p class="jup-blocking-label">{$i18n.t('Blocked on')}</p>
									<ul class="jup-blocking-list">
										{#each project.blocking_requirements as item (item.requirement)}
											<li class="jup-blocking-item">
												<span class="jup-requirement">{item.requirement}</span>
												{#if item.engagement && engagementOf(item.engagement)}
													{@const held = engagementOf(item.engagement)}
													<!-- The resolved citation: whose reply this is waiting for, and the rung
													     they are actually on — never a guess at whether they will say yes. -->
													<a
														class="jup-meta jup-cite-link text-xs"
														href="#{cardId('engagement', item.engagement)}"
													>
														{held?.counterparty.join(', ')}&nbsp;·&nbsp;{stageOf(held, stageLabels)}
													</a>
												{:else}
													<span class="jup-meta text-xs">
														{citationKind(item)}:&nbsp;{citation(item)}
													</span>
												{/if}
											</li>
										{/each}
									</ul>
								</div>
							{/if}

							<ol class="jup-ladder" aria-label={$i18n.t('Gate ladder')}>
								{#each GATES as gate (gate)}
									<li
										class="jup-rung"
										class:jup-rung-held={gateIsHeld(project, gate)}
										class:jup-rung-refused={!gateIsHeld(project, gate) &&
											gateWasRefused(project, gate)}
									>
										{gate}
										<!-- The state in words as well as colour, so a screen reader hears more
										     than "G1 G2 G3 G4". -->
										<span class="sr-only">
											{gateIsHeld(project, gate)
												? $i18n.t('passed')
												: gateWasRefused(project, gate)
													? $i18n.t('refused')
													: $i18n.t('not assessed')}
										</span>
									</li>
								{/each}
							</ol>

							{#if project.assessments.length > 0}
								<ul class="jup-assessments">
									{#each project.assessments as assessment (assessment.source)}
										<li class="jup-assessment">
											<span class="jup-assessment-gate">{assessment.gate}</span>
											<span
												class="jup-pill {assessment.verdict === 'pass'
													? 'jup-pill-pass'
													: 'jup-pill-fail'}"
											>
												{assessment.verdict === 'pass' ? $i18n.t('Passed') : $i18n.t('Refused')}
											</span>
											<span class="jup-meta text-xs">
												{assessment.assessed_on}&nbsp;·&nbsp;{assessment.signed_by}
											</span>

											{#if assessment.evidence.length > 0}
												<!-- Collapsed: the unmet items already lead the card under Blocked on,
												     so the full list is a check the Director opens, not a third
												     statement of the same blocker. -->
												<details class="jup-evidence-wrap">
													<summary class="jup-evidence-summary">
														{$i18n.t('Evidence: {{met}} of {{total}} satisfied', {
															met: assessment.evidence.filter((item) => item.satisfied).length,
															total: assessment.evidence.length
														})}
													</summary>
													<ul class="jup-evidence" aria-label={$i18n.t('Evidence required')}>
														{#each assessment.evidence as item (item.requirement)}
															<li class="jup-evidence-item">
																<span
																	class="jup-tick"
																	class:jup-tick-met={item.satisfied}
																	aria-hidden="true"
																>
																	{item.satisfied ? '✓' : '✗'}
																</span>
																<span class="jup-requirement">{item.requirement}</span>
																<span class="jup-evidence-state">
																	{item.satisfied ? $i18n.t('Satisfied') : $i18n.t('Not satisfied')}
																</span>
																<span class="jup-meta text-xs">
																	{citationKind(item)}:&nbsp;{citation(item)}
																</span>
															</li>
														{/each}
													</ul>
												</details>
											{:else}
												<p class="jup-meta jup-evidence-none text-xs">
													{$i18n.t('This assessment records no evidence requirements.')}
												</p>
											{/if}

											{#if assessment.awaiting_engagements.length > 0 && (assessment.verdict !== 'fail' || project.blocking_requirements.length === 0)}
												<!-- Under a refusal these are what the gate is waiting for. Under a *pass*
												     the same citations are a waiver the board granted, and #4's rule holds
												     here too: a waiver must never read as a blocker. A refusal's list is
												     skipped when Blocked on above already names the same counterparties. -->
												<p class="jup-meta jup-awaiting text-xs">
													{assessment.verdict === 'fail'
														? $i18n.t('Waiting on')
														: $i18n.t('Outstanding, waived')}:
													{#each assessment.awaiting_engagements as id, index (id)}{index > 0
															? ', '
															: ''}{engagementOf(id)?.counterparty.join(', ') ?? id}&nbsp;({stageOf(
															engagementOf(id),
															stageLabels
														) ?? $i18n.t('unresolved')}){/each}
												</p>
											{/if}
										</li>
									{/each}
								</ul>
							{:else}
								<p class="jup-meta mt-3 text-xs">
									{$i18n.t('This project has never been assessed against a gate.')}
								</p>
							{/if}
							{#if project.figures_by_tier.length > 0}
								<!-- One block per tier, never one list. The tier heading is what makes
								     composing two bases into a single statement something a renderer would
								     have to go out of its way to do (D11). -->
								<div class="jup-figures">
									{#each project.figures_by_tier as group (group.tier)}
										<section class="jup-tier">
											<p class="jup-tier-label">{tierLabels[group.tier] ?? group.label}</p>
											<p class="jup-tier-meaning">{tierMeanings[group.tier] ?? group.meaning}</p>
											<ul class="jup-figure-list">
												{#each group.figures as figure (figure.label)}
													<li class="jup-figure">
														<span class="jup-figure-value">{figure.value}</span>
														<span class="jup-figure-label">{figure.label}</span>
														<span class="jup-meta text-xs">
															{$i18n.t('Basis')}:&nbsp;{figure.basis}
														</span>
													</li>
												{/each}
											</ul>
										</section>
									{/each}
								</div>
							{/if}
						</li>
					{/each}
				</ul>

				{#if visibleEngagements.length > 0}
					<section class="jup-engagements-section">
						<h2 class="jup-title text-xl font-semibold">{$i18n.t('Engagements')}</h2>
						<!-- ADR-0009's consequence, now served with the payload rather than written
						     here, so the projection is the single source of what this view does not
						     prove and markup cannot drift from it. -->
						<aside class="jup-non-coverage" aria-label={$i18n.t('What this view does not prove')}>
							<p class="jup-non-coverage-label">{$i18n.t('What this view does not prove')}</p>
							<ul class="jup-non-coverage-list">
								{#each portfolio?.engagement_non_coverage ?? [] as statement (statement)}
									<li>{serverText[statement] ?? statement}</li>
								{/each}
							</ul>
						</aside>

						<ul class="mt-4 flex flex-col gap-3">
							{#each visibleEngagements as engagement (engagement.id)}
								<li
									class="jup-card"
									class:jup-card-target={targetId === cardId('engagement', engagement.id)}
									id={cardId('engagement', engagement.id)}
								>
									<div class="flex flex-wrap items-start justify-between gap-3">
										<div>
											<h3 class="jup-project-name text-sm font-semibold">
												{engagement.counterparty.join(', ')}
											</h3>
											<p class="jup-meta mt-0.5 text-xs">
												{engagement.id}{#if engagement.pillar}&nbsp;·&nbsp;{engagement.pillar}{/if}
											</p>
										</div>
										<span class="jup-pill jup-pill-stage"
											>{stageLabels[engagement.stage] ?? engagement.stage_label}</span
										>
									</div>

									<p class="jup-purpose mt-2 text-sm">{engagement.purpose}</p>

									<ol class="jup-ladder" aria-label={$i18n.t('Engagement stage ladder')}>
										{#each STAGES as stage (stage)}
											<li
												class="jup-rung"
												class:jup-rung-held={stage === engagement.stage}
												aria-current={stage === engagement.stage ? 'step' : undefined}
												title={stageLabels[stage]}
											>
												{stageLabels[stage]}
											</li>
										{/each}
									</ol>

									<p class="jup-meta jup-evidence-none mt-3 text-xs">
										{$i18n.t('Evidenced by')}:&nbsp;{engagement.artefact}
									</p>
								</li>
							{/each}
						</ul>
					</section>
				{/if}
			{/if}

			{#if (portfolio?.non_coverage ?? []).length > 0}
				<!-- Outside the branch chain on purpose. The empty and unavailable states are
				     exactly where a reader fills the silence with an assumption, so they are the
				     last place non-coverage should disappear. A clean dashboard mistaken for a
				     safe portfolio is the failure these sentences exist to prevent. -->
				<aside class="jup-non-coverage" aria-label={$i18n.t('What this view does not prove')}>
					<p class="jup-non-coverage-label">{$i18n.t('What this view does not prove')}</p>
					<ul class="jup-non-coverage-list">
						{#each portfolio?.non_coverage ?? [] as statement (statement)}
							<li>{serverText[statement] ?? statement}</li>
						{/each}
					</ul>
				</aside>
			{/if}
		</div>
	</div>
</div>

<style>
	/* Colour comes from the ported JUP tokens. Accents are fills, so every word uses a `-text`
	 * variant — see src/jup-tokens.css for the measured ratios.
	 *
	 * Type scale: 12 / 14 / 16 / 20 / 24px (0.75 / 0.875 / 1 / 1.25 / 1.5rem), nothing smaller.
	 * Labels are 12px, sentences 14px. Running text is held to a 68ch measure. */
	.jup-portfolio {
		background: var(--jup-paper);
	}

	.jup-title {
		color: var(--jup-ink);
		font-family: var(--jup-font-display);
		font-weight: var(--jup-ui-weight-display);
		letter-spacing: -0.035em;
	}

	.jup-subtitle,
	.jup-meta {
		color: var(--jup-ink-soft);
	}

	.jup-subtitle {
		max-width: 68ch;
	}

	.jup-project-name {
		color: var(--jup-ink);
	}

	.jup-card {
		background: var(--jup-ui-paper);
		border: 1px solid var(--jup-ui-hairline);
		border-radius: var(--jup-radius);
		box-shadow: var(--jup-ui-shadow-card);
		padding: 1.25rem;
	}

	/* A card reached by a deep link says so, without moving anything. */
	.jup-card {
		scroll-margin-top: 1.5rem;
	}

	.jup-card-target {
		outline: 2px solid var(--jup-ring);
		outline-offset: 2px;
	}

	.jup-controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.jup-control {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.jup-control-search {
		flex: 1 1 14rem;
	}

	.jup-control-label {
		color: var(--jup-ink-soft);
		font-size: 0.75rem;
		font-weight: 500;
	}

	/* The page is the canvas, where the kit's tonal fill (also Anti-flash White) would vanish, so a
	 * field steps up to paper with a hairline. Focus: a muted-ink edge (5.92:1) and the soft halo. */
	.jup-input {
		min-height: 2.25rem;
		background: var(--jup-ui-paper);
		color: var(--jup-ink);
		border: 1px solid var(--jup-ui-hairline-strong);
		border-radius: var(--jup-radius-sm);
		padding: 0.4rem 0.875rem;
		font-size: 0.875rem;
		transition: var(--jup-ui-transition);
	}

	.jup-input:hover {
		border-color: var(--jup-ui-muted);
	}

	.jup-input:focus-visible {
		outline: none;
		background: var(--jup-ui-paper);
		border-color: var(--jup-ui-muted);
		box-shadow: var(--jup-ui-ring);
	}

	.jup-count {
		margin-bottom: 1rem;
	}

	.jup-link,
	.jup-anchor,
	.jup-cite-link {
		color: var(--jup-link-text);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.jup-anchor {
		margin-left: 0.35rem;
		font-weight: 400;
		text-decoration: none;
		opacity: 0;
	}

	.jup-project-name:hover .jup-anchor,
	.jup-anchor:focus-visible {
		opacity: 1;
	}

	.jup-notice {
		background: var(--jup-neu-bg);
		color: var(--jup-neu-text);
		border: 1px solid var(--jup-line);
		border-radius: 14px;
		padding: 1.15rem 1.25rem;
	}

	.jup-notice-refused {
		background: var(--jup-down-bg);
		color: var(--jup-down-text);
	}

	.jup-pill {
		display: inline-flex;
		align-items: center;
		border-radius: var(--jup-radius-sm);
		padding: 0.22rem 0.62rem;
		font-size: 0.75rem;
		white-space: nowrap;
	}

	.jup-pill-gate {
		background: var(--jup-gate-bg);
		color: var(--jup-gate-text);
	}

	.jup-pill-pass {
		background: var(--jup-up-bg);
		color: var(--jup-up-text);
	}

	.jup-pill-fail,
	.jup-pill-refused {
		background: var(--jup-down-bg);
		color: var(--jup-down-text);
	}

	.jup-pill-none {
		background: var(--jup-neu-bg);
		color: var(--jup-neu-text);
	}

	.jup-ladder {
		display: flex;
		gap: 0.4rem;
		margin-top: 0.95rem;
	}

	.jup-rung {
		flex: 1;
		text-align: center;
		border-radius: var(--jup-radius-sm);
		border: 1px solid var(--jup-line);
		background: var(--jup-neu-bg);
		color: var(--jup-neu-text);
		padding: 0.3rem 0;
		font-size: 0.75rem;
		letter-spacing: 0.04em;
	}

	.jup-rung-held {
		background: var(--jup-up-bg);
		color: var(--jup-up-text);
		border-color: var(--jup-up-text);
		font-weight: 600;
	}

	.jup-rung-refused {
		background: var(--jup-down-bg);
		color: var(--jup-down-text);
		border-color: var(--jup-down-text);
	}

	.jup-assessments {
		margin-top: 0.95rem;
		border-top: 1px solid var(--jup-line-soft);
		padding-top: 0.7rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.jup-assessment {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.55rem;
	}

	.jup-assessment-gate {
		color: var(--jup-ink);
		font-size: 0.875rem;
		font-weight: 600;
		min-width: 1.6rem;
	}

	/* The blockers, lifted to the top of the card. A Director reading one screen should see what
	 * is missing without expanding an assessment. */
	.jup-blocking {
		margin-top: 0.95rem;
		background: var(--jup-down-bg);
		color: var(--jup-down-text);
		border-radius: var(--jup-radius-nested);
		padding: 0.6rem 0.75rem;
	}

	.jup-blocking-label {
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.jup-blocking-list {
		margin-top: 0.35rem;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.jup-blocking-item {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.5rem;
		font-size: 0.875rem;
		max-width: 68ch;
	}

	/* `.jup-assessment` wraps, so the evidence list claims a full row of its own beneath the
	 * verdict rather than trailing off the end of it. */
	.jup-evidence-wrap,
	.jup-evidence-none {
		flex-basis: 100%;
		margin-left: 2.15rem;
	}

	.jup-evidence-summary {
		cursor: pointer;
		width: fit-content;
		color: var(--jup-ink-soft);
		font-size: 0.75rem;
		font-weight: 500;
	}

	.jup-evidence-summary:hover {
		color: var(--jup-ink);
	}

	.jup-evidence-wrap[open] .jup-evidence-summary {
		margin-bottom: 0.4rem;
	}

	.jup-evidence {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.jup-evidence-item {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.45rem;
		font-size: 0.875rem;
		max-width: 68ch;
	}

	.jup-requirement {
		color: var(--jup-ink);
		font-family: var(--jup-font-mono);
		font-size: 0.75rem;
	}

	/* Inside the blocking block the neutral ink token is the wrong hue family against the refusal
	 * fill, so both the requirement and its citation take the block's own colour. */
	.jup-blocking-item .jup-requirement,
	.jup-blocking-item .jup-meta {
		color: inherit;
	}

	/* No opacity softening here: at 0.82 the composited citation measures 3.75:1 against the
	 * refusal fill and fails AA, even though the token itself is 4.90:1. */

	.jup-evidence-state {
		color: var(--jup-ink-soft);
		font-size: 0.75rem;
	}

	/* A shape as well as a colour, so met and unmet do not rely on hue alone. */
	.jup-tick {
		color: var(--jup-down-text);
		font-weight: 700;
		min-width: 0.9rem;
	}

	.jup-tick-met {
		color: var(--jup-up-text);
	}

	.jup-engagements-section {
		margin-top: 2.25rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--jup-line);
	}

	.jup-purpose {
		color: var(--jup-ink-soft);
		max-width: 68ch;
	}

	.jup-pill-stage {
		background: var(--jup-gate-bg);
		color: var(--jup-gate-text);
	}

	.jup-awaiting {
		flex-basis: 100%;
		margin-left: 2.15rem;
	}

	/* One visually separated block per tier. The separation is the point: two bases must not
	 * read as one statement, so they do not share a row, a rule or a background. */
	.jup-figures {
		margin-top: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.jup-tier {
		border-left: 3px solid var(--jup-line);
		padding-left: 0.75rem;
	}

	.jup-tier-label {
		color: var(--jup-ink);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.04em;
	}

	.jup-tier-meaning {
		color: var(--jup-ink-soft);
		font-size: 0.875rem;
		max-width: 68ch;
		margin-top: 0.1rem;
	}

	.jup-figure-list {
		margin-top: 0.45rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.jup-figure {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.5rem;
	}

	/* The one number the Director acts on: larger than the project name, set in the display face
	 * at 500 with tabular figures (the kit's StatBlock), so amounts align across tiers. */
	.jup-figure-value {
		color: var(--jup-ink);
		font-family: var(--jup-font-display);
		font-size: 1.375rem;
		font-weight: 500;
		letter-spacing: -0.03em;
		font-variant-numeric: tabular-nums;
	}

	.jup-figure-label {
		color: var(--jup-ink-soft);
		font-size: 0.875rem;
	}

	.jup-non-coverage {
		margin-top: 1.75rem;
		background: var(--jup-neu-bg);
		color: var(--jup-neu-text);
		border: 1px solid var(--jup-line);
		border-radius: 14px;
		padding: 0.9rem 1.1rem;
	}

	.jup-non-coverage-label {
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.jup-non-coverage-list {
		margin-top: 0.45rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.875rem;
		max-width: 68ch;
		list-style: disc;
		padding-left: 1.1rem;
	}
</style>
