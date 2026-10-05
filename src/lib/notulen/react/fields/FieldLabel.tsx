import type { PropDef } from '../../types';

/** A property's name. */
export const FieldLabel = ({ f }: { f: PropDef }) => <span className="nt-label">{f.name}</span>;
