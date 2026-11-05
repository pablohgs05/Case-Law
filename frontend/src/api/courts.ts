import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';

export type Court = {
  // The value the search's `tribunal` parameter takes, exactly as sent back.
  abbreviation: string;
  name: string;
};

type CourtsResponse = {
  courts: Court[];
};

export async function listCourts(): Promise<Court[]> {
  assertApiConfiguration();

  const url = new URL(`${apiBaseUrl}/courts`, window.location.origin);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: apiHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Courts request failed with status ${response.status}`);
  }

  return ((await response.json()) as CourtsResponse).courts;
}
