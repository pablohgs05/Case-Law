import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';

export type FilterOption<T = string> = { value: T; label: string };
export type FilterOptions = {
  judging_bodies: FilterOption[];
  reporting_judges: FilterOption[];
  procedural_classes: FilterOption<number>[];
};

export async function listFilterOptions(): Promise<FilterOptions> {
  assertApiConfiguration();
  const response = await fetch(new URL(`${apiBaseUrl}/filters`, window.location.origin), {
    headers: apiHeaders(),
  });
  if (!response.ok) throw new Error(`Filter options request failed with status ${response.status}`);
  const body = (await response.json()) as FilterOptions;
  if (
    !Array.isArray(body.judging_bodies) ||
    !Array.isArray(body.reporting_judges) ||
    !Array.isArray(body.procedural_classes)
  )
    throw new Error('Invalid filter options response');
  return body;
}
