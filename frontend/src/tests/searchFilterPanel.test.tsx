import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

// Only the address is replaced: the request code under test is the real one,
// and it reads the base URL from the environment, which a test run should not
// depend on.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

type Court = { abbreviation: string; name: string };

const COURTS: Court[] = [
  { abbreviation: 'STJ', name: 'Superior Tribunal de Justiça' },
  { abbreviation: 'TJDFT', name: 'Tribunal de Justiça do Distrito Federal e dos Territórios' },
];

const DECISION = {
  source: 'tjdft-jurisdf',
  identifier: '2164119',
  court: 'TJDFT',
  case_number: '0812659-17.2025.8.07.0016',
  judging_body: '1ª TURMA CÍVEL',
  reporting_judge: 'ANA CANTARINO',
  decided_on: '2026-03-10',
  small_claims: false,
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2164119',
  source_url_reachable: true,
  snippet: '<mark>Dano</mark> <mark>moral</mark> configurado.',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function page(total: number, count = 1) {
  return {
    total,
    page: 1,
    page_size: 20,
    results: Array.from({ length: count }, (_, index) => ({
      ...DECISION,
      identifier: `${2164119 + index}`,
    })),
  };
}

type Handler = (url: URL) => Response | Promise<Response>;

// A stand-in for the API that answers what each test says and remembers every
// address the screen asked for.
function installApi(handlers: { courts?: Handler; decisions?: Handler } = {}) {
  const requested: URL[] = [];
  const courts = handlers.courts ?? (() => json({ courts: COURTS }));
  const decisions = handlers.decisions ?? (() => json(page(1)));

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requested.push(url);
      if (url.pathname === '/courts') return courts(url);
      if (url.pathname === '/decisions') return decisions(url);
      throw new Error(`unexpected request ${url}`);
    }),
  );

  const searches = () => requested.filter((url) => url.pathname === '/decisions');

  return {
    searches,
    lastSearch: (): URL | undefined => searches()[searches().length - 1],
    courtRequests: () => requested.filter((url) => url.pathname === '/courts'),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

async function renderPage() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: /filtros/i }));
  return user;
}

const court = (abbreviation: string) =>
  screen.findByRole('checkbox', { name: new RegExp(`^${abbreviation}\\b`) });

const setDate = (label: string, value: string) => {
  const group = screen.getByRole('group', { name: label });
  return (field: 'De' | 'Até') =>
    fireEvent.change(within(group).getByLabelText(field), { target: { value } });
};

const judged = (field: 'De' | 'Até', value: string) => setDate('Data de julgamento', value)(field);
const published = (field: 'De' | 'Até', value: string) =>
  setDate('Data de publicação (opcional)', value)(field);

const search = (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole('button', { name: 'Pesquisar' }));

const params = (url: URL | undefined) => {
  const entries = [...(url?.searchParams.keys() ?? [])];
  return [...new Set(entries)].sort();
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the court options', () => {
  it('come from the court list endpoint, by the abbreviation it returns', async () => {
    const api = installApi();
    await renderPage();

    expect(await court('STJ')).toBeInTheDocument();
    expect(await court('TJDFT')).toBeInTheDocument();
    expect(api.courtRequests()).toHaveLength(1);
  });

  it('say they are loading while the list is on its way', async () => {
    const pending = deferred<Response>();
    installApi({ courts: () => pending.promise });
    await renderPage();

    expect(screen.getByRole('status')).toHaveTextContent('Carregando tribunais');

    await act(async () => pending.resolve(json({ courts: COURTS })));
    expect(await court('TJDFT')).toBeInTheDocument();
  });

  it('say so when the list fails, and load it again on retry', async () => {
    let calls = 0;
    const api = installApi({
      courts: () => (++calls === 1 ? json({ detail: 'down' }, 503) : json({ courts: COURTS })),
    });
    const user = await renderPage();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar a lista de tribunais');
    expect(screen.queryByText(/Nenhum tribunal com decisões/)).not.toBeInTheDocument();

    await user.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));

    expect(await court('TJDFT')).toBeInTheDocument();
    expect(api.courtRequests()).toHaveLength(2);
  });

  it('say there is none when the endpoint answers an empty list', async () => {
    installApi({ courts: () => json({ courts: [] }) });
    await renderPage();

    expect(await screen.findByText(/Nenhum tribunal com decisões/)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });
});

describe('choosing courts', () => {
  it('selects several and unselects one by choosing it again', async () => {
    const api = installApi();
    const user = await renderPage();

    await user.click(await court('TJDFT'));
    await user.click(await court('STJ'));
    await user.click(await court('TJDFT'));

    expect(await court('TJDFT')).not.toBeChecked();
    expect(await court('STJ')).toBeChecked();

    await search(user);
    await waitFor(() => expect(api.searches()).toHaveLength(1));
    expect(api.lastSearch()?.searchParams.getAll('tribunal')).toEqual(['STJ']);
  });

  it('works from the keyboard, and Enter in the search box applies it', async () => {
    const api = installApi();
    const user = await renderPage();

    (await court('TJDFT')).focus();
    await user.keyboard(' ');
    expect(await court('TJDFT')).toBeChecked();

    await user.type(screen.getByLabelText('Pesquisar decisões'), '{Enter}');

    await waitFor(() => expect(api.searches()).toHaveLength(1));
    expect(api.lastSearch()?.searchParams.getAll('tribunal')).toEqual(['TJDFT']);
  });
});

describe('applying from the keyboard', () => {
  it('Enter in a date field applies, since the search button sits above the panel', async () => {
    const api = installApi();
    await renderPage();

    judged('De', '2026-01-01');
    const field = within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText(
      'De',
    );
    fireEvent.keyDown(field, { key: 'Enter' });

    await waitFor(() => expect(api.searches()).toHaveLength(1));
    expect(api.lastSearch()?.searchParams.get('date_from')).toBe('2026-01-01');
  });

  it('Enter in a date field still refuses a backwards range', async () => {
    const api = installApi();
    await renderPage();

    judged('De', '2026-03-10');
    judged('Até', '2026-03-09');
    const field = within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText(
      'Até',
    );
    fireEvent.keyDown(field, { key: 'Enter' });

    expect(
      await within(screen.getByRole('group', { name: 'Data de julgamento' })).findByRole('alert'),
    ).toBeInTheDocument();
    expect(api.searches()).toHaveLength(0);
  });
});

describe('applying the filters', () => {
  it('sends nothing while the controls are being edited', async () => {
    const api = installApi();
    const user = await renderPage();

    await user.click(await court('TJDFT'));
    judged('De', '2026-01-01');
    published('Até', '2026-03-31');

    expect(api.searches()).toHaveLength(0);
  });

  it('sends each court and every day exactly as chosen, on the first page', async () => {
    const api = installApi();
    const user = await renderPage();

    await user.click(await court('TJDFT'));
    await user.click(await court('STJ'));
    judged('De', '2026-01-01');
    judged('Até', '2026-03-31');
    published('De', '2026-03-01');
    published('Até', '2026-04-15');
    await search(user);

    await waitFor(() => expect(api.searches()).toHaveLength(1));
    const sent = api.lastSearch()!.searchParams;
    expect(sent.getAll('tribunal')).toEqual(['TJDFT', 'STJ']);
    expect(sent.get('date_from')).toBe('2026-01-01');
    expect(sent.get('date_to')).toBe('2026-03-31');
    expect(sent.get('published_from')).toBe('2026-03-01');
    expect(sent.get('published_to')).toBe('2026-04-15');
    expect(sent.get('page')).toBe('1');
  });

  it('keeps the expression and the chosen search mode', async () => {
    const api = installApi();
    const user = await renderPage();
    const box = screen.getByLabelText('Pesquisar decisões');

    await user.clear(box);
    await user.type(box, 'dano moral');
    await user.click(screen.getByRole('button', { name: 'Frase exata' }));
    await user.click(await court('TJDFT'));
    await search(user);

    await waitFor(() => expect(api.searches()).toHaveLength(1));
    expect(api.lastSearch()?.searchParams.get('q')).toBe('dano moral');
    await waitFor(() => expect(box).toHaveValue('dano moral'));
    expect(screen.getByRole('button', { name: 'Frase exata' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('accepts the same day on both ends', async () => {
    const api = installApi();
    const user = await renderPage();

    judged('De', '2026-02-15');
    judged('Até', '2026-02-15');
    await search(user);

    await waitFor(() => expect(api.searches()).toHaveLength(1));
    expect(api.lastSearch()?.searchParams.get('date_from')).toBe('2026-02-15');
    expect(api.lastSearch()?.searchParams.get('date_to')).toBe('2026-02-15');
  });

  it('sends a single end alone', async () => {
    const api = installApi();
    const user = await renderPage();

    published('De', '2026-03-01');
    await search(user);

    await waitFor(() => expect(api.searches()).toHaveLength(1));
    expect(params(api.lastSearch())).toEqual(['page', 'page_size', 'published_from', 'q']);
  });

  it('shows the total and the list from the same answer', async () => {
    installApi({ decisions: () => json(page(1234, 2)) });
    const user = await renderPage();

    await user.click(await court('TJDFT'));
    await search(user);

    expect(await screen.findByText('1234')).toBeInTheDocument();
    expect(screen.getAllByRole('article')).toHaveLength(2);
  });

  it('goes back to an unrestricted search once every filter is removed', async () => {
    const api = installApi();
    const user = await renderPage();

    await user.click(await court('TJDFT'));
    judged('De', '2026-01-01');
    await search(user);
    await waitFor(() => expect(api.searches()).toHaveLength(1));

    await user.click(await court('TJDFT'));
    judged('De', '');
    await search(user);

    await waitFor(() => expect(api.searches()).toHaveLength(2));
    expect(params(api.lastSearch())).toEqual(['page', 'page_size', 'q']);
  });

  it('says when what is on screen was searched with other filters', async () => {
    installApi();
    const user = await renderPage();

    await search(user);
    await screen.findByText('Total de resultados:');
    await user.click(await court('TJDFT'));

    expect(screen.getByText(/ainda não foram aplicadas/)).toBeInTheDocument();
  });
});

describe('a backwards range', () => {
  it('is not sent, and the message sits by its fields', async () => {
    const api = installApi();
    const user = await renderPage();

    judged('De', '2026-03-10');
    judged('Até', '2026-03-09');
    await search(user);

    const group = screen.getByRole('group', { name: 'Data de julgamento' });
    expect(within(group).getByRole('alert')).toHaveTextContent(
      'A data final deve ser igual ou posterior à data inicial.',
    );
    expect(within(group).getByLabelText('Até')).toHaveAttribute('aria-invalid', 'true');
    expect(within(group).getByLabelText('De')).toHaveValue('2026-03-10');
    expect(within(group).getByLabelText('Até')).toHaveValue('2026-03-09');
    expect(api.searches()).toHaveLength(0);
  });

  it('refused by the API lands on the period it named', async () => {
    installApi({
      decisions: () =>
        json({ detail: 'published_from must be less than or equal to published_to.' }, 400),
    });
    const user = await renderPage();

    await search(user);

    const group = screen.getByRole('group', { name: 'Data de publicação (opcional)' });
    expect(await within(group).findByRole('alert')).toHaveTextContent(
      'A data final deve ser igual ou posterior à data inicial.',
    );
  });
});

describe('a failed or overtaken search', () => {
  it('keeps what was chosen and shows no stale results', async () => {
    let calls = 0;
    installApi({
      decisions: () => (++calls === 1 ? json(page(7, 3)) : json({ detail: 'down' }, 500)),
    });
    const user = await renderPage();

    await search(user);
    expect(await screen.findAllByRole('article')).toHaveLength(3);

    await user.click(await court('TJDFT'));
    judged('De', '2026-01-01');
    await search(user);

    expect(await screen.findByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(await court('TJDFT')).toBeChecked();
    expect(
      within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText('De'),
    ).toHaveValue('2026-01-01');
  });

  it('never lets a late answer replace the newer one', async () => {
    const first = deferred<Response>();
    let calls = 0;
    installApi({
      decisions: () => (++calls === 1 ? first.promise : json(page(222))),
    });
    await renderPage();

    const form = screen.getByRole('button', { name: 'Pesquisar' }).closest('form')!;
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(await screen.findByText('222')).toBeInTheDocument();

    await act(async () => first.resolve(json(page(111))));

    expect(screen.getByText('222')).toBeInTheDocument();
    expect(screen.queryByText('111')).not.toBeInTheDocument();
  });
});
