import { apiBaseUrl, assertApiConfiguration } from './client';

export type SearchDecisionMatch = {
  source: string;
  identifier: string;
  court: string;
  case_number: string;
  judging_body: string;
  reporting_judge: string;
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

export async function searchDecisions(params: {
  q: string;
  page?: number;
  page_size?: number;
}): Promise<SearchDecisionResponse> {
  assertApiConfiguration();

  const url = new URL(`${apiBaseUrl}/decisions`, window.location.origin);
  url.searchParams.set('q', params.q);

  if (params.page) {
    url.searchParams.set('page', String(params.page));
  }

  if (params.page_size) {
    url.searchParams.set('page_size', String(params.page_size));
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Search request failed with status ${response.status}`);
  }

  return (await response.json()) as SearchDecisionResponse;
}
