import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';

export type SearchDecisionMatch = {
  source: string;
  identifier: string;
  court: string;
  // The API declares these three nullable and means it: a third of the
  // collection has no class name, and the reporter is missing on part of it.
  case_number: string | null;
  judging_body: string | null;
  reporting_judge: string | null;
  decided_on: string;
  small_claims: string | null;
  source_url: string;
  source_url_reachable: boolean | null;
  source_url_shared: boolean;
  // What the court itself settled. Empty on most of the collection, and an
  // API published before the field existed sends nothing at all.
  thesis?: string[];
  deliberation: string | null;
  snippet: string;
};

export type SearchDecisionResponse = {
  // Every match of the cut, not only this page.
  total: number;
  // The page served, counting from 1, and the size that was applied.
  page: number;
  page_size: number;
  // Where this page sits inside the total, counting from 1; null when the page
  // carries nothing. Optional: an API published before paging was stable does
  // not send them.
  range_from?: number | null;
  range_to?: number | null;
  results: SearchDecisionMatch[];
};

// The two orders the API accepts. `relevance` is its default, so it is left
// out of the request: the default search stays the same request it always was.
export type SearchOrder = 'relevance' | 'date';

export const DEFAULT_ORDER: SearchOrder = 'relevance';

// Which indicator the reader arrived from. The API cuts the snippet around
// what produced that classification instead of around what was typed; absent,
// it keeps showing the search terms, which is right in a plain search.
export type Highlight = 'resultado' | 'aderencia';

export type SearchParams = {
  q: string;
  page?: number;
  page_size?: number;
  // Court abbreviations. Sent as one `tribunal` per court, which the API reads
  // as "any of these".
  tribunal?: string[];
  // Exact option values and numeric CNJ codes. Repeated values combine with OR.
  orgao_julgador?: string[];
  relator?: string[];
  classe_cnj?: number[];
  resultado?: string[];
  highlight?: Highlight;
  // `YYYY-MM-DD`, passed through untouched.
  date_from?: string;
  date_to?: string;
  published_from?: string;
  published_to?: string;
  // Applied by the API over every match, before paging — never on the page.
  order?: SearchOrder;
};

// A failed search, carrying what the API said so the screen can tell a
// rejected filter from a server that is down.
export class SearchRequestError extends Error {
  readonly status: number;
  readonly detail: string | null;

  constructor(status: number, detail: string | null) {
    super(`Search request failed with status ${status}`);
    this.name = 'SearchRequestError';
    this.status = status;
    this.detail = detail;
  }
}

export async function readDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

export async function searchDecisions(
  params: SearchParams,
  options: { signal?: AbortSignal } = {},
): Promise<SearchDecisionResponse> {
  assertApiConfiguration();

  const url = new URL(`${apiBaseUrl}/decisions`, window.location.origin);
  url.searchParams.set('q', params.q);

  if (params.page) {
    url.searchParams.set('page', String(params.page));
  }

  if (params.page_size) {
    url.searchParams.set('page_size', String(params.page_size));
  }

  for (const name of [
    'tribunal',
    'orgao_julgador',
    'relator',
    'classe_cnj',
    'resultado',
  ] as const) {
    for (const value of params[name] ?? []) {
      url.searchParams.append(name, String(value));
    }
  }

  for (const name of ['date_from', 'date_to', 'published_from', 'published_to'] as const) {
    const value = params[name];
    if (value) {
      url.searchParams.set(name, value);
    }
  }

  if (params.order && params.order !== DEFAULT_ORDER) {
    url.searchParams.set('order', params.order);
  }

  if (params.highlight) {
    url.searchParams.set('highlight', params.highlight);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    signal: options.signal,
    headers: apiHeaders(),
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return (await response.json()) as SearchDecisionResponse;
}
