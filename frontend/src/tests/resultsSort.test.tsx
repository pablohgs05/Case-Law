import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

// Only the address is replaced: the request code under test is the real one.
// These answers are controlled, so they prove what the screen sends and shows,
// not that the API orders correctly — its own tests cover that.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

const APPLIED = 'prescrição intercorrente em execução fiscal';

function decision(identifier: string, decidedOn: string) {
  return {
    source: 'tjdft-jurisdf',
    identifier,
    court: 'TJDFT',
    case_number: `0000${identifier}-00.2026.8.07.0001`,
    judging_body: '1ª TURMA CÍVEL',
    reporting_judge: 'ANA CANTARINO',
    decided_on: decidedOn,
    small_claims: false,
    source_url: `https://jurisdf.tjdft.jus.br/detalhes/${identifier}`,
    source_url_reachable: true,
    snippet: `Trecho ${identifier}.`,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function page(total: number, results: ReturnType<typeof decision>[]) {
  return { total, page: 1, page_size: 20, results };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

type Handler = (url: URL) => Response | Promise<Response>;

// `answer` serves the search. The screen also opens the first result beside the
// list, so the detail endpoint gets its own answer, and only searches are kept
// in `sent` — the order is a matter of the search alone.
function installApi(answer: Handler) {
  const sent: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname !== '/decisions') {
        return json({ detail: 'Decision not found.' }, 404);
      }
      sent.push(url);
      return answer(url);
    }),
  );
  return {
    sent,
    last: () => sent[sent.length - 1],
  };
}

const byOrder: Handler = (url) =>
  url.searchParams.get('order') === 'date'
    ? json(page(1234, [decision('3', '2026-09-10'), decision('1', '2026-03-01')]))
    : json(page(1234, [decision('1', '2026-03-01'), decision('3', '2026-09-10')]));

async function searchFirst() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article');
  return user;
}

const sortBox = () => screen.getByRole('combobox', { name: 'Ordenar por' });

const shownOrder = () =>
  screen.getAllByRole('article').map((card) => card.getAttribute('aria-label'));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the order selector', () => {
  it('is not offered before there is a search to order', () => {
    installApi(byOrder);
    renderApp();

    expect(screen.queryByRole('combobox', { name: 'Ordenar por' })).toBeNull();
  });

  it('shows up beside the results on the order applied, relevance, sending no order', async () => {
    const api = installApi(byOrder);
    await searchFirst();

    expect(sortBox()).toHaveValue('relevance');
    expect(screen.getByRole('option', { name: 'Relevância' })).toHaveProperty('selected', true);
    expect(api.last().searchParams.has('order')).toBe(false);
  });
});

describe('changing the order', () => {
  it('asks the API for date, on the first page, with the applied expression', async () => {
    const api = installApi(byOrder);
    const user = await searchFirst();

    await user.selectOptions(sortBox(), 'date');

    await waitFor(() => expect(api.sent).toHaveLength(2));
    expect(api.last().searchParams.get('order')).toBe('date');
    expect(api.last().searchParams.get('page')).toBe('1');
    expect(api.last().searchParams.get('q')).toBe(APPLIED);
    expect(sortBox()).toHaveValue('date');
  });

  it('asks for relevance again by sending no order, the API default', async () => {
    const api = installApi(byOrder);
    const user = await searchFirst();
    await user.selectOptions(sortBox(), 'date');
    await waitFor(() => expect(api.sent).toHaveLength(2));
    await screen.findAllByRole('article');

    await user.selectOptions(sortBox(), 'relevance');

    await waitFor(() => expect(api.sent).toHaveLength(3));
    expect(api.last().searchParams.has('order')).toBe(false);
    expect(api.last().searchParams.get('q')).toBe(APPLIED);
  });

  it('keeps the applied filters, and not a filter still being edited', async () => {
    const api = installApi(byOrder);
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    const judged = screen.getByRole('group', { name: 'Data de julgamento' });
    fireEvent.change(within(judged).getByLabelText('De'), { target: { value: '2026-01-01' } });
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');

    // An edit to the panel after the search: not applied by the reorder.
    fireEvent.change(within(judged).getByLabelText('Até'), { target: { value: '2026-03-31' } });
    await user.selectOptions(sortBox(), 'date');

    await waitFor(() => expect(api.sent).toHaveLength(2));
    expect(api.last().searchParams.get('order')).toBe('date');
    expect(api.last().searchParams.get('date_from')).toBe('2026-01-01');
    expect(api.last().searchParams.has('date_to')).toBe(false);
    expect(api.last().searchParams.get('q')).toBe(APPLIED);
  });

  it('keeps the chosen search mode', async () => {
    installApi(byOrder);
    const user = await searchFirst();
    await user.click(screen.getByRole('button', { name: 'Frase exata' }));

    await user.selectOptions(sortBox(), 'date');
    await screen.findAllByRole('article');

    expect(screen.getByRole('button', { name: 'Frase exata' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('never applies an edit still in the search box', async () => {
    const api = installApi(byOrder);
    const user = await searchFirst();
    const box = screen.getByLabelText('Pesquisar decisões');

    await user.clear(box);
    await user.type(box, 'usucapiao');
    await user.selectOptions(sortBox(), 'date');

    await waitFor(() => expect(api.sent).toHaveLength(2));
    expect(api.last().searchParams.get('q')).toBe(APPLIED);
    expect(box).toHaveValue('usucapiao');
  });

  it('asks for nothing when the order already applied is chosen again', async () => {
    const api = installApi(byOrder);
    await searchFirst();

    fireEvent.change(sortBox(), { target: { value: 'relevance' } });

    expect(api.sent).toHaveLength(1);
  });

  it('keeps the chosen order for the next search', async () => {
    const api = installApi(byOrder);
    const user = await searchFirst();
    await user.selectOptions(sortBox(), 'date');
    await screen.findAllByRole('article');

    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    await waitFor(() => expect(api.sent).toHaveLength(3));
    expect(api.last().searchParams.get('order')).toBe('date');
  });
});

describe('the reordered results', () => {
  it('are shown exactly as the API returned them, with the new total', async () => {
    // Deliberately out of date order: the screen must not sort them itself.
    installApi((url) =>
      url.searchParams.get('order') === 'date'
        ? json(page(777, [decision('5', '2026-01-01'), decision('9', '2026-12-31')]))
        : json(page(1234, [decision('1', '2026-03-01')])),
    );
    const user = await searchFirst();

    await user.selectOptions(sortBox(), 'date');

    expect(await screen.findByText('777')).toBeInTheDocument();
    expect(shownOrder()).toEqual([
      'Decisão 00005-00.2026.8.07.0001',
      'Decisão 00009-00.2026.8.07.0001',
    ]);
  });

  it('never show the old list as if already in the new order', async () => {
    const pending = deferred<Response>();
    installApi((url) =>
      url.searchParams.get('order') === 'date' ? pending.promise : byOrder(url),
    );
    const user = await searchFirst();

    await user.selectOptions(sortBox(), 'date');

    expect(screen.queryAllByRole('article')).toHaveLength(0);
    // In the list itself: the empty detail panel beside it says the same.
    const list = document.querySelector<HTMLElement>('.search-results')!;
    expect(within(list).getByText('Carregando resultados...')).toBeInTheDocument();
    expect(sortBox()).toBeDisabled();

    await act(async () => pending.resolve(json(page(1234, [decision('3', '2026-09-10')]))));
    expect(await screen.findAllByRole('article')).toHaveLength(1);
  });

  it('are never replaced by a late answer to an older order', async () => {
    const late = deferred<Response>();
    let dateCalls = 0;
    installApi((url) => {
      if (url.searchParams.get('order') === 'date' && ++dateCalls === 1) return late.promise;
      return json(page(222, [decision('2', '2026-05-05')]));
    });
    const user = await searchFirst();

    await user.selectOptions(sortBox(), 'date');
    // A second search overtakes the first while it is still out.
    const form = screen.getByRole('button', { name: /Pesquis/ }).closest('form')!;
    fireEvent.submit(form);
    expect(await screen.findByText('222')).toBeInTheDocument();

    await act(async () => late.resolve(json(page(111, [decision('1', '2026-01-01')]))));

    expect(screen.getByText('222')).toBeInTheDocument();
    expect(screen.queryByText('111')).toBeNull();
  });
});

describe('a failed reorder', () => {
  it('says the update failed, shows no results, and retries the same order', async () => {
    let dateCalls = 0;
    const api = installApi((url) => {
      if (url.searchParams.get('order') === 'date' && ++dateCalls === 1) {
        return json({ detail: 'down' }, 503);
      }
      return byOrder(url);
    });
    const user = await searchFirst();

    await user.selectOptions(sortBox(), 'date');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível reordenar os resultados.');
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(screen.queryByText('1234')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));

    expect(await screen.findAllByRole('article')).toHaveLength(2);
    expect(api.last().searchParams.get('order')).toBe('date');
    expect(api.last().searchParams.get('q')).toBe(APPLIED);
  });
});
