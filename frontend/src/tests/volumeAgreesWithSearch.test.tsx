import { fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

// Only the address is replaced: the request code under test is the real one,
// so the cut the screen asks each endpoint for is the cut it really sends.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

// One collection, answered by both routes. The point of the card is that the
// two numbers travel different paths — a count and an aggregation — so a fake
// that served each a number of its own could never catch them disagreeing.
// This one derives both from the same rows and honours the same filters, which
// leaves the screen as the only place a divergence can come from.
const COLLECTION = [
  ...Array.from({ length: 1200 }, (_, i) => ({ court: 'STJ', judged: '2026-02-10', n: i })),
  ...Array.from({ length: 640 }, (_, i) => ({ court: 'TJDFT', judged: '2026-05-20', n: i })),
  ...Array.from({ length: 7 }, (_, i) => ({ court: 'TRF3', judged: '2026-05-21', n: i })),
];

function cut(url: URL) {
  const courts = url.searchParams.getAll('tribunal');
  const from = url.searchParams.get('date_from');
  return COLLECTION.filter(
    (d) => (courts.length === 0 || courts.includes(d.court)) && (!from || d.judged >= from),
  );
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function decision(n: number, court: string) {
  return {
    source: 'teste',
    identifier: `${court}${n}`,
    court,
    case_number: `0700${n}-11.2026.8.07.0001`,
    judging_body: '1ª TURMA CÍVEL',
    reporting_judge: 'RELATOR',
    decided_on: '2026-05-20',
    small_claims: false,
    source_url: `https://exemplo.test/${court}${n}`,
    source_url_reachable: true,
    class_code: 198,
    judged_on: '2026-05-20',
    published_on: '2026-05-25',
    summary: `Ementa ${court}${n}.`,
    outcome: null,
    full_text_available: true,
    sections: null,
    snippet: 'Trecho.',
  };
}

function installApi() {
  const asked: Record<string, URL[]> = { decisions: [], volume: [] };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      const rows = cut(url);

      if (url.pathname === '/decisions') {
        asked.decisions.push(url);
        return json({
          total: rows.length,
          page: 1,
          page_size: 20,
          range_from: rows.length ? 1 : null,
          range_to: rows.length ? Math.min(20, rows.length) : null,
          results: rows.slice(0, 20).map((d) => decision(d.n, d.court)),
        });
      }

      if (url.pathname === '/indicators/volume-by-court') {
        asked.volume.push(url);
        const byCourt = new Map<string, number>();
        for (const row of rows) {
          byCourt.set(row.court, (byCourt.get(row.court) ?? 0) + 1);
        }
        return json({
          total: rows.length,
          courts: [...byCourt].map(([abbreviation, decisions]) => ({
            abbreviation,
            name: abbreviation,
            decisions,
          })),
        });
      }

      const detail = url.pathname.match(/^\/decisions\/[^/]+\/([^/]+)$/);
      if (detail) {
        const court = detail[1].replace(/\d+$/, '');
        return json(decision(Number(detail[1].replace(/^\D+/, '')), court));
      }

      if (url.pathname === '/indicators/last-update') {
        return json({ state: 'loaded', updated_at: '2026-09-18T14:42:03Z', records: 7 });
      }

      return json({
        courts: [
          { abbreviation: 'STJ', name: 'STJ' },
          { abbreviation: 'TJDFT', name: 'TJDFT' },
          { abbreviation: 'TRF3', name: 'TRF3' },
        ],
      });
    }),
  );
  return asked;
}

const digits = (text: string | null | undefined) => Number((text ?? '').replace(/\D/g, ''));

// What the reader is told beside the results.
function searchTotal(): number {
  const summary = document.querySelector('.search-summary strong');
  return digits(summary?.textContent);
}

// What the panorama says the same cut holds, and what its bars add up to.
function panoramaTotal(): number {
  // Scoped to the volume card: two panels now state the size of the cut,
  // and this test is about the one drawn beside the results.
  const panel = within(screen.getByRole('article', { name: 'Volume por tribunal' }));
  return digits(panel.getByText(/decis(ão|ões) no recorte/).textContent);
}

function barsAddUpTo(): number {
  return [...document.querySelectorAll('.volume-chart__value')].reduce(
    (sum, value) => sum + digits(value.textContent),
    0,
  );
}

async function search(user: ReturnType<typeof userEvent.setup>, expression: string) {
  const box = screen.getByLabelText('Pesquisar decisões');
  await user.clear(box);
  await user.type(box, expression);
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article', { name: /Ler a decisão|processo/ }).catch(() => null);
}

async function narrowByDate(user: ReturnType<typeof userEvent.setup>, from: string) {
  const toggle = screen.getByRole('button', { name: /filtros/i });
  if (toggle.getAttribute('aria-expanded') !== 'true') {
    await user.click(toggle);
  }
  const judged = screen.getByRole('group', { name: 'Data de julgamento' });
  fireEvent.change(within(judged).getByLabelText('De'), { target: { value: from } });
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article', { name: /Ler a decisão|processo/ }).catch(() => null);
}

async function openPanorama(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await within(screen.getByRole('article', { name: 'Volume por tribunal' })).findByText(
    /decis(ão|ões) no recorte/,
  );
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the chart and the results agree on how many there are', () => {
  it('shows the same number on both, over the whole base', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();

    await search(user, 'dano moral');
    const beside = searchTotal();
    await openPanorama(user);

    expect(beside).toBe(COLLECTION.length);
    expect(panoramaTotal()).toBe(beside);
    expect(barsAddUpTo()).toBe(beside);
  });

  it('still agrees once a filter narrows the cut', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();

    await search(user, 'dano moral');

    await narrowByDate(user, '2026-05-01');

    const beside = searchTotal();
    await openPanorama(user);

    expect(beside).toBe(647);
    expect(beside).toBeLessThan(COLLECTION.length);
    expect(panoramaTotal()).toBe(beside);
    expect(barsAddUpTo()).toBe(beside);
  });

  it('asks both endpoints for the same cut', async () => {
    const asked = installApi();
    const user = userEvent.setup();
    renderApp();

    await search(user, 'dano moral');
    await narrowByDate(user, '2026-05-01');
    await openPanorama(user);

    const narrowing = (url: URL) =>
      [
        url.searchParams.get('q'),
        url.searchParams.getAll('tribunal').sort().join(','),
        url.searchParams.get('date_from'),
        url.searchParams.get('date_to'),
      ].join('|');

    expect(asked.decisions.length).toBeGreaterThan(0);
    expect(asked.volume.length).toBeGreaterThan(0);
    const last = (urls: URL[]) => urls[urls.length - 1];
    expect(narrowing(last(asked.volume))).toBe(narrowing(last(asked.decisions)));
  });
});
