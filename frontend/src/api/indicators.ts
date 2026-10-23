import { apiBaseUrl, assertApiConfiguration } from './client';
import { readDetail, SearchRequestError, type SearchParams } from './search';

// What `/indicators/coverage` answers: the base as a whole, never a search. It
// takes no parameter, so no expression, filter, order or page can reach it.
//
// Every field the screen shows may come back null here: `null` means the
// answer did not carry it in a readable form, which is not the same as zero.

export type CourtCoverage = {
  abbreviation: string;
  name: string | null;
  documents: number | null;
  // `YYYY-MM-DD`: the decisions' own dates (judgement, or publication when the
  // judgement date is missing), not when they were collected.
  first: string | null;
  last: string | null;
};

// Whether a load ever finished here. Read this rather than the absence of a
// date: a new environment and a broken pipeline both have no `updated_at`.
export type LoadState = 'loaded' | 'all_loads_failed' | 'never_loaded';

export type Coverage = {
  // Zero before the first load, which is an answer rather than an error.
  documents: number | null;
  first: string | null;
  last: string | null;
  // Largest first, as the API orders them.
  courts: CourtCoverage[];
  state: LoadState | null;
  // When the most recent successful load finished, in UTC: the collection's
  // date, not a decision's.
  updated_at: string | null;
};

// What `/indicators/volume-by-court` answers: the search's own cut, counted by
// court. It takes the search's expression and filters, never its order or
// page, and narrows through the same builder, so the total is the list's.
export type CourtVolume = {
  abbreviation: string;
  name: string | null;
  decisions: number | null;
};

export type VolumeByCourt = {
  // The courts' counts add up to it.
  total: number | null;
  // Busiest court first, as the API orders them. Empty when nothing matches.
  courts: CourtVolume[];
};

export type Granularity = 'month' | 'quarter' | 'year';

// What `/indicators/volume-by-period` answers: the search's own cut, counted by
// period (month, quarter, or year). The granularity adapts to the cut's amplitude
// unless explicitly specified. Months/periods with zero decisions inside the
// interval appear with count 0 so continuity is preserved.
export type PeriodVolume = {
  period: string;
  decisions: number | null;
};

export type VolumeByPeriod = {
  total: number | null;
  granularity: Granularity | null;
  periods: PeriodVolume[];
};

export type VolumePeriodParams = VolumeParams & {
  granularity?: Granularity | string;
};

// What `/indicators/last-update` answers: when the collection was last
// refreshed. It is the base's date, one for every court, not the cut's.
export type LastUpdate = {
  state: LoadState | null;
  updated_at: string | null;
};

// What `/indicators/outcome-share` answers: the same cut, counted by what the
// court decided. `classified` is the denominator of every `share`, and
// `unclassified` the rest — decisions the court did settle, but not as an
// appeal on its merits.
export type OutcomeCount = {
  outcome: string;
  decisions: number | null;
  share: number | null;
};

export type OutcomeShare = {
  total: number | null;
  classified: number | null;
  unclassified: number | null;
  outcomes: OutcomeCount[];
};

// An indicator that takes no search parameter failed: the coverage, or the
// freshness. Only the status is kept; there is no filter to point back to.
export class IndicatorRequestError extends Error {
  readonly status: number;

  constructor(indicator: string, status: number) {
    super(`${indicator} request failed with status ${status}`);
    this.name = 'IndicatorRequestError';
    this.status = status;
  }
}

const LOAD_STATES: readonly string[] = ['loaded', 'all_loads_failed', 'never_loaded'];

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const count = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;

function readCourt(value: unknown): CourtCoverage | null {
  const court = (value ?? {}) as Record<string, unknown>;
  const abbreviation = text(court.abbreviation);

  // A row with no court to name is no row at all.
  if (!abbreviation) {
    return null;
  }

  return {
    abbreviation,
    name: text(court.name),
    documents: count(court.documents),
    first: text(court.first),
    last: text(court.last),
  };
}

// Read field by field, so one field the screen cannot use leaves the others
// standing instead of taking the whole answer down.
export function readCoverage(body: unknown): Coverage {
  const raw = (body ?? {}) as Record<string, unknown>;
  const state = text(raw.state);

  return {
    documents: count(raw.documents),
    first: text(raw.first),
    last: text(raw.last),
    courts: Array.isArray(raw.courts)
      ? raw.courts.map(readCourt).filter((court): court is CourtCoverage => court !== null)
      : [],
    state: state && LOAD_STATES.includes(state) ? (state as LoadState) : null,
    updated_at: text(raw.updated_at),
  };
}

export async function getCoverage(options: { signal?: AbortSignal } = {}): Promise<Coverage> {
  assertApiConfiguration();

  // Nothing is appended: the coverage is the same whatever is being searched.
  const url = new URL(`${apiBaseUrl}/indicators/coverage`, window.location.origin);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new IndicatorRequestError('Coverage', response.status);
  }

  return readCoverage(await response.json());
}

// The cut the volume counts: the search's expression and filters, and nothing
// that only arranges the list. Order and page are not parameters here, so
// turning a page or re-sorting can never change a count.
export type VolumeParams = Pick<
  SearchParams,
  | 'q'
  | 'tribunal'
  | 'orgao_julgador'
  | 'relator'
  | 'classe_cnj'
  | 'date_from'
  | 'date_to'
  | 'published_from'
  | 'published_to'
>;

// The cut as the indicators take it, the same for every one of them.
function cutUrl(path: string, params: VolumeParams): URL {
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin);
  url.searchParams.set('q', params.q);

  for (const name of ['tribunal', 'orgao_julgador', 'relator', 'classe_cnj'] as const) {
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

  return url;
}

function readCourtVolume(value: unknown): CourtVolume | null {
  const court = (value ?? {}) as Record<string, unknown>;
  const abbreviation = text(court.abbreviation);

  if (!abbreviation) {
    return null;
  }

  return { abbreviation, name: text(court.name), decisions: count(court.decisions) };
}

export function readVolume(body: unknown): VolumeByCourt {
  const raw = (body ?? {}) as Record<string, unknown>;

  return {
    total: count(raw.total),
    courts: Array.isArray(raw.courts)
      ? raw.courts.map(readCourtVolume).filter((court): court is CourtVolume => court !== null)
      : [],
  };
}

// Fails the way the search does, with the API's detail, so a period the API
// refuses reads the same on both views of the cut.
export async function getVolumeByCourt(
  params: VolumeParams,
  options: { signal?: AbortSignal } = {},
): Promise<VolumeByCourt> {
  assertApiConfiguration();

  const response = await fetch(cutUrl('/indicators/volume-by-court', params).toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readVolume(await response.json());
}

function readPeriod(value: unknown): PeriodVolume | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const period = text(row.period);

  if (!period) {
    return null;
  }

  return { period, decisions: count(row.decisions) };
}

const GRANULARITIES: readonly string[] = ['month', 'quarter', 'year'];

export function readVolumeByPeriod(body: unknown): VolumeByPeriod {
  const raw = (body ?? {}) as Record<string, unknown>;
  const granularity = text(raw.granularity);

  return {
    total: count(raw.total),
    granularity:
      granularity && GRANULARITIES.includes(granularity) ? (granularity as Granularity) : null,
    periods: Array.isArray(raw.periods)
      ? raw.periods.map(readPeriod).filter((row): row is PeriodVolume => row !== null)
      : [],
  };
}

export async function getVolumeByPeriod(
  params: VolumePeriodParams,
  options: { signal?: AbortSignal } = {},
): Promise<VolumeByPeriod> {
  assertApiConfiguration();

  const url = cutUrl('/indicators/volume-by-period', params);
  if (params.granularity) {
    url.searchParams.set('granularity', params.granularity);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readVolumeByPeriod(await response.json());
}

function readOutcomeCount(value: unknown): OutcomeCount | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const outcome = text(row.outcome);

  if (!outcome) {
    return null;
  }

  return { outcome, decisions: count(row.decisions), share: count(row.share) };
}

export function readOutcomeShare(body: unknown): OutcomeShare {
  const raw = (body ?? {}) as Record<string, unknown>;

  return {
    total: count(raw.total),
    classified: count(raw.classified),
    unclassified: count(raw.unclassified),
    outcomes: Array.isArray(raw.outcomes)
      ? raw.outcomes.map(readOutcomeCount).filter((row): row is OutcomeCount => row !== null)
      : [],
  };
}

export async function getOutcomeShare(
  params: VolumeParams,
  options: { signal?: AbortSignal } = {},
): Promise<OutcomeShare> {
  assertApiConfiguration();

  const response = await fetch(cutUrl('/indicators/outcome-share', params).toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readOutcomeShare(await response.json());
}

export function readLastUpdate(body: unknown): LastUpdate {
  const raw = (body ?? {}) as Record<string, unknown>;
  const state = text(raw.state);

  return {
    state: state && LOAD_STATES.includes(state) ? (state as LoadState) : null,
    updated_at: text(raw.updated_at),
  };
}

// The collection's own date, as the load record has it — never the time the
// screen asked.
export async function getLastUpdate(options: { signal?: AbortSignal } = {}): Promise<LastUpdate> {
  assertApiConfiguration();

  const url = new URL(`${apiBaseUrl}/indicators/last-update`, window.location.origin);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new IndicatorRequestError('Last update', response.status);
  }

  return readLastUpdate(await response.json());
}
