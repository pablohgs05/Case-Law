import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';
import { readDetail, SearchRequestError } from './search';

// The two doctrine endpoints: what was matched to one decision, and the
// collection itself. Both answer records and links, never the work.
//
// Every field may come back null: `null` means the answer did not carry it in
// a readable form, which is not the same as empty.

// One record from the collection. `date` is text and `year` is the number
// beside it, because a publication date is partial by nature — `1976`,
// `2001-12`, `1997/1998` — and a Date would invent a day nobody recorded.
export type Work = {
  repository: string;
  identifier: string;
  title: string;
  alternative_titles: string[];
  authors: string[];
  subjects: string[];
  type: string | null;
  date: string | null;
  year: number | null;
  language: string | null;
  publication: string | null;
  reference: string | null;
  url: string;
};

// A work matched to a decision's thesis, and why. `matched_on` carries word
// stems rather than words — `ma-f` is *má-fé* — because it is the record of
// what actually matched; turning stems back into words is the screen's job.
export type Suggestion = Work & {
  score: number | null;
  matched_on: string[];
};

export type DoctrineResults = {
  total: number | null;
  page: number | null;
  page_size: number | null;
  results: Work[];
};

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const count = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.map(text).filter((item): item is string => item !== null) : [];

export function readWork(value: unknown): Work | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const title = text(row.title);
  const url = text(row.url);

  // A record with no title is a blank line, and one with no link leads
  // nowhere. Either way there is nothing to show.
  if (!title || !url) {
    return null;
  }

  return {
    repository: text(row.repository) ?? '',
    identifier: text(row.identifier) ?? '',
    title,
    alternative_titles: strings(row.alternative_titles),
    authors: strings(row.authors),
    subjects: strings(row.subjects),
    type: text(row.type),
    date: text(row.date),
    year: count(row.year),
    language: text(row.language),
    publication: text(row.publication),
    reference: text(row.reference),
    url,
  };
}

export function readSuggestion(value: unknown): Suggestion | null {
  const work = readWork(value);

  if (!work) {
    return null;
  }

  const row = (value ?? {}) as Record<string, unknown>;

  return {
    ...work,
    score: count(row.score),
    // Without the terms the reader cannot judge the suggestion without
    // opening the work, which is the cost it exists to spare them.
    matched_on: strings(row.matched_on),
  };
}

export function readSuggestions(body: unknown): Suggestion[] {
  const raw = (body ?? {}) as Record<string, unknown>;

  return Array.isArray(raw.results)
    ? raw.results.map(readSuggestion).filter((row): row is Suggestion => row !== null)
    : [];
}

export function readDoctrineResults(body: unknown): DoctrineResults {
  const raw = (body ?? {}) as Record<string, unknown>;

  return {
    total: count(raw.total),
    page: count(raw.page),
    page_size: count(raw.page_size),
    results: Array.isArray(raw.results)
      ? raw.results.map(readWork).filter((row): row is Work => row !== null)
      : [],
  };
}

function url(path: string): URL {
  return new URL(`${apiBaseUrl}${path}`, window.location.origin);
}

// Enrichment, never the critical path: a caller that fails here shows the
// decision without the doctrine block rather than showing an error page.
export async function getRelatedDoctrine(
  source: string,
  identifier: string,
  options: { signal?: AbortSignal; limit?: number } = {},
): Promise<Suggestion[]> {
  assertApiConfiguration();

  const target = url(
    `/decisions/${encodeURIComponent(source)}/${encodeURIComponent(identifier)}/doctrine`,
  );
  if (options.limit) {
    target.searchParams.set('limit', String(options.limit));
  }

  const response = await fetch(target.toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readSuggestions(await response.json());
}

export async function searchDoctrine(
  q: string,
  options: { signal?: AbortSignal; page?: number; pageSize?: number } = {},
): Promise<DoctrineResults> {
  assertApiConfiguration();

  const target = url('/doctrine');
  target.searchParams.set('q', q);
  if (options.page) {
    target.searchParams.set('page', String(options.page));
  }
  if (options.pageSize) {
    target.searchParams.set('page_size', String(options.pageSize));
  }

  const response = await fetch(target.toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readDoctrineResults(await response.json());
}
