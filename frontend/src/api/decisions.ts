import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';

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
  source_url_shared: boolean;
  // The national council's number for the class. The API sends no name.
  class_code: number | null;
  judged_on: string | null;
  published_on: string | null;
  // The whole ementa. HTML with `<mark>` when asked with `q`, plain text without.
  summary: string;
  outcome: string | null;
  // What the court itself settled, one entry per item it numbered. Empty when
  // the court recorded none, which is most of the collection: the structured
  // ementa is a 2024 standard and the STJ's own reaches back to 1989.
  thesis: string[];
  // How the panel voted: 'unanime', 'maioria', or null when neither was read.
  deliberation: string | null;
  full_text_available: boolean;
  sections: EmentaSections | null;
  // Súmulas and temas the decision cites. Absent on an older API, which is why
  // the screen reads it through `readCitedPrecedents` rather than trusting it.
  precedents?: unknown;
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
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new DecisionRequestError(response.status);
  }

  return (await response.json()) as Decision;
}

// Read the thesis defensively: an environment serving a publication older than
// this build sends no field at all, and `.map` on `undefined` would take the
// whole card down over something that is absent on most of the collection
// anyway.
export function readThesis(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}
