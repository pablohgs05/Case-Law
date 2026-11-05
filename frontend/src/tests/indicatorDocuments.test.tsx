import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from './renderApp';
import { selectIndicator } from '../search/indicatorSelection';
import TimelineChart from '../components/TimelineChart';
import { fetchPage, heldPage, resetBuffer } from '../search/resultsBuffer';
import { NO_FILTERS, toSearchParams } from '../search/filters';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
// Keep the real lazy renderer in this integration test.
void TimelineChart;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const decision = (n: number) => ({
  source: 'teste',
  identifier: String(n),
  court: 'STJ',
  case_number: `processo-${n}`,
  judging_body: 'CORTE ESPECIAL',
  reporting_judge: 'RELATOR A',
  decided_on: '2024-05-20',
  small_claims: null,
  source_url: 'https://example.test/decision',
  source_url_reachable: true,
  deliberation: null,
  snippet: 'Dano <mark>moral</mark> comprovado.',
});
function api(answer?: (url: URL) => Response | Promise<Response>, courtTotal = 7) {
  const requests: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requests.push(url);
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'STJ', name: 'Superior Tribunal de Justiça' }] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/indicators/last-update')
        return json({ state: 'loaded', updated_at: '2026-10-22T12:00:00Z' });
      if (url.pathname === '/indicators/volume-by-court')
        return json({
          total: Math.max(10, courtTotal),
          courts: [
            { abbreviation: 'STJ', name: 'Superior Tribunal de Justiça', decisions: courtTotal },
          ],
        });
      if (url.pathname === '/indicators/outcome-share')
        return json({
          total: 10,
          classified: 10,
          unclassified: 0,
          outcomes: [
            { outcome: 'provido', decisions: 4, share: 40 },
            { outcome: 'negado', decisions: 6, share: 60 },
            { outcome: 'parcialmente_provido', decisions: 0, share: 0 },
          ],
        });
      if (url.pathname === '/indicators/volume-by-period')
        return json({
          total: 10,
          granularity: 'quarter',
          periods: [
            { period: '2024-01-01', decisions: 3 },
            { period: '2024-04-01', decisions: 7 },
          ],
        });
      if (url.pathname === '/decisions') {
        if (
          url.searchParams.has('tribunal') ||
          url.searchParams.has('resultado') ||
          url.searchParams.has('date_to')
        ) {
          if (answer) return answer(url);
          const total =
            url.searchParams.get('resultado') === 'parcialmente_provido'
              ? 0
              : url.searchParams.has('resultado')
                ? 4
                : courtTotal;
          const page = Number(url.searchParams.get('page') ?? 1);
          const size = Number(url.searchParams.get('page_size') ?? 6);
          return json({
            total,
            page,
            page_size: size,
            results: Array.from(
              { length: Math.max(0, Math.min(size, total - (page - 1) * size)) },
              (_, n) => decision((page - 1) * size + n + 1),
            ),
          });
        }
        return json({ total: 1, page: 1, page_size: 6, results: [decision(0)] });
      }
      return json({
        ...decision(1),
        class_code: 198,
        judged_on: '2024-05-20',
        published_on: null,
        summary: 'Texto da decisão selecionada.',
        outcome: 'provido',
        full_text_available: false,
        sections: null,
      });
    }),
  );
  return requests;
}
beforeEach(() => {
  resetBuffer();
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
  // jsdom does not implement the native dialog API. Focus trapping and Escape
  // are also checked in the real browser, where showModal makes the page inert.
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: {
      configurable: true,
      value(this: HTMLDialogElement) {
        this.setAttribute('open', '');
      },
    },
    close: {
      configurable: true,
      value(this: HTMLDialogElement) {
        this.removeAttribute('open');
      },
    },
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
async function panorama() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await screen.findByRole('button', { name: /Consultar documentos de STJ/ });
  return user;
}
const lastSearch = (requests: URL[]) => {
  const searches = requests.filter((u) => u.pathname === '/decisions');
  return searches[searches.length - 1];
};

it('opens court documents by keyboard, paginates, reads a decision and restores the Panorama and focus', async () => {
  const requests = api();
  const user = await panorama();
  const target = screen.getByRole('button', { name: /Consultar documentos de STJ/ });
  target.focus();
  await user.keyboard('{Enter}');
  const drawer = await screen.findByRole('dialog', { name: 'STJ: 7 decisões' });
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.get('q')).toBe(
    'prescrição intercorrente em execução fiscal',
  );
  expect(lastSearch(requests).searchParams.getAll('tribunal')).toEqual(['STJ']);
  const beforePage = requests.length;
  await user.click(within(drawer).getByRole('button', { name: 'Próxima' }));
  await waitFor(() =>
    expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(1),
  );
  expect(lastSearch(requests).searchParams.get('page')).toBe('1');
  expect(lastSearch(requests).searchParams.get('page_size')).toBe('12');
  expect(requests).toHaveLength(beforePage);
  expect(within(drawer).queryByText('Carregando documentos do indicador...')).toBeNull();
  await user.click(within(drawer).getByRole('button', { name: 'Abrir decisão' }));
  await within(drawer).findByText('Texto da decisão selecionada.');
  await user.click(
    within(drawer).getByRole('button', { name: 'Voltar aos documentos do indicador' }),
  );
  expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(1);
  const count = requests.length;
  await user.click(
    within(drawer).getByRole('button', { name: 'Fechar documentos e voltar ao Panorama' }),
  );
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(target).toHaveFocus();
  expect(screen.getByRole('tab', { name: 'Panorama' })).toHaveAttribute('aria-selected', 'true');
  expect(requests).toHaveLength(count);
});
it('selects a result without dropping the expression and handles an empty category', async () => {
  const requests = api();
  const user = await panorama();
  await user.click(screen.getByRole('button', { name: 'Como os recursos foram julgados' }));
  await user.click(
    await screen.findByRole('button', { name: /Consultar documentos com resultado Provido:/ }),
  );
  let drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.getAll('resultado')).toEqual(['provido']);
  fireEvent(drawer, new Event('cancel', { bubbles: true, cancelable: true }));
  await user.click(
    screen.getByRole('button', {
      name: /Consultar documentos com resultado Parcialmente provido:/,
    }),
  );
  drawer = screen.getByRole('dialog');
  expect(await within(drawer).findByText(/Nenhum documento encontrado/)).toBeInTheDocument();
});
it('uses the declared quarter for period bounds and has no interactive target inside aria-hidden', async () => {
  const requests = api();
  const user = await panorama();
  await user.click(screen.getByRole('button', { name: 'Como o volume mudou' }));
  expect(screen.queryByText('Consultar documentos por período')).toBeNull();
  const target = await screen.findByRole('button', { name: /Consultar documentos de 2T\/2024/ });
  expect(target.closest('[aria-hidden="true"]')).toBeNull();
  target.focus();
  await user.keyboard('{Enter}');
  const drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.get('date_from')).toBe('2024-04-01');
  expect(lastSearch(requests).searchParams.get('date_to')).toBe('2024-06-30');
  await user.click(
    within(drawer).getByRole('button', { name: 'Fechar documentos e voltar ao Panorama' }),
  );
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Consultar documentos de 2T\/2024/ })).toHaveFocus(),
  );
  for (const button of document.querySelectorAll('.indicator-target'))
    expect(button.closest('[aria-hidden="true"]')).toBeNull();
});
it('disables the targets during loading, allows retry and discards a late response after closing', async () => {
  let resolve!: (response: Response) => void;
  let calls = 0;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  api(() => (++calls === 1 ? json({}, 503) : pending));
  const user = await panorama();
  await user.click(screen.getByRole('button', { name: /Consultar documentos de STJ/ }));
  const drawer = screen.getByRole('dialog');
  await within(drawer).findByRole('alert');
  await user.click(within(drawer).getByRole('button', { name: 'Tentar novamente' }));
  expect(within(drawer).getByRole('status')).toHaveTextContent('Carregando documentos');
  expect(screen.getByRole('button', { name: /Consultar documentos de STJ/ })).toBeDisabled();
  await user.click(
    within(drawer).getByRole('button', { name: 'Fechar documentos e voltar ao Panorama' }),
  );
  await act(async () => resolve(json({ total: 7, page: 1, page_size: 6, results: [decision(1)] })));
  expect(screen.queryByRole('dialog')).toBeNull();
});
it.each([
  ['month', '2024-02-01', '2024-02-01', '2024-02-29'],
  ['quarter', '2024-04-01', '2024-04-01', '2024-06-30'],
  ['year', '2024-01-01', '2024-01-01', '2024-12-31'],
] as const)(
  'adds a %s period to every original filter with inclusive bounds',
  (granularity, period, from, to) => {
    const original = {
      q: 'dano moral',
      tribunal: ['STJ', 'TJDFT'],
      orgao_julgador: ['CORTE'],
      relator: ['RELATOR A'],
      classe_cnj: [198],
      published_from: '2024-02-10',
      order: 'date' as const,
      page: 4,
    };
    const selected = selectIndicator(original, { kind: 'period', granularity, period, count: 2 });
    expect(selected.params).toEqual({ ...original, page: 1, date_from: from, date_to: to });
    expect(original.page).toBe(4);
  },
);
it('intersects original bounds and never turns incompatible selections into an unrestricted search', () => {
  expect(
    selectIndicator(
      { q: 'dano moral', date_from: '2024-05-10', date_to: '2024-05-20' },
      { kind: 'period', period: '2024-01-01', granularity: 'year', count: 2 },
    ).params,
  ).toMatchObject({ date_from: '2024-05-10', date_to: '2024-05-20' });
  expect(
    selectIndicator(
      { q: 'dano moral', tribunal: ['STJ'] },
      { kind: 'court', court: 'TJDFT', count: 0 },
    ).params,
  ).toBeNull();
  expect(
    selectIndicator(
      { q: 'dano moral', resultado: ['negado'] },
      { kind: 'outcome', outcome: 'provido', count: 0 },
    ).params,
  ).toBeNull();
});

it('opens one dimension at a time by keyboard without reloading indicators', async () => {
  const requests = api();
  const user = await panorama();
  expect(screen.getByRole('heading', { name: 'Panorama', level: 1 })).toBeInTheDocument();
  const courts = screen.getByRole('button', { name: 'Onde o tema se concentra' });
  const temporal = screen.getByRole('button', { name: 'Como o volume mudou' });
  const outcomes = screen.getByRole('button', { name: 'Como os recursos foram julgados' });
  expect(courts).toHaveAttribute('aria-expanded', 'true');
  expect(temporal).toHaveAttribute('aria-expanded', 'false');
  const indicatorRequests = () =>
    requests.filter((url) => url.pathname.startsWith('/indicators/')).length;
  const before = indicatorRequests();
  expect(before).toBeGreaterThanOrEqual(3);
  temporal.focus();
  await user.keyboard('{Enter}');
  expect(temporal).toHaveAttribute('aria-expanded', 'true');
  expect(courts).toHaveAttribute('aria-expanded', 'false');
  expect(document.getElementById('dimension-courts')).toHaveAttribute('hidden');
  await user.click(outcomes);
  expect(outcomes).toHaveAttribute('aria-expanded', 'true');
  expect(temporal).toHaveAttribute('aria-expanded', 'false');
  const target = screen.getByRole('button', {
    name: /Consultar documentos com resultado Provido:/,
  });
  expect(target.closest('[aria-hidden="true"]')).toBeNull();
  target.focus();
  await user.keyboard('{Enter}');
  const drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  await user.click(
    within(drawer).getByRole('button', { name: 'Fechar documentos e voltar ao Panorama' }),
  );
  expect(outcomes).toHaveAttribute('aria-expanded', 'true');
  expect(target).toHaveFocus();
  expect(indicatorRequests()).toBe(before);
});

it('shows removable context beside the original filters and restores the original cut inside the drawer', async () => {
  const requests = api();
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: /Filtros/ }));
  fireEvent.change(
    within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText('De'),
    { target: { value: '2024-02-01' } },
  );
  fireEvent.change(
    within(screen.getByRole('group', { name: 'Data de publicação (opcional)' })).getByLabelText(
      'De',
    ),
    { target: { value: '2024-02-10' } },
  );
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await user.click(await screen.findByRole('button', { name: /Consultar documentos de STJ/ }));
  const drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  const context = within(drawer).getByRole('group', { name: 'Filtros aplicados aos documentos' });
  expect(context).toHaveTextContent('Filtros aplicados: 3');
  const remove = within(context).getByRole('button', {
    name: 'Remover seleção do indicador Tribunal: STJ',
  });
  expect(remove).toBeVisible();
  expect(lastSearch(requests).searchParams.get('date_from')).toBe('2024-02-01');
  expect(lastSearch(requests).searchParams.get('published_from')).toBe('2024-02-10');
  await user.click(remove);
  await within(drawer).findByRole('heading', { name: 'Pesquisa original: 1 decisão' });
  await waitFor(() =>
    expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(1),
  );
  expect(context).toHaveTextContent('Filtros aplicados: 2');
  const restored = lastSearch(requests).searchParams;
  expect(restored.getAll('tribunal')).toEqual([]);
  expect(restored.get('date_from')).toBe('2024-02-01');
  expect(restored.get('published_from')).toBe('2024-02-10');
  expect(restored.get('q')).toBe('prescrição intercorrente em execução fiscal');
  expect(restored.get('page')).toBe('1');
  const before = requests.length;
  await user.click(within(drawer).getByRole('button', { name: 'Voltar ao Panorama' }));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(requests).toHaveLength(before);
  expect(screen.getByRole('button', { name: 'Onde o tema se concentra' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
});

it('browser Back closes the indicator and another selection works without reloading the Panorama', async () => {
  const requests = api();
  const user = await panorama();
  await user.click(screen.getByRole('button', { name: 'Como os recursos foram julgados' }));
  await user.click(
    screen.getByRole('button', { name: /Consultar documentos com resultado Provido:/ }),
  );
  await within(screen.getByRole('dialog')).findAllByRole('button', { name: 'Abrir decisão' });
  const countsBefore = requests.filter((url) => url.pathname.startsWith('/indicators/')).length;
  fireEvent.click(screen.getByTestId('browser-back'));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(screen.getByRole('button', { name: 'Como os recursos foram julgados' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  await user.click(
    screen.getByRole('button', { name: /Consultar documentos com resultado Negado:/ }),
  );
  const drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.getAll('resultado')).toEqual(['negado']);
  expect(requests.filter((url) => url.pathname.startsWith('/indicators/'))).toHaveLength(
    countsBefore,
  );
  await user.click(within(drawer).getByRole('button', { name: 'Voltar ao Panorama' }));
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('reopening the same indicator starts a fresh block instead of showing its previous documents', async () => {
  let generation = 2019;
  const requests = api(() =>
    json({
      total: 7,
      page: 1,
      page_size: 12,
      results: Array.from({ length: 7 }, (_, n) => decision(generation + n)),
    }),
  );
  const user = await panorama();
  const target = screen.getByRole('button', { name: /Consultar documentos de STJ/ });
  await user.click(target);
  await within(screen.getByRole('dialog')).findByText('processo-2019');
  await user.click(
    within(screen.getByRole('dialog')).getByRole('button', { name: 'Voltar ao Panorama' }),
  );
  const before = requests.filter(
    (url) => url.pathname === '/decisions' && url.searchParams.has('tribunal'),
  ).length;
  generation = 2024;
  await user.click(target);
  const drawer = screen.getByRole('dialog');
  await within(drawer).findByText('processo-2024');
  expect(within(drawer).queryByText('processo-2019')).toBeNull();
  expect(
    requests.filter((url) => url.pathname === '/decisions' && url.searchParams.has('tribunal')),
  ).toHaveLength(before + 1);
});

it('keeps visited pages and prefetched blocks without showing loading again inside the same cut', async () => {
  const requests = api(undefined, 31);
  const user = await panorama();
  await user.click(screen.getByRole('button', { name: /Consultar documentos de STJ/ }));
  const drawer = screen.getByRole('dialog');
  await within(drawer).findByText('processo-1');
  const selectedRequests = () =>
    requests.filter((url) => url.pathname === '/decisions' && url.searchParams.has('tribunal'));
  expect(selectedRequests()).toHaveLength(1);
  await user.click(within(drawer).getByRole('button', { name: 'Próxima' }));
  expect(within(drawer).getByText('processo-7')).toBeInTheDocument();
  expect(within(drawer).queryByText('Carregando documentos do indicador...')).toBeNull();
  await waitFor(() => expect(selectedRequests()).toHaveLength(2));
  // Page two prefetched the block carrying pages three and four.
  const cut = selectIndicator(
    {
      ...toSearchParams('prescrição intercorrente em execução fiscal', NO_FILTERS),
      order: 'relevance',
    },
    { kind: 'court', court: 'STJ', count: 31 },
  ).params!;
  await waitFor(() => expect(heldPage({ ...cut, page: 3 })).not.toBeNull());
  await user.click(within(drawer).getByRole('button', { name: 'Próxima' }));
  expect(within(drawer).getByText('processo-13')).toBeInTheDocument();
  expect(within(drawer).queryByText('Carregando documentos do indicador...')).toBeNull();
  await user.click(within(drawer).getByRole('button', { name: 'Anterior' }));
  expect(within(drawer).getByText('processo-7')).toBeInTheDocument();
  await user.click(within(drawer).getByRole('button', { name: 'Anterior' }));
  expect(within(drawer).getByText('processo-1')).toBeInTheDocument();
  expect(within(drawer).queryByText('Carregando documentos do indicador...')).toBeNull();
  expect(selectedRequests()).toHaveLength(2);
  expect(selectedRequests().map((url) => url.searchParams.get('page_size'))).toEqual(['12', '12']);
});

it('an older response cannot refill a reset buffer even when the next cut has exactly the same parameters', async () => {
  let resolveOld!: (response: Response) => void;
  let resolveNew!: (response: Response) => void;
  const old = new Promise<Response>((done) => {
    resolveOld = done;
  });
  const fresh = new Promise<Response>((done) => {
    resolveNew = done;
  });
  vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(old).mockReturnValueOnce(fresh));
  const params = { q: 'dano moral', tribunal: ['STJ'], resultado: ['provido'] };
  const first = fetchPage(params);
  resetBuffer();
  const second = fetchPage(params);
  resolveNew(json({ total: 1, page: 1, page_size: 12, results: [decision(2024)] }));
  await second;
  resolveOld(json({ total: 1, page: 1, page_size: 12, results: [decision(2019)] }));
  await first;
  expect(heldPage(params)?.results[0].identifier).toBe('2024');
});

it.each([
  ['Onde o tema se concentra', /Consultar documentos de STJ/, [1, 2, 3]],
  ['Como o volume mudou', /Consultar documentos de 2024:/, [1, 2, 3, 4]],
  ['Como os recursos foram julgados', /Consultar documentos com resultado Provido:/, [1, 3]],
] as const)(
  'the actual list agrees with %s and keeps the original date cut',
  async (dimension, targetName, expectedIds) => {
    api();
    const fallback = globalThis.fetch;
    const requests: URL[] = [];
    const collection = [
      { ...decision(0), decided_on: '2023-12-31', court: 'STJ', outcome: 'provido' },
      { ...decision(1), decided_on: '2024-01-01', court: 'STJ', outcome: 'provido' },
      { ...decision(2), decided_on: '2024-02-29', court: 'STJ', outcome: 'negado' },
      { ...decision(3), decided_on: '2024-12-31', court: 'STJ', outcome: 'provido' },
      { ...decision(4), decided_on: '2024-12-31', court: 'TJDFT', outcome: 'negado' },
      { ...decision(5), decided_on: '2025-01-01', court: 'STJ', outcome: 'provido' },
    ];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        requests.push(url);
        const params = url.searchParams;
        const rows = collection.filter(
          (row) =>
            (!params.has('date_from') || row.decided_on >= params.get('date_from')!) &&
            (!params.has('date_to') || row.decided_on <= params.get('date_to')!) &&
            (!params.has('tribunal') || params.getAll('tribunal').includes(row.court)) &&
            (!params.has('resultado') || params.getAll('resultado').includes(row.outcome)),
        );
        if (url.pathname === '/decisions') {
          const page = Number(params.get('page') ?? 1);
          const size = Number(params.get('page_size') ?? 6);
          return json({
            total: rows.length,
            page,
            page_size: size,
            results: rows.slice((page - 1) * size, page * size),
          });
        }
        if (url.pathname === '/indicators/volume-by-court')
          return json({
            total: rows.length,
            courts: ['STJ', 'TJDFT'].map((court) => ({
              abbreviation: court,
              name: court,
              decisions: rows.filter((row) => row.court === court).length,
            })),
          });
        if (url.pathname === '/indicators/volume-by-period')
          return json({
            total: rows.length,
            granularity: 'year',
            periods: [{ period: '2024-01-01', decisions: rows.length }],
          });
        if (url.pathname === '/indicators/outcome-share')
          return json({
            total: rows.length,
            classified: rows.length,
            unclassified: 0,
            outcomes: ['provido', 'negado', 'parcialmente_provido'].map((outcome) => ({
              outcome,
              decisions: rows.filter((row) => row.outcome === outcome).length,
              share: (rows.filter((row) => row.outcome === outcome).length / rows.length) * 100,
            })),
          });
        return fallback(input);
      }),
    );
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: /Filtros/ }));
    const dates = within(screen.getByRole('group', { name: 'Data de julgamento' }));
    fireEvent.change(dates.getByLabelText('De'), { target: { value: '2024-01-01' } });
    fireEvent.change(dates.getByLabelText('Até'), { target: { value: '2024-12-31' } });
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await user.click(screen.getByRole('tab', { name: 'Panorama' }));
    await screen.findByRole('button', { name: /Consultar documentos de STJ/ });
    if (dimension !== 'Onde o tema se concentra')
      await user.click(screen.getByRole('button', { name: dimension }));
    const target = await screen.findByRole('button', { name: targetName });
    expect(target).toHaveAccessibleName(new RegExp(`${expectedIds.length} decisões`));
    expect(target.closest('[aria-hidden="true"]')).toBeNull();
    screen.getByRole('button', { name: dimension }).focus();
    for (let step = 0; step < 20 && document.activeElement !== target; step++) await user.tab();
    expect(target).toHaveFocus();
    await user.keyboard('{Enter}');
    const drawer = screen.getByRole('dialog');
    await waitFor(() =>
      expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(
        expectedIds.length,
      ),
    );
    for (const id of expectedIds) expect(within(drawer).getByText(`processo-${id}`)).toBeVisible();
    expect(within(drawer).queryByText('processo-0')).toBeNull();
    expect(within(drawer).queryByText('processo-5')).toBeNull();
    expect(within(drawer).queryByText(/A consulta retornou/)).toBeNull();
    expect(
      within(drawer).getByRole('button', { name: /Remover seleção do indicador/ }),
    ).toBeVisible();
    const selected = lastSearch(requests).searchParams;
    expect(selected.get('date_from')).toBe('2024-01-01');
    expect(selected.get('date_to')).toBe('2024-12-31');
    expect(selected.get('q')).toBe('prescrição intercorrente em execução fiscal');
    await user.click(within(drawer).getByRole('button', { name: /Remover seleção do indicador/ }));
    await waitFor(() =>
      expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(4),
    );
    await user.click(within(drawer).getByRole('button', { name: 'Voltar ao Panorama' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByRole('button', { name: dimension })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  },
);

it('a rapid double click opens one selection, makes one request and needs only one return', async () => {
  const requests = api();
  const user = await panorama();
  const target = screen.getByRole('button', { name: /Consultar documentos de STJ/ });
  await user.dblClick(target);
  const drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(
    requests.filter((url) => url.pathname === '/decisions' && url.searchParams.has('tribunal')),
  ).toHaveLength(1);
  await user.click(within(drawer).getByRole('button', { name: 'Voltar ao Panorama' }));
  expect(screen.queryByRole('dialog')).toBeNull();
});

describe('o trecho destacado na lista vinda do indicador', () => {
  const original = { q: 'dano moral' };

  it('aponta para o dispositivo quando o indicador é o de resultado', () => {
    // A classificação foi lida do dispositivo, então é ali que o trecho é
    // recortado. Medido sobre decisões com tese escrita, destacar os termos
    // da busca punha 31,5% dos trechos na "questão em discussão" e 2,25% na
    // tese — a pergunta no lugar da resposta.
    const selected = selectIndicator(original, { kind: 'outcome', outcome: 'negado', count: 3 });

    expect(selected.params?.highlight).toBe('resultado');
  });

  it('não pede destaque nos indicadores sem inferência nossa', () => {
    // Tribunal e período vêm de campo copiado da fonte: não há passagem que
    // justifique a classificação, e os termos do leitor continuam certos.
    const porTribunal = selectIndicator(original, { kind: 'court', court: 'STJ', count: 3 });
    const porPeriodo = selectIndicator(original, {
      kind: 'period',
      period: '2026-03',
      granularity: 'month',
      count: 3,
    });

    expect(porTribunal.params?.highlight).toBeUndefined();
    expect(porPeriodo.params?.highlight).toBeUndefined();
  });

  it('deixa a busca comum intocada', () => {
    expect(original).not.toHaveProperty('highlight');
  });
});
