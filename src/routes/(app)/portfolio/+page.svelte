<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { showSidebar } from '$lib/stores';
	import {
		getPortfolio,
		type EvidenceItem,
		type Portfolio,
		type PortfolioProject
	} from '$lib/apis/portfolio';
	import Spinner from '$lib/components/common/Spinner.svelte';

	import '$lib/styles/jup-brand.css';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The fail-closed stage gates, in ladder order. Rendering the whole ladder rather than only the
	// gate reached is what makes Current Gate legible as a derivation instead of a status field.
	const GATES = ['G1', 'G2', 'G3', 'G4'];

	let loaded = false;
	let portfolio: Portfolio | null = null;
	let loadError: string | null = null;

	const gateIsHeld = (project: PortfolioProject, gate: string) =>
		project.assessments.some((a) => a.gate === gate && a.verdict === 'pass');

	const gateWasRefused = (project: PortfolioProject, gate: string) =>
		project.assessments.some((a) => a.gate === gate && a.verdict === 'fail');

	// What the record cites the requirement against — an artefact path or an Engagement id. The
	// parser has already refused any item carrying neither, so there is no empty case to render.
	const citation = (item: EvidenceItem) => item.artefact ?? item.engagement ?? '';

	const citationKind = (item: EvidenceItem) =>
		item.artefact ? $i18n.t('Artefact') : $i18n.t('Engagement');

	onMount(async () => {
		try {
			portfolio = await getPortfolio(localStorage.token);
		} catch (error) {
			// A record the projection refuses to trust surfaces here. Saying so is the point: a gate
			// that cannot verify its own records must stop rather than render a confident blank.
			loadError = `${error}`;
			toast.error(loadError);
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
												<span class="jup-meta text-xs">
													{citationKind(item)}:&nbsp;{citation(item)}
												</span>
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
										</li>
									{/each}
								</ul>
							{:else}
								<p class="jup-meta mt-3 text-xs">
									{$i18n.t('This project has never been assessed against a gate.')}
								</p>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
</div>

<style>
	/* Colour comes from the ported JUP tokens. Accents are fills, so every word uses a `-text`
	 * variant — see src/lib/styles/jup-brand.css for the measured ratios. */
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
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
</style>
