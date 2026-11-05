import type { OutcomeCount, OutcomeShare } from '../api/indicators';

export type OutcomeState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; outcome: OutcomeShare };

export const OUTCOME_LABELS: Record<string, string> = {
  negado: 'Negado',
  provido: 'Provido',
  parcialmente_provido: 'Parcialmente provido',
};

export const outcomeLabel = (outcome: string) => OUTCOME_LABELS[outcome] ?? outcome;

// One order for the bar and the list beside it, so the two cannot disagree.
export function rankOutcomes(outcomes: OutcomeCount[]): OutcomeCount[] {
  return [...outcomes].sort((a, b) => {
    if (a.decisions !== b.decisions) {
      if (a.decisions === null) return 1;
      if (b.decisions === null) return -1;
      return b.decisions - a.decisions;
    }
    return a.outcome < b.outcome ? -1 : a.outcome > b.outcome ? 1 : 0;
  });
}

export const percent = (share: number) =>
  `${share.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
