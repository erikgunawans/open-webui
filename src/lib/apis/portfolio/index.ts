import { WEBUI_API_BASE_URL } from '$lib/constants';

export type GateAssessment = {
	gate: string;
	verdict: 'pass' | 'fail';
	assessed_on: string;
	signed_by: string;
	source: string;
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
};

export type Portfolio = {
	projects: PortfolioProject[];
	// Set only when the records could not be read. The page shows the sentence, so a
	// misconfiguration is visible rather than looking like a clean portfolio.
	unavailable_reason: string | null;
};

export const getPortfolio = async (token: string = ''): Promise<Portfolio> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/portfolio/`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
