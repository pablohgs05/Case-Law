import { apiBaseUrl, assertApiConfiguration } from './client';
import { readDetail, SearchRequestError } from './search';
import { apiHeaders } from './token';

// Reading the thesis of a decision the court wrote none for.
//
// The only call in this client that costs the firm money, so it is never made
// on render, on hover, or on a list. A person asks, once, and the answer is
// kept on the server for whoever asks next.

// What came of the asking. `none` and `unverified` both show no thesis, but
// they mean opposite things: one is a fact about the decision, the other
// about the model, and the screen says which.
export type Outcome = 'read' | 'none' | 'unverified';

export type IdentifiedThesis = {
  outcome: Outcome;
  // Null when the tool could not identify a thesis it can stand behind. That
  // is an ordinary answer, not a failure.
  thesis: string | null;
  // The passage of the ementa the thesis was drawn from. The server found this
  // string in the ementa before answering, so the reader can check the reading
  // against the text in front of them.
  passage: string | null;
  model: string | null;
  // True when the reading already existed and no model was asked again.
  cached: boolean;
};

function url(path: string): URL {
  return new URL(`${apiBaseUrl}${path}`, window.location.origin);
}

export async function identifyThesis(
  source: string,
  identifier: string,
  options: { signal?: AbortSignal } = {},
): Promise<IdentifiedThesis> {
  assertApiConfiguration();

  const target = url(
    `/decisions/${encodeURIComponent(source)}/${encodeURIComponent(identifier)}/thesis`,
  );

  const response = await fetch(target.toString(), {
    method: 'POST',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  const body: unknown = await response.json();
  const record = (body ?? {}) as Partial<IdentifiedThesis>;

  const outcome: Outcome =
    record.outcome === 'read' || record.outcome === 'none' ? record.outcome : 'unverified';

  return {
    outcome,
    thesis: typeof record.thesis === 'string' && record.thesis.trim() ? record.thesis : null,
    passage: typeof record.passage === 'string' && record.passage.trim() ? record.passage : null,
    model: typeof record.model === 'string' && record.model.trim() ? record.model : null,
    cached: record.cached === true,
  };
}
