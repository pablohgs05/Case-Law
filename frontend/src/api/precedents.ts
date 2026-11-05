import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';
import { cutUrl, type VolumeParams } from './indicators';
import { readDetail, SearchRequestError } from './search';

// What the precedent endpoints answer. Two different questions share this
// module: which precedents one decision cites, and how a whole cut used the
// ones it cites.
//
// Every field may come back null: `null` means the answer did not carry it in
// a readable form, which is not the same as zero.

// The five the model records. `indeterminado` is a value, not an absence — a
// tool that guesses is worse than one that says it does not know.
export type Adherence = 'seguiu' | 'afastou' | 'distinguiu' | 'mencionou' | 'indeterminado';

export const ADHERENCES: readonly Adherence[] = [
  'seguiu',
  'afastou',
  'distinguiu',
  'mencionou',
  'indeterminado',
];

// One precedent a decision cited. `text` is null when the catalogue has no
// entry for it, which is 4% of citations: the citation is still real, and the
// screen shows it without a text rather than hiding it.
export type CitedPrecedent = {
  court: string;
  kind: string;
  number: number | null;
  text: string | null;
  status: string | null;
  settled_on: string | null;
  // The court's own words around the citation. This is what lets a reader
  // check the inferred label against what was actually written.
  snippet: string | null;
  adherence: Adherence | null;
  resolved: boolean;
  // Whether the ementa said which court settled it. A bare "Tema 793"
  // identifies no precedent: both courts have one, saying different things.
  court_stated: boolean;
};

export type AdherenceCount = {
  adherence: Adherence;
  links: number | null;
  // Never add these up to reach `citing`: a decision that followed one
  // precedent and set another aside counts in both rows.
  decisions: number | null;
  share: number | null;
};

// Three denominators, because confusing them produces a false percentage.
// `decisions` is the whole cut, `citing` the ones that cite anything at all,
// and `determined` the citations whose wording settled the question — the one
// every `share` is over.
export type AdherenceShare = {
  decisions: number | null;
  citing: number | null;
  links: number | null;
  determined: number | null;
  undetermined: number | null;
  adherences: AdherenceCount[];
};

export type MostCited = {
  court: string;
  kind: string;
  number: number | null;
  text: string | null;
  citations: number | null;
  decisions: number | null;
};

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const count = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;

const adherenceOf = (value: unknown): Adherence | null => {
  const name = text(value);
  return name && (ADHERENCES as readonly string[]).includes(name) ? (name as Adherence) : null;
};

export function readCitedPrecedent(value: unknown): CitedPrecedent | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const court = text(row.court);
  const kind = text(row.kind);

  // A citation with no court and kind cannot be named, let alone looked up.
  if (!court || !kind) {
    return null;
  }

  return {
    court,
    kind,
    number: count(row.number),
    text: text(row.text),
    status: text(row.status),
    settled_on: text(row.settled_on),
    snippet: text(row.snippet),
    adherence: adherenceOf(row.adherence),
    resolved: row.resolved === true,
    // Absent on an older API reads as stated, which is what every súmula is.
    court_stated: row.court_stated !== false,
  };
}

export function readCitedPrecedents(value: unknown): CitedPrecedent[] {
  return Array.isArray(value)
    ? value.map(readCitedPrecedent).filter((row): row is CitedPrecedent => row !== null)
    : [];
}

function readAdherenceCount(value: unknown): AdherenceCount | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const adherence = adherenceOf(row.adherence);

  if (!adherence) {
    return null;
  }

  return {
    adherence,
    links: count(row.links),
    decisions: count(row.decisions),
    share: count(row.share),
  };
}

export function readAdherenceShare(body: unknown): AdherenceShare {
  const raw = (body ?? {}) as Record<string, unknown>;

  return {
    decisions: count(raw.decisions),
    citing: count(raw.citing),
    links: count(raw.links),
    determined: count(raw.determined),
    undetermined: count(raw.undetermined),
    adherences: Array.isArray(raw.adherences)
      ? raw.adherences.map(readAdherenceCount).filter((row): row is AdherenceCount => row !== null)
      : [],
  };
}

function readMostCitedRow(value: unknown): MostCited | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const court = text(row.court);
  const kind = text(row.kind);

  if (!court || !kind) {
    return null;
  }

  return {
    court,
    kind,
    number: count(row.number),
    text: text(row.text),
    citations: count(row.citations),
    decisions: count(row.decisions),
  };
}

export function readMostCited(body: unknown): MostCited[] {
  return Array.isArray(body)
    ? body.map(readMostCitedRow).filter((row): row is MostCited => row !== null)
    : [];
}

// Fails the way the search does, with the API's detail, so a period the API
// refuses reads the same on every view of the cut.
export async function getAdherence(
  params: VolumeParams,
  options: { signal?: AbortSignal } = {},
): Promise<AdherenceShare> {
  assertApiConfiguration();

  const response = await fetch(cutUrl('/indicators/adherence', params).toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readAdherenceShare(await response.json());
}

export async function getMostCited(
  params: VolumeParams,
  options: { signal?: AbortSignal; limit?: number } = {},
): Promise<MostCited[]> {
  assertApiConfiguration();

  const url = cutUrl('/indicators/most-cited-precedents', params);
  if (options.limit) {
    url.searchParams.set('limit', String(options.limit));
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readMostCited(await response.json());
}

// Kept so a caller never has to know the base URL shape; the detail endpoint
// carries the precedents inline, so this is only for a screen that needs them
// without the rest of the decision.
export function precedentsUrl(source: string, identifier: string): string {
  return new URL(
    `${apiBaseUrl}/decisions/${encodeURIComponent(source)}/${encodeURIComponent(identifier)}`,
    window.location.origin,
  ).toString();
}
