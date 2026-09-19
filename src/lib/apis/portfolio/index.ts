import { WEBUI_API_BASE_URL } from '$lib/constants';

export type EvidenceItem = {
	requirement: string;
	satisfied: boolean;
	// Exactly one of these is set; the parser refuses an item carrying neither, so the page never
	// has to render a requirement with nothing to check it against. `engagement` is an id, resolved
	// against the Engagement records in a later slice — never an embedded copy of their state.
	artefact: string | null;
	engagement: string | null;
};

export type CertaintyTier = 'FAKTA' | 'POTENSI' | 'ILUSTRATIF';

export type Figure = {
	label: string;
	// Written text, never a number — a parsed number is one something eventually adds up, and
	// the one sum this system must never compute is one that crosses tiers (D11).
	value: string;
	tier: CertaintyTier;
	tier_label: string;
	tier_meaning: string;
	basis: string;
};

export type TierGroup = {
	tier: CertaintyTier;
	label: string;
	meaning: string;
	figures: Figure[];
};

export type Engagement = {
	id: string;
	counterparty: string[];
	pillar: string | null;
	purpose: string;
	// The rung slug is what to branch on; `stage_label` is presentation and may be renamed
	// without a data migration. The ladder is closed — the parser refuses anything else.
	stage: 'no-contact' | 'contacted' | 'in-discussion' | 'written-intent' | 'executed';
	stage_label: string;
	artefact: string;
	// There is deliberately no likelihood, probability, expected-close or confidence field on
	// this type, and no UI control for one (ADR-0009). An engagement records where it stands,
	// never whether it will close. Its absence is the point; do not add one.
};

export type GateAssessment = {
	gate: string;
	verdict: 'pass' | 'fail';
	assessed_on: string;
	signed_by: string;
	source: string;
	evidence: EvidenceItem[];
	// Unsatisfied citations only — a satisfied one is provenance, not a wait.
	awaiting_engagements: string[];
};

export type PortfolioProject = {
	id: string;
	name: string;
	pillar: string | null;
	// Derived from the assessments, never stored (ADR-0003). `null` means the project holds no
	// passing assessment — a different claim from holding no assessment at all, which is
	// `has_assessments: false`. The two must never render alike.
	current_gate: string | null;
	has_assessments: boolean;
	assessments: GateAssessment[];
	// Derived from the refusals only. A requirement left unmet under a passing verdict is a waiver
	// the board granted on the record, and is deliberately not listed as a blocker.
	blocking_requirements: EvidenceItem[];
	// Whose reply this project is waiting for, across all its refusals, each named once.
	awaiting_engagements: string[];
	// Grouped, and the only shape figures arrive in. Do not flatten this: a flat list is how
	// a feasibility NPV ends up beside a top-line revenue potential as though the two were
	// comparable, which is precisely what D11 prohibits. There is no total to render.
	figures_by_tier: TierGroup[];
};

export type Portfolio = {
	projects: PortfolioProject[];
	// One record per engagement, however many gates cite it (ADR-0008). Gates carry ids and
	// resolve them here, so a counterparty's stage exists in exactly one place.
	engagements: Engagement[];
	// What each view does not prove, shipped with the payload rather than written into the
	// markup, so it cannot go stale unnoticed.
	non_coverage: string[];
	engagement_non_coverage: string[];
	// Set only when the records could not be read. The page shows the sentence, so a
	// misconfiguration is visible rather than looking like a clean portfolio.
	unavailable_reason: string | null;
};

// Carries the status so the page can tell a refusal apart from a record it cannot trust.
// Both arrive here as a thrown error, and telling a member without access that the records
// are untrustworthy would send them to fix something that is not broken.
export class PortfolioRequestError extends Error {
	readonly status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = 'PortfolioRequestError';
		this.status = status;
	}

	// 403 from the operating-layer permission: signed in, understood, and still no. A 401
	// means the session is gone, which the app's own auth handling deals with elsewhere.
	get isAccessDenied(): boolean {
		return this.status === 403;
	}
}

export const getPortfolio = async (token: string = ''): Promise<Portfolio> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/portfolio/`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const body = await res.json().catch(() => null);
		const detail = body?.detail ?? `The portfolio request failed (${res.status}).`;
		const error = new PortfolioRequestError(res.status, `${detail}`);
		console.error(error);
		throw error;
	}

	return res.json();
};
