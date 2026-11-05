import { afterEach, expect, it, vi } from 'vitest';

import { getOutcomeShare, getVolumeByCourt } from '../api/indicators';
import { searchDecisions } from '../api/search';
import { NO_FILTERS, toSearchParams } from '../search/filters';
import { fetchPage, heldPage, resetBuffer } from '../search/resultsBuffer';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://localhost:8000',
  assertApiConfiguration: () => undefined,
}));

afterEach(() => {
  vi.unstubAllGlobals();
  resetBuffer();
});

it('sends repeated filter parameters to search and both indicators', async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ total: 0, results: [], courts: [], outcomes: [] }),
  });
  vi.stubGlobal('fetch', fetch);
  const params = toSearchParams('dano moral', {
    ...NO_FILTERS,
    judgingBodies: ['CORTE ESPECIAL', 'PRIMEIRA TURMA'],
    reportingJudges: ['RELATOR A', 'RELATOR B'],
    proceduralClasses: [198, 213],
  });

  await searchDecisions(params);
  await getVolumeByCourt(params);
  await getOutcomeShare(params);

  expect(fetch).toHaveBeenCalledTimes(3);
  for (const [address] of fetch.mock.calls) {
    const query = new URL(String(address)).searchParams;
    expect(query.getAll('orgao_julgador')).toEqual(['CORTE ESPECIAL', 'PRIMEIRA TURMA']);
    expect(query.getAll('relator')).toEqual(['RELATOR A', 'RELATOR B']);
    expect(query.getAll('classe_cnj')).toEqual(['198', '213']);
  }
});

it('never serves the previous reporting judge from the results buffer', async () => {
  const fetch = vi.fn().mockImplementation(async (address: string) => {
    const judge = new URL(address).searchParams.get('relator');
    return {
      ok: true,
      json: async () => ({ total: 1, results: [{ reporting_judge: judge }] }),
    };
  });
  vi.stubGlobal('fetch', fetch);
  const first = toSearchParams('dano moral', { ...NO_FILTERS, reportingJudges: ['RELATOR A'] });
  const next = toSearchParams('dano moral', { ...NO_FILTERS, reportingJudges: ['RELATOR B'] });

  await fetchPage(first);
  expect(heldPage(first)?.results[0].reporting_judge).toBe('RELATOR A');
  expect(heldPage(next)).toBeNull();
  expect((await fetchPage(next)).results[0].reporting_judge).toBe('RELATOR B');
  expect(fetch).toHaveBeenCalledTimes(2);
});
