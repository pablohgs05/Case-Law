import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import HomePage from '../pages/HomePage';
import SearchSessionProvider from '../search/SearchSessionProvider';
import { currentAddress, renderApp } from './renderApp';

// Only the address of the API is replaced: the request code under test is the
// real one. Every request is counted, so "no new search" is a number.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

function decision(identifier: string) {
  return {
    source: 'tjdft-jurisdf',
    identifier,
    court: 'TJDFT',
    case_number: `0700${identifier}-11.2026.8.07.0001`,
    judging_body: '1ª TURMA CÍVEL',
    reporting_judge: `RELATOR ${identifier}`,
    decided_on: '2026-03-10',
    small_claims: false,
    source_url: `https://jurisdf.tjdft.jus.br/detalhes/${identifier}`,
    source_url_reachable: true,
    class_code: 198,
    judged_on: '2026-03-10',
    published_on: '2026-03-15',
    summary: `Ementa ${identifier}.`,
    outcome: null,
    full_text_available: true,
    sections: null,
  };
}

const DECISIONS = ['1001', '1002', '1003'].map(decision);

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

type SearchAnswer = (url: URL) => Response | Promise<Response>;

// Searches and detail reads are kept apart: opening a decision reads its
// detail, and that must not be mistaken for — or hide — a search.
function installApi(search: SearchAnswer = () => json(page(57))) {
  const searches: URL[] = [];
  const details: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      const detail = url.pathname.match(/^\/decisions\/[^/]+\/([^/]+)$/);
      if (detail) {
        details.push(url.pathname);
        const found = DECISIONS.find((d) => d.identifier === detail[1]);
        return found ? json(found) : json({ detail: 'Decision not found.' }, 404);
      }
      if (url.pathname === '/decisions') {
        searches.push(url);
        return search(url);
      }
      return json({ courts: [] });
    }),
  );
  return { searches, details };
}

function page(total: number, identifiers = ['1001', '1002', '1003']) {
  return {
    total,
    page: 1,
    page_size: 20,
    results: identifiers.map((id) => ({ ...decision(id), snippet: `Trecho ${id}.` })),
  };
}

const card = (identifier: string) =>
  screen.getByRole('link', { name: new RegExp(`Ler a decisão do processo 0700${identifier}`) });

const panel = () => screen.getByRole('complementary');

async function searchWithContext() {
  const user = userEvent.setup();
  renderApp();
  // An expression, a mode, filters and an order applied with the search, to
  // check that every one of them comes back too.
  const box = screen.getByLabelText('Pesquisar decisões');
  await user.clear(box);
  await user.type(box, 'dano moral');
  await user.click(screen.getByRole('button', { name: 'Frase exata' }));
  await user.click(screen.getByRole('button', { name: /filtros/i }));
  const judged = screen.getByRole('group', { name: 'Data de julgamento' });
  fireEvent.change(within(judged).getByLabelText('De'), { target: { value: '2026-01-01' } });
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');
  await screen.findAllByRole('article');
  return user;
}

function expectContextKept() {
  expect(currentAddress()).toBe('/');
  expect(screen.getByLabelText('Pesquisar decisões')).toHaveValue('dano moral');
  expect(screen.getByRole('button', { name: 'Frase exata' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  expect(screen.getByText('57')).toBeInTheDocument();
  expect(screen.getAllByRole('article')).toHaveLength(3);
  expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toHaveValue('date');
  const judged = screen.getByRole('group', { name: 'Data de julgamento' });
  expect(within(judged).getByLabelText('De')).toHaveValue('2026-01-01');
  expect(screen.getByRole('button', { name: /Filtros/ })).toHaveTextContent('1');
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('back to the results', () => {
  it("by the screen's own action: the list as it was, and no new search", async () => {
    const api = installApi();
    const user = await searchWithContext();
    // The searches made so far: the initial one and the reorder.
    const searchesBefore = api.searches.length;
    expect(searchesBefore).toBe(2);
    expect(api.searches[searchesBefore - 1].searchParams.get('q')).toBe('dano moral');

    await user.click(card('1002'));
    expect(currentAddress()).toBe('/decisoes/tjdft-jurisdf/1002');
    await within(panel()).findByText('RELATOR 1002');
    // Opening it read its detail — a different request from a search.
    expect(api.details).toContain('/decisions/tjdft-jurisdf/1002');

    await user.click(within(panel()).getByRole('button', { name: 'Voltar aos resultados' }));

    expectContextKept();
    expect(api.searches).toHaveLength(searchesBefore);
    expect(card('1002')).toHaveFocus();
  });

  it("by the browser's Back button: the same, with no new search", async () => {
    const api = installApi();
    const user = await searchWithContext();
    const before = api.searches.length;

    await user.click(card('1003'));
    await within(panel()).findByText('RELATOR 1003');

    fireEvent.click(screen.getByTestId('browser-back'));

    await waitFor(() => expect(currentAddress()).toBe('/'));
    expectContextKept();
    expect(api.searches).toHaveLength(before);
  });

  it('lands on the list, not on the decision read before, after reading several', async () => {
    const api = installApi();
    const user = await searchWithContext();
    const before = api.searches.length;

    await user.click(card('1002'));
    await user.click(card('1003'));
    await within(panel()).findByText('RELATOR 1003');

    fireEvent.click(screen.getByTestId('browser-back'));

    await waitFor(() => expect(currentAddress()).toBe('/'));
    expect(api.searches).toHaveLength(before);
  });

  it('never applies what is still being edited', async () => {
    const api = installApi();
    const user = await searchWithContext();
    const before = api.searches.length;
    await user.click(card('1002'));

    const box = screen.getByLabelText('Pesquisar decisões');
    await user.clear(box);
    await user.type(box, 'outra coisa');
    const judged = screen.getByRole('group', { name: 'Data de julgamento' });
    fireEvent.change(within(judged).getByLabelText('Até'), { target: { value: '2026-03-31' } });

    await user.click(within(panel()).getByRole('button', { name: 'Voltar aos resultados' }));

    expect(api.searches).toHaveLength(before);
    expect(screen.getByText('57')).toBeInTheDocument();
    expect(box).toHaveValue('outra coisa');
  });

  it('leaves a new search, and a new order, working as before', async () => {
    const api = installApi();
    const user = await searchWithContext();
    await user.click(card('1002'));
    await user.click(within(panel()).getByRole('button', { name: 'Voltar aos resultados' }));
    const before = api.searches.length;

    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'relevance');
    await screen.findAllByRole('article');
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');

    expect(api.searches).toHaveLength(before + 2);
  });

  it('from a decision chosen after a new search, lands on the new list only', async () => {
    let calls = 0;
    const api = installApi(() => (++calls <= 2 ? json(page(57)) : json(page(9, ['1003']))));
    const user = await searchWithContext();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    expect(await screen.findByText('9')).toBeInTheDocument();

    await user.click(card('1003'));
    await user.click(within(panel()).getByRole('button', { name: 'Voltar aos resultados' }));

    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.queryByText('57')).toBeNull();
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(api.searches).toHaveLength(3);
  });
});

describe('a decision opened from a link, with no search behind it', () => {
  it('offers the way to the search, with no invented results and no request', async () => {
    const api = installApi();
    const user = userEvent.setup();
    renderApp('/decisoes/tjdft-jurisdf/1002');
    await within(panel()).findByText('RELATOR 1002');

    expect(within(panel()).queryByRole('button', { name: 'Voltar aos resultados' })).toBeNull();
    await user.click(within(panel()).getByRole('button', { name: 'Ir para a busca' }));

    expect(currentAddress()).toBe('/');
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(api.searches).toHaveLength(0);
  });
});

describe('the search session', () => {
  function Screen({ shown }: { shown: boolean }) {
    return (
      <MemoryRouter>
        <SearchSessionProvider>{shown && <HomePage />}</SearchSessionProvider>
      </MemoryRouter>
    );
  }

  it('survives the list being unmounted, with no new search when it comes back', async () => {
    const api = installApi();
    const user = userEvent.setup();
    const { rerender } = render(<Screen shown />);
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');

    rerender(<Screen shown={false} />);
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    rerender(<Screen shown />);

    expect(screen.getAllByRole('article')).toHaveLength(3);
    expect(screen.getByText('57')).toBeInTheDocument();
    expect(api.searches).toHaveLength(1);
  });

  it('never lets an answer from before the unmount overwrite a search made after it', async () => {
    const late = deferred<Response>();
    let calls = 0;
    installApi(() => (++calls === 1 ? late.promise : json(page(222, ['1002']))));
    const user = userEvent.setup();
    const { rerender } = render(<Screen shown />);
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    rerender(<Screen shown={false} />);
    rerender(<Screen shown />);
    // Still loading from before: search again once the button is back.
    await act(async () => {
      fireEvent.submit(screen.getByRole('button', { name: /Pesquis/ }).closest('form')!);
    });
    expect(await screen.findByText('222')).toBeInTheDocument();

    await act(async () => late.resolve(json(page(111))));

    expect(screen.getByText('222')).toBeInTheDocument();
    expect(screen.queryByText('111')).toBeNull();
  });
});
