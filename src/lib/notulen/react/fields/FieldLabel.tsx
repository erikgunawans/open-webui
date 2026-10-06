import { labelOf, type PropDef } from '../../types';

/** A property's name. */
export const FieldLabel = ({ f }: { f: PropDef }) => <span className="nt-label">{labelOf(f)}</span>;
