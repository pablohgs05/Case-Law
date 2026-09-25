import { apiBaseUrl, assertApiConfiguration } from './client';

// The four sections of the national court council's shape, without the labels
// the court wrote. `null` on the decision when the ementa is free prose.
export type EmentaSections = {
  headnote: string;
  case: string;
  question: string;
  reasoning: string;
  ruling: string;
};

export type Decision = {
  source: string;
  identifier: string;
  court: string;
  case_number: string | null;
  judging_body: string | null;
  reporting_judge: string | null;
  // Judgement date, or publication date when the court recorded no judgement.
  decided_on: string;
  small_claims: boolean;
  source_url: string;
  source_url_reachable: boolean | null;
  // The national council's number for the class. The API sends no name.
  class_code: number | null;
  judged_on: string | null;
  published_on: string | null;
  // The whole ementa. HTML with `<mark>` when asked with `q`, plain text without.
  summary: string;
  outcome: string | null;
  full_text_available: boolean;
  sections: EmentaSections | null;
};

// A failed read, carrying the status so a missing decision can be told apart
// from a server that did not answer.
export class DecisionRequestError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Decision request failed with status ${status}`);
    this.name = 'DecisionRequestError';
    this.status = status;
  }
}

// A decision is identified by its collection and the court's own identifier.
// The case number is not unique: one case can have several decisions.
export async function getDecision(
  source: string,
  identifier: string,
  options: { q?: string; signal?: AbortSignal } = {},
): Promise<Decision> {
  assertApiConfiguration();

  const path = `/decisions/${encodeURIComponent(source)}/${encodeURIComponent(identifier)}`;
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin);

  if (options.q) {
    url.searchParams.set('q', options.q);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new DecisionRequestError(response.status);
  }

  return (await response.json()) as Decision;
}
