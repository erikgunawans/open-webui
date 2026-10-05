import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider } from '@jup/ui';

import { demoMeeting } from '../../../demo';
import { agendaPlan } from '../../../layar-model';
import { V07Keputusan } from './V07Keputusan';

describe('Layar 07 decision list', () => {
	it('is a group of plain buttons, so ←/→ stay agenda keys with no listbox model to break', () => {
		const meeting = demoMeeting(0);
		const html = renderToStaticMarkup(
			<JupUIProvider storageKey={null}>
				<V07Keputusan
					meeting={meeting}
					agenda={agendaPlan(meeting)[7]}
					selected={null}
					onSelect={() => {}}
					onDecide={() => {}}
				/>
			</JupUIProvider>
		);
		expect(html).not.toMatch(/role="(listbox|option)"/);
		expect(html).toContain('aria-current="true"');
		expect(html).toContain('Tolak');
	});
});
