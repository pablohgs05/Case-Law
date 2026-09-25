import { apiBaseUrl, assertApiConfiguration } from './client';

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
  snippet: string;
};

export type SearchDecisionResponse = {
  total: number;
  page: number;
  page_size: number;
  results: SearchDecisionMatch[];
};

// The two orders the API accepts. `relevance` is its default, so it is left
// out of the request: the default search stays the same request it always was.
export type SearchOrder = 'relevance' | 'date';

export const DEFAULT_ORDER: SearchOrder = 'relevance';

export type SearchParams = {
  q: string;
  page?: number;
  page_size?: number;
  // Court abbreviations. Sent as one `tribunal` per court, which the API reads
  // as "any of these".
  tribunal?: string[];
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

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

export async function searchDecisions(params: SearchParams): Promise<SearchDecisionResponse> {
  assertApiConfiguration();

  const url = new URL(`${apiBaseUrl}/decisions`, window.location.origin);
  url.searchParams.set('q', params.q);

  if (params.page) {
    url.searchParams.set('page', String(params.page));
  }

  if (params.page_size) {
    url.searchParams.set('page_size', String(params.page_size));
  }

  for (const court of params.tribunal ?? []) {
    url.searchParams.append('tribunal', court);
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

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return (await response.json()) as SearchDecisionResponse;
}
