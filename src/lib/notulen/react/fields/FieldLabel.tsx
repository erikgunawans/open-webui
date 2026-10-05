import type { PropDef, PropType } from '../../types';

const TYPE_LABEL: Record<PropType, string> = {
	title: 'title',
	rich_text: 'teks',
	people: 'person',
	files: 'files',
	checkbox: 'checkbox',
	select: 'select',
	status: 'status',
	multi_select: 'multi-select',
	date: 'date',
	number: 'number',
	url: 'url'
};

/** A property's name, with its lowercase type beside it when "show types" is on. */
export const FieldLabel = ({ f, showType }: { f: PropDef; showType: boolean }) => (
	<span className="nt-label">
		{f.name}
		{showType ? <span className="nt-type">{TYPE_LABEL[f.type]}</span> : null}
	</span>
);
