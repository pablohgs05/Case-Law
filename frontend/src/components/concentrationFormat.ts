import type { Concentration } from '../api/indicators';

export type ConcentrationState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; concentration: Concentration };

// How many groups are ranked before the rest is folded into one slice. The
// API answers exactly this many, so the screen and the rule it states agree.
export const CONCENTRATION_LIMIT = 5;

// Below this, one decision moves a share by more than three points, and a
// reporting judge with two of five decisions would read as "40% of the theme".
// The cut is then too small to say where anything concentrates.
export const MIN_CONCENTRATION_CUT = 30;
