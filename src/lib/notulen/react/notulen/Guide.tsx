import { Card } from '@jup/ui';

import { GUIDE_HTML } from '../../schema';

// The original template guide, rendered in full. GUIDE_HTML is generated from the handoff at
// build time (scripts/gen-schema.ts) and holds no scripts or handlers; nothing user-entered
// reaches it.

export const Guide = () => (
	<section className="nt-agenda" aria-labelledby="nt-h-guide">
		<header className="nt-ahead">
			<div className="nt-eyebrow">Panduan asli — ditampilkan lengkap</div>
			<h2 className="nt-h2" id="nt-h-guide">
				Panduan & checklist
			</h2>
		</header>
		<Card padding="lg">
			<div className="nt-guide" dangerouslySetInnerHTML={{ __html: GUIDE_HTML }} />
		</Card>
	</section>
);
