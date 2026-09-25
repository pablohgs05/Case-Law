import { describe, expect, it } from 'vitest';

import {
  countFilters,
  errorsFromApi,
  INVERTED_RANGE_MESSAGE,
  NO_FILTERS,
  rangeErrors,
  sameFilters,
  toSearchParams,
} from '../search/filters';

describe('a date range', () => {
  it('is refused when it ends before it starts', () => {
    expect(rangeErrors({ ...NO_FILTERS, dateFrom: '2026-03-10', dateTo: '2026-03-09' })).toEqual({
      judged: INVERTED_RANGE_MESSAGE,
    });
  });

  it('accepts the same day on both ends', () => {
    expect(rangeErrors({ ...NO_FILTERS, dateFrom: '2026-03-10', dateTo: '2026-03-10' })).toEqual(
      {},
    );
  });

  it('accepts either end alone', () => {
    expect(rangeErrors({ ...NO_FILTERS, dateFrom: '2026-03-10' })).toEqual({});
    expect(rangeErrors({ ...NO_FILTERS, dateTo: '2026-03-10' })).toEqual({});
  });

  it('checks the publication period on its own', () => {
    expect(
      rangeErrors({ ...NO_FILTERS, publishedFrom: '2026-04-02', publishedTo: '2026-04-01' }),
    ).toEqual({ published: INVERTED_RANGE_MESSAGE });
  });

  it('compares across months and years by the day, not by the text of the day', () => {
    expect(rangeErrors({ ...NO_FILTERS, dateFrom: '2025-12-31', dateTo: '2026-01-01' })).toEqual(
      {},
    );
  });
});

describe('the parameters sent to the search', () => {
  it('leave every empty filter out', () => {
    expect(toSearchParams('dano moral', NO_FILTERS)).toEqual({
      q: 'dano moral',
      page: 1,
      page_size: 20,
      tribunal: undefined,
      date_from: undefined,
      date_to: undefined,
      published_from: undefined,
      published_to: undefined,
    });
  });

  it('carry the courts and the days exactly as chosen', () => {
    const params = toSearchParams('dano moral', {
      courts: ['TJDFT', 'STJ'],
      dateFrom: '2026-01-01',
      dateTo: '2026-03-31',
      publishedFrom: '2026-03-01',
      publishedTo: '',
    });

    expect(params.tribunal).toEqual(['TJDFT', 'STJ']);
    expect(params.date_from).toBe('2026-01-01');
    expect(params.date_to).toBe('2026-03-31');
    expect(params.published_from).toBe('2026-03-01');
    expect(params.published_to).toBeUndefined();
  });

  it('always start on the first page', () => {
    expect(toSearchParams('x', { ...NO_FILTERS, courts: ['TJDFT'] }).page).toBe(1);
  });
});

describe('the applied-filter count', () => {
  it('counts each court and each period with at least one end', () => {
    expect(countFilters(NO_FILTERS)).toBe(0);
    expect(countFilters({ ...NO_FILTERS, courts: ['TJDFT', 'STJ'], dateTo: '2026-03-31' })).toBe(3);
  });
});

describe('comparing filters', () => {
  it('ignores the order courts were picked in', () => {
    expect(
      sameFilters(
        { ...NO_FILTERS, courts: ['STJ', 'TJDFT'] },
        { ...NO_FILTERS, courts: ['TJDFT', 'STJ'] },
      ),
    ).toBe(true);
  });

  it('notices a changed day', () => {
    expect(sameFilters(NO_FILTERS, { ...NO_FILTERS, dateFrom: '2026-01-01' })).toBe(false);
  });
});

describe('a range the API refused', () => {
  it('lands on the period the API named', () => {
    expect(errorsFromApi(400, 'date_from must be less than or equal to date_to.')).toEqual({
      judged: INVERTED_RANGE_MESSAGE,
    });
    expect(
      errorsFromApi(400, 'published_from must be less than or equal to published_to.'),
    ).toEqual({ published: INVERTED_RANGE_MESSAGE });
  });

  it('is not mistaken for any other failure', () => {
    expect(errorsFromApi(400, 'Part of the request is not text the database can read.')).toBe(null);
    expect(errorsFromApi(503, null)).toBe(null);
  });
});
