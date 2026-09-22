<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { showSidebar } from '$lib/stores';
	import {
		getPortfolio,
		PortfolioRequestError,
		type Engagement,
		type EvidenceItem,
		type Portfolio,
		type PortfolioProject
	} from '$lib/apis/portfolio';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The fail-closed stage gates, in ladder order. Rendering the whole ladder rather than only the
	// gate reached is what makes Current Gate legible as a derivation instead of a status field.
	const GATES = ['G1', 'G2', 'G3', 'G4'];

	// The Engagement Stage ladder (ADR-0008), lowest rung first. Rendering the whole ladder
	// rather than only the rung reached is what makes a stage read as a position on a scale
	// — and what makes `No contact` legible as a recorded position rather than an absence.
	const STAGES = [
		{ slug: 'no-contact', label: 'No contact' },
		{ slug: 'contacted', label: 'Contacted' },
		{ slug: 'in-discussion', label: 'In discussion' },
		{ slug: 'written-intent', label: 'Written intent' },
		{ slug: 'executed', label: 'Executed' }
	];

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

	// What the record cites the requirement against — an artefact path or an Engagement id. The
	// parser has already refused any item carrying neither, so there is no empty case to render.
	const citation = (item: EvidenceItem) => item.artefact ?? item.engagement ?? '';

	const citationKind = (item: EvidenceItem) =>
		item.artefact ? $i18n.t('Artefact') : $i18n.t('Engagement');

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
	});
</script>

<svelte:head>
	<title>{$i18n.t('Portfolio')}</title>
</svelte:head>

<div
	class="jup-portfolio flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} max-w-full"
>
	<div class="flex-1 max-h-full overflow-y-auto">
		<div class="mx-auto w-full max-w-4xl px-5 py-8">
			<header class="mb-7">
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
					<p class="mt-1 text-sm">{accessDenied}</p>
				</div>
			{:else if loadError}
				<div class="jup-notice jup-notice-refused">
					<p class="font-medium">{$i18n.t('The portfolio was refused, not emptied.')}</p>
					<p class="mt-1 text-sm">{loadError}</p>
				</div>
			{:else if portfolio?.unavailable_reason}
				<div class="jup-notice">
					<p class="font-medium">{$i18n.t('No records available')}</p>
					<p class="mt-1 text-sm">{portfolio.unavailable_reason}</p>
				</div>
			{:else if (portfolio?.projects ?? []).length === 0}
				<div class="jup-notice">
					<p class="font-medium">{$i18n.t('No projects are recorded')}</p>
					<p class="mt-1 text-sm">
						{$i18n.t('The records directory was read and holds no project.')}
					</p>
				</div>
			{:else}
				<ul class="flex flex-col gap-4">
					{#each portfolio?.projects ?? [] as project (project.id)}
						<li class="jup-card">
							<div class="flex flex-wrap items-start justify-between gap-3">
								<div>
									<h2 class="jup-project-name text-base font-semibold">{project.name}</h2>
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
													<span class="jup-meta text-xs">
														{held?.counterparty.join(', ')}&nbsp;·&nbsp;{held?.stage_label}
													</span>
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
											{:else}
												<p class="jup-meta jup-evidence-none text-xs">
													{$i18n.t('This assessment records no evidence requirements.')}
												</p>
											{/if}

											{#if assessment.awaiting_engagements.length > 0}
												<!-- Under a refusal these are what the gate is waiting for. Under a *pass*
												     the same citations are a waiver the board granted, and #4's rule holds
												     here too: a waiver must never read as a blocker. -->
												<p class="jup-meta jup-awaiting text-xs">
													{assessment.verdict === 'fail'
														? $i18n.t('Waiting on')
														: $i18n.t('Outstanding, waived')}:
													{#each assessment.awaiting_engagements as id, index (id)}{index > 0
															? ', '
															: ''}{engagementOf(id)?.counterparty.join(', ') ??
															id}&nbsp;({engagementOf(id)?.stage_label ??
															$i18n.t('unresolved')}){/each}
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
											<p class="jup-tier-label">{group.label}</p>
											<p class="jup-tier-meaning">{group.meaning}</p>
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

				{#if (portfolio?.engagements ?? []).length > 0}
					<section class="jup-engagements-section">
						<h2 class="jup-title text-lg font-semibold">{$i18n.t('Engagements')}</h2>
						<!-- ADR-0009's consequence, now served with the payload rather than written
						     here, so the projection is the single source of what this view does not
						     prove and markup cannot drift from it. -->
						<aside class="jup-non-coverage" aria-label={$i18n.t('What this view does not prove')}>
							<p class="jup-non-coverage-label">{$i18n.t('What this view does not prove')}</p>
							<ul class="jup-non-coverage-list">
								{#each portfolio?.engagement_non_coverage ?? [] as statement (statement)}
									<li>{statement}</li>
								{/each}
							</ul>
						</aside>

						<ul class="mt-4 flex flex-col gap-3">
							{#each portfolio?.engagements ?? [] as engagement (engagement.id)}
								<li class="jup-card">
									<div class="flex flex-wrap items-start justify-between gap-3">
										<div>
											<h3 class="jup-project-name text-sm font-semibold">
												{engagement.counterparty.join(', ')}
											</h3>
											<p class="jup-meta mt-0.5 text-xs">
												{engagement.id}{#if engagement.pillar}&nbsp;·&nbsp;{engagement.pillar}{/if}
											</p>
										</div>
										<span class="jup-pill jup-pill-stage">{engagement.stage_label}</span>
									</div>

									<p class="jup-purpose mt-2 text-sm">{engagement.purpose}</p>

									<ol class="jup-ladder" aria-label={$i18n.t('Engagement stage ladder')}>
										{#each STAGES as stage (stage.slug)}
											<li
												class="jup-rung"
												class:jup-rung-held={stage.slug === engagement.stage}
												title={stage.label}
											>
												{stage.label}
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
							<li>{statement}</li>
						{/each}
					</ul>
				</aside>
			{/if}
		</div>
	</div>
</div>

<style>
	/* Colour comes from the ported JUP tokens. Accents are fills, so every word uses a `-text`
	 * variant — see src/jup-tokens.css for the measured ratios. */
	.jup-portfolio {
		background: var(--jup-paper);
	}

	.jup-title {
		color: var(--jup-ink);
	}

	.jup-subtitle,
	.jup-meta {
		color: var(--jup-ink-soft);
	}

	.jup-project-name {
		color: var(--jup-ink);
	}

	.jup-card {
		background: var(--jup-surface);
		border: 1px solid var(--jup-line);
		border-radius: var(--jup-radius);
		box-shadow: var(--jup-shadow);
		padding: 1.15rem 1.25rem;
	}

	.jup-notice {
		background: var(--jup-neu-bg);
		color: var(--jup-neu-text);
		border: 1px solid var(--jup-line);
		border-radius: var(--jup-radius);
		padding: 1.15rem 1.25rem;
	}

	.jup-notice-refused {
		background: var(--jup-down-bg);
		color: var(--jup-down-text);
	}

	.jup-pill {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
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
		font-size: 0.72rem;
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
		font-size: 0.78rem;
		font-weight: 600;
		min-width: 1.6rem;
	}

	/* The blockers, lifted to the top of the card. A Director reading one screen should see what
	 * is missing without expanding an assessment. */
	.jup-blocking {
		margin-top: 0.95rem;
		background: var(--jup-down-bg);
		color: var(--jup-down-text);
		border-radius: var(--jup-radius-sm);
		padding: 0.6rem 0.75rem;
	}

	.jup-blocking-label {
		font-size: 0.7rem;
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
		font-size: 0.8rem;
	}

	/* `.jup-assessment` wraps, so the evidence list claims a full row of its own beneath the
	 * verdict rather than trailing off the end of it. */
	.jup-evidence,
	.jup-evidence-none {
		flex-basis: 100%;
		margin-left: 2.15rem;
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
		font-size: 0.78rem;
	}

	.jup-requirement {
		color: var(--jup-ink);
		font-family: var(--jup-font-mono);
		font-size: 0.76rem;
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
		font-size: 0.72rem;
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
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.04em;
	}

	.jup-tier-meaning {
		color: var(--jup-ink-soft);
		font-size: 0.72rem;
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

	.jup-figure-value {
		color: var(--jup-ink);
		font-size: 0.95rem;
		font-weight: 600;
	}

	.jup-figure-label {
		color: var(--jup-ink-soft);
		font-size: 0.8rem;
	}

	.jup-non-coverage {
		margin-top: 1.75rem;
		background: var(--jup-neu-bg);
		color: var(--jup-neu-text);
		border: 1px solid var(--jup-line);
		border-radius: var(--jup-radius);
		padding: 0.9rem 1.1rem;
	}

	.jup-non-coverage-label {
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.jup-non-coverage-list {
		margin-top: 0.45rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.8rem;
		list-style: disc;
		padding-left: 1.1rem;
	}
</style>
