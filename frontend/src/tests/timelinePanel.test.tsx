import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderApp } from './renderApp';
// Preload the real renderer so cold dynamic-import compilation is outside
// the DOM assertion timeout. The production component remains lazy-loaded.
import TimelineChart from '../components/TimelineChart';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const series = (decisions = 12) => ({
  total: decisions,
  granularity: 'month',
  periods: [{ period: '2026-03-01', decisions }],
});
function api(answer: (url: URL) => Response | Promise<Response> = () => json(series())) {
  const requested: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requested.push(url);
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'STJ', name: 'STJ' }] });
      if (url.pathname === '/indicators/volume-by-period') return answer(url);
      if (url.pathname === '/decisions')
        return json({ total: 12, page: 1, page_size: 12, results: [] });
      if (url.pathname === '/indicators/volume-by-court') return json({ total: 12, courts: [] });
      if (url.pathname === '/indicators/outcome-share')
        return json({ total: 12, classified: 0, unclassified: 12, outcomes: [] });
      return json({ state: 'loaded', updated_at: '2026-10-20T12:00:00Z' });
    }),
  );
  return () => requested.filter((url) => url.pathname === '/indicators/volume-by-period');
}
beforeEach(() => {
  // jsdom has no layout; give the real Recharts renderer a measured viewport.
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    return {
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 800,
      bottom: 330,
      width: this.tagName === 'SPAN' ? 40 : 800,
      height: this.tagName === 'SPAN' ? 12 : 330,
      toJSON: () => ({}),
    };
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
it.each([
  ['month', 'Mar/26'],
  ['quarter', '1T/2026'],
  ['year', '2026'],
] as const)('formats %s periods in the accessible table', (granularity, label) => {
  render(
    <TimelineChart
      periods={[{ period: '2026-03-01', decisions: 12 }]}
      granularity={granularity}
      showValues={false}
    />,
  );
  expect(within(screen.getByRole('table')).getByText(label)).toBeInTheDocument();
});

it('distinguishes zero from an unknown count', () => {
  render(
    <TimelineChart
      periods={[
        { period: '2026-01-01', decisions: 0 },
        { period: '2026-02-01', decisions: null },
      ]}
      showValues={false}
    />,
  );
  const table = within(screen.getByRole('table'));
  expect(table.getByText('0')).toBeInTheDocument();
  expect(table.getByText('Não informado')).toBeInTheDocument();
});

const card = () => within(screen.getByRole('article', { name: 'Volume ao longo do tempo' }));
async function openTimeline(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  const toggle = screen.getByRole('button', { name: 'Como o volume mudou' });
  if (toggle.getAttribute('aria-expanded') === 'false') await user.click(toggle);
}

it('loads the applied search in Panorama, including court and dates, only once per cut', async () => {
  const requests = api();
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: /Filtros/ }));
  await user.click(await screen.findByRole('checkbox', { name: /^STJ/ }));
  fireEvent.change(
    within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText('De'),
    { target: { value: '2026-03-01' } },
  );
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  expect(requests()).toHaveLength(0);
  await openTimeline(user);
  await card().findByRole('table');
  expect(within(card().getByRole('table')).getByText('12')).toBeInTheDocument();
  expect(card().getByRole('table').parentElement).toHaveClass('sr-only');
  expect(card().queryByText('Consultar documentos por período')).toBeNull();
  expect(card().queryByText('Consultar valores por período')).toBeNull();
  expect(card().queryByText(/Agrupamento pela data/)).toBeNull();
  expect(requests()[0].searchParams.getAll('tribunal')).toEqual(['STJ']);
  expect(requests()[0].searchParams.get('date_from')).toBe('2026-03-01');
  expect(requests()[0].searchParams.has('page')).toBe(false);
  expect(requests()[0].searchParams.has('order')).toBe(false);
  await user.click(screen.getByRole('tab', { name: 'Documentos' }));
  await openTimeline(user);
  expect(requests()).toHaveLength(1);
});

it('retries a failed temporal request without presenting failure as an empty series', async () => {
  let calls = 0;
  api(() => (++calls === 1 ? json({}, 503) : json(series())));
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await openTimeline(user);
  await card().findByRole('alert');
  expect(card().queryByText(/Nenhum dado temporal/)).toBeNull();
  await user.click(card().getByRole('button', { name: 'Tentar novamente o gráfico temporal' }));
  await card().findByRole('table');
  expect(calls).toBe(2);
});

it('shows an empty state for a successful series without decisions', async () => {
  api(() => json({ total: 0, granularity: 'month', periods: [] }));
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await openTimeline(user);
  await card().findByText(/Nenhum dado temporal encontrado/);
  expect(card().queryByRole('alert')).toBeNull();
});

it('does not replace the new cut with a late answer from the previous search', async () => {
  let resolve!: (r: Response) => void;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  const requests = api((url) =>
    url.searchParams.get('q') === 'primeiro tema' ? pending : json(series(99)),
  );
  const user = userEvent.setup();
  renderApp();
  const box = screen.getByRole('searchbox', { name: 'Pesquisar decisões' });
  await user.clear(box);
  await user.type(box, 'primeiro tema');
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await openTimeline(user);
  await waitFor(() => expect(requests()).toHaveLength(1));
  expect(card().getByRole('status')).toHaveTextContent('Carregando');
  await user.clear(box);
  await user.type(box, 'segundo tema');
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await card().findByText('99');
  await act(async () => resolve(json(series(12))));
  expect(card().getByText('99')).toBeInTheDocument();
});

it('keeps the coverage warning visible and identifies a single period', async () => {
  api();
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await openTimeline(user);
  expect(await card().findByText('O recorte contém um único período.')).toBeInTheDocument();
  expect(screen.getByText(/Os tribunais têm janelas de cobertura diferentes/)).toBeVisible();
  await waitFor(() => expect(document.querySelector('.recharts-area-dot')).not.toBeNull());
});

it.each([
  ['month', 'Mar/26'],
  ['quarter', '1T/2026'],
  ['year', '2026'],
] as const)(
  'uses the declared %s granularity on the graphical axis',
  async (granularity, label) => {
    const { container } = render(
      <TimelineChart
        periods={[{ period: '2026-03-01', decisions: 12 }]}
        granularity={granularity}
        showValues={false}
      />,
    );
    await waitFor(() =>
      expect(
        [...container.querySelectorAll('svg text[orientation="bottom"]')]
          .map((tick) => tick.textContent)
          .join(' '),
      ).toContain(label),
    );
  },
);

it('draws the empty middle period at zero and keeps the same values in the text equivalent', async () => {
  const { container } = render(
    <TimelineChart
      periods={[
        { period: '2026-01-01', decisions: 2 },
        { period: '2026-02-01', decisions: 0 },
        { period: '2026-03-01', decisions: 3 },
      ]}
      showValues={false}
    />,
  );
  const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
  expect(rows.map((row) => within(row).getByRole('cell').textContent)).toEqual(['2', '0', '3']);
  // Three segments would have been joined directly if the zero bucket were dropped.
  await waitFor(() => {
    const path = container.querySelector('.recharts-area-curve')?.getAttribute('d') ?? '';
    expect(path).not.toBe('');
    expect(path.match(/[MC]/g)).toHaveLength(3);
  });
});

it.each([false, true])(
  'agrees with search totals derived from the same collection, narrowed=%s',
  async (narrowed) => {
    const collection = [
      { court: 'STJ', date: '2026-01-10' },
      { court: 'STJ', date: '2026-03-10' },
      { court: 'TJDFT', date: '2026-03-20' },
    ];
    const requests: URL[] = [];
    api();
    const fallback = globalThis.fetch;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        if (url.pathname !== '/decisions' && url.pathname !== '/indicators/volume-by-period')
          return fallback(input);
        requests.push(url);
        const courts = url.searchParams.getAll('tribunal');
        const rows = collection.filter((row) => !courts.length || courts.includes(row.court));
        if (url.pathname === '/decisions')
          return json({ total: rows.length, page: 1, page_size: 12, results: [] });
        return json({
          total: rows.length,
          granularity: 'month',
          periods: ['01', '02', '03'].map((month) => ({
            period: `2026-${month}-01`,
            decisions: rows.filter((row) => row.date.startsWith(`2026-${month}`)).length,
          })),
        });
      }),
    );
    const user = userEvent.setup();
    renderApp();
    if (narrowed) {
      await user.click(screen.getByRole('button', { name: /Filtros/ }));
      await user.click(await screen.findByRole('checkbox', { name: /^STJ/ }));
    }
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await waitFor(() =>
      expect(document.querySelector('.search-summary strong')).toHaveTextContent(
        narrowed ? '2' : '3',
      ),
    );
    const total = Number(document.querySelector('.search-summary strong')!.textContent);
    await openTimeline(user);
    const table = await card().findByRole('table');
    const sum = within(table)
      .getAllByRole('cell')
      .reduce((n, cell) => n + Number(cell.textContent), 0);
    expect(sum).toBe(total);
    expect(requests[0].searchParams.getAll('tribunal')).toEqual(
      requests[1].searchParams.getAll('tribunal'),
    );
  },
);

it('keeps the successful search available when the temporal indicator fails', async () => {
  api(() => json({}, 503));
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await waitFor(() =>
    expect(document.querySelector('.search-summary strong')).toHaveTextContent('12'),
  );
  await openTimeline(user);
  await card().findByRole('alert');
  await user.click(screen.getByRole('tab', { name: 'Documentos' }));
  expect(document.querySelector('.search-summary strong')).toHaveTextContent('12');
  expect(screen.getByRole('searchbox', { name: 'Pesquisar decisões' })).toBeEnabled();
});
