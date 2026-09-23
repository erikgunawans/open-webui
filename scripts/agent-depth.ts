/**
 * Print the agent-depth phase ledger from .planning/agent-depth-plan.md.
 *
 * The plan's "## Phase ledger" table is the source of truth; this only reads it, so the command
 * can never disagree with the plan. Usage: bun scripts/agent-depth.ts [--track A|V|H|I|P]
 */
import { join } from 'node:path';

const PLAN = join(import.meta.dir, '..', '.planning', 'agent-depth-plan.md');
const STATUSES = ['live', 'in-progress', 'ready', 'blocked', 'planned'] as const;
type Status = (typeof STATUSES)[number];
type Row = { id: string; phase: string; status: Status; closes: string; waits: string };

const ICON: Record<Status, string> = {
	live: '●',
	'in-progress': '◐',
	ready: '○',
	blocked: '■',
	planned: '·'
};

function ledger(markdown: string): Row[] {
	const start = markdown.indexOf('## Phase ledger');
	if (start < 0) throw new Error(`no "## Phase ledger" section in ${PLAN}`);
	const lines = markdown.slice(start).split('\n').slice(1);
	const rows: Row[] = [];
	for (const line of lines) {
		if (line.startsWith('## ')) break;
		if (!line.startsWith('|') || /^\|\s*-/.test(line) || /^\|\s*ID\s*\|/.test(line)) continue;
		const cells = line
			.split('|')
			.slice(1, -1)
			.map((c) => c.trim());
		if (cells.length !== 5)
			throw new Error(`ledger row has ${cells.length} cells, expected 5: ${line}`);
		const [id, phase, status, closes, waits] = cells;
		if (!STATUSES.includes(status as Status))
			throw new Error(`unknown status "${status}" on ${id}`);
		rows.push({ id, phase, status: status as Status, closes, waits });
	}
	if (rows.length === 0) throw new Error('the phase ledger is empty');
	return rows;
}

const trackArg = process.argv.indexOf('--track');
const track = trackArg > 0 ? process.argv[trackArg + 1]?.toUpperCase() : undefined;

const markdown = await Bun.file(PLAN).text();
const status = markdown.match(/^Status: (.*)$/m)?.[1] ?? 'unknown';
const rows = ledger(markdown).filter((r) => !track || r.id.startsWith(track));

const pad = (s: string, n: number) => (s.length >= n ? s : s + ' '.repeat(n - s.length));
const idW = Math.max(...rows.map((r) => r.id.length));
const phaseW = Math.min(52, Math.max(...rows.map((r) => r.phase.length)));
const statusW = Math.max(...rows.map((r) => r.status.length));

console.log(`Agent-depth plan — ${status.replace(/\*\*/g, '')}\n`);
for (const r of rows) {
	const waits = r.waits === '—' ? '' : `  ⟵ ${r.waits}`;
	console.log(
		`${ICON[r.status]} ${pad(r.id, idW)}  ${pad(r.phase, phaseW)}  ${pad(r.status, statusW)}${waits}`
	);
}

const count = (s: Status) => rows.filter((r) => r.status === s).length;
console.log(
	`\n${count('live')} live · ${count('in-progress')} in progress · ${count('ready')} ready · ` +
		`${count('blocked')} blocked · ${count('planned')} planned`
);
const next = rows.find((r) => r.status === 'in-progress') ?? rows.find((r) => r.status === 'ready');
if (next)
	console.log(
		`Next: ${next.id} ${next.phase}${next.waits === '—' ? '' : ` (waits on: ${next.waits})`}`
	);
