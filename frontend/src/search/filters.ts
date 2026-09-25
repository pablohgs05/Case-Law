import type { SearchParams } from '../api/search';

export type SearchFilterValues = {
  // Abbreviations exactly as the API lists them. Empty means every court.
  courts: string[];
  // `YYYY-MM-DD`, what a date input holds and what the API reads. Empty means
  // the range is open on that side.
  dateFrom: string;
  dateTo: string;
  // The publication date alone. A decision without one is left out while
  // either end is set.
  publishedFrom: string;
  publishedTo: string;
};

export type DateGroup = 'judged' | 'published';

export type FilterErrors = Partial<Record<DateGroup, string>>;

export const NO_FILTERS: SearchFilterValues = {
  courts: [],
  dateFrom: '',
  dateTo: '',
  publishedFrom: '',
  publishedTo: '',
};

export const INVERTED_RANGE_MESSAGE = 'A data final deve ser igual ou posterior à data inicial.';

export const INCOMPLETE_DATE_MESSAGE = 'Preencha a data completa, no formato dd/mm/aaaa.';

export const PAGE_SIZE = 20;

// Both ends are `YYYY-MM-DD`, so comparing the strings compares the days, with
// no Date object and so no time zone to move a day. The same day on both ends
// is a valid one-day range.
function isInverted(from: string, to: string): boolean {
  return Boolean(from && to && to < from);
}

export function rangeErrors(values: SearchFilterValues): FilterErrors {
  const errors: FilterErrors = {};

  if (isInverted(values.dateFrom, values.dateTo)) {
    errors.judged = INVERTED_RANGE_MESSAGE;
  }
  if (isInverted(values.publishedFrom, values.publishedTo)) {
    errors.published = INVERTED_RANGE_MESSAGE;
  }

  return errors;
}

export function hasErrors(errors: FilterErrors): boolean {
  return Object.values(errors).some(Boolean);
}

// What the button's badge counts: each court, and each period with at least
// one end, since a single bound is a filter too.
export function countFilters(values: SearchFilterValues): number {
  return (
    values.courts.length +
    (values.dateFrom || values.dateTo ? 1 : 0) +
    (values.publishedFrom || values.publishedTo ? 1 : 0)
  );
}

export function sameFilters(a: SearchFilterValues, b: SearchFilterValues): boolean {
  const courts = (values: SearchFilterValues) => [...values.courts].sort().join('\n');

  return (
    courts(a) === courts(b) &&
    a.dateFrom === b.dateFrom &&
    a.dateTo === b.dateTo &&
    a.publishedFrom === b.publishedFrom &&
    a.publishedTo === b.publishedTo
  );
}

// Every new cut starts on the first page. Empty values are left out rather
// than sent blank: an absent parameter is what the API reads as "no filter".
export function toSearchParams(q: string, values: SearchFilterValues): SearchParams {
  return {
    q,
    page: 1,
    page_size: PAGE_SIZE,
    tribunal: values.courts.length > 0 ? values.courts : undefined,
    date_from: values.dateFrom || undefined,
    date_to: values.dateTo || undefined,
    published_from: values.publishedFrom || undefined,
    published_to: values.publishedTo || undefined,
  };
}

// The API answers a backwards range with 400 and a detail naming the parameter.
// Checked here too, so a rule the screen missed still lands on the right fields.
export function errorsFromApi(status: number, detail: string | null): FilterErrors | null {
  if (status !== 400 || !detail) {
    return null;
  }
  if (detail.startsWith('published_from')) {
    return { published: INVERTED_RANGE_MESSAGE };
  }
  if (detail.startsWith('date_from')) {
    return { judged: INVERTED_RANGE_MESSAGE };
  }
  return null;
}
