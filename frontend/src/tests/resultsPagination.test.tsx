import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The application's page size, not one chosen for the test.
import { PAGE_SIZE } from '../search/filters';
import { BLOCK_SIZE, PAGES_PER_BLOCK } from '../search/resultsBuffer';
import { currentAddress, renderApp } from './renderApp';

// Only the address is replaced: the request code under test is the real one.
// The answers are controlled, and they page as the API does — offset
// (page - 1) * page_size, range counted from 1 and null on an empty page — so
// what is checked is what the screen asks for and shows, not the API itself.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

const APPLIED = 'prescrição intercorrente em execução fiscal';

const COURTS = [
  { abbreviation: 'STJ', name: 'Superior Tribunal de Justiça' },
  { abbreviation: 'TJDFT', name: 'Tribunal de Justiça do Distrito Federal e dos Territórios' },
];

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
  };
}

function detail(identifier: string) {
  return {
    ...decision(identifier),
    class_code: 198,
    judged_on: '2026-03-10',
    published_on: '2026-03-15',
    summary: `Ementa da decisão ${identifier}.`,
    outcome: null,
    full_text_available: true,
    sections: null,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// One page of `total` matches, sliced the way the API slices it. The position
// in the whole is in the identifier, so a card says which slice it came from.
function pageOf(url: URL, total: number) {
  const page = Number(url.searchParams.get('page') ?? '1');
  const pageSize = Number(url.searchParams.get('page_size') ?? String(PAGE_SIZE));
  const offset = (page - 1) * pageSize;
  const count = Math.max(0, Math.min(pageSize, total - offset));
  const results = Array.from({ length: count }, (_, i) => ({
    ...decision(String(offset + i + 1)),
    snippet: `Trecho ${offset + i + 1}.`,
  }));
  return {
    total,
    page,
    page_size: pageSize,
    range_from: count ? offset + 1 : null,
    range_to: count ? offset + count : null,
    results,
  };
}

type Answer = (url: URL) => Response | Promise<Response>;

// Searches are kept apart from detail and court reads: only a search is a page.
function installApi(total: number, answer?: Answer) {
  const searches: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/filters') {
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      }
      if (url.pathname === '/courts') {
        return json({ courts: COURTS });
      }
      const found = url.pathname.match(/^\/decisions\/[^/]+\/([^/]+)$/);
      if (found) {
        return json(detail(found[1]));
      }
      searches.push(url);
      return answer ? answer(url) : json(pageOf(url, total));
    }),
  );
  return {
    searches,
    last: () => searches[searches.length - 1],
    // The blocks asked for, in order, as the API was asked for them.
    blocks: () => searches.map((url) => url.searchParams.get('page')),
  };
}

// The screen's pages come in blocks: page N is served from block
// ceil(N / PAGES_PER_BLOCK), and that is the number the API is asked for. A
// block is asked for once, so the other pages it holds ask for nothing.
const block = (page: number) => String(Math.ceil(page / PAGES_PER_BLOCK));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const pagination = () => screen.getByRole('navigation', { name: 'Páginas dos resultados' });
const range = () => within(pagination()).getByText(/Exibindo|Nenhum|Carregando|Esta página/);
const button = (name: 'Primeira página' | 'Anterior' | 'Próxima' | 'Última página') =>
  within(pagination()).getByRole('button', { name });
// The numbered pages, as the row shows them, the gaps included: those are
// hidden from screen readers, so read from the markup, not by role.
const numbers = () =>
  Array.from(pagination().querySelectorAll('li'))
    .map((item) => item.textContent)
    .filter((text) => text !== '');
const shown = () => screen.getAllByRole('article').map((card) => within(card).getByText(/^Trecho/));

const waitForRange = (text: string) =>
  waitFor(() => expect(range()).toHaveTextContent(new RegExp(`^${text}$`)));

async function searchFirst() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article');
  return user;
}

async function next(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.click(button('Próxima'));
  await waitForRange(text);
}

// Every parameter but the page, as a comparable text.
const cut = (url: URL) => {
  const rest = new URLSearchParams(url.searchParams);
  rest.delete('page');
  rest.sort();
  return rest.toString();
};

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the range of results', () => {
  it('on the first page of 45, shows 1–6 of 45, from the first page asked for', async () => {
    const api = installApi(45);
    await searchFirst();

    await waitForRange('Exibindo 1–6 de 45 resultados');
    expect(api.blocks()).toEqual([block(1)]);
    expect(api.last().searchParams.get('page_size')).toBe(String(BLOCK_SIZE));
    expect(shown()).toHaveLength(PAGE_SIZE);
  });

  it('goes 1–6, 7–12, 13–15: the last page ends at the total, not a full page past it', async () => {
    const api = installApi(15);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 15 resultados');

    // The second page is already in the first block: it shows without asking.
    await next(user, 'Exibindo 7–12 de 15 resultados');
    expect(api.blocks()).toEqual([block(1), block(3)]);
    expect(shown()[0]).toHaveTextContent('Trecho 7.');

    await next(user, 'Exibindo 13–15 de 15 resultados');
    expect(api.blocks()).toEqual([block(1), block(3)]);
    expect(shown()).toHaveLength(3);
    expect(button('Próxima')).toBeDisabled();
  });

  it('with a total that fills its last page exactly, offers no page after it', async () => {
    const api = installApi(12);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 12 resultados');

    await next(user, 'Exibindo 7–12 de 12 resultados');

    // Nothing is fetched ahead past the end of the list.
    expect(api.blocks()).toEqual([block(1)]);
    expect(button('Próxima')).toBeDisabled();
    await user.click(button('Próxima'));
    expect(api.searches).toHaveLength(1);
  });

  it('with a single page, has every way out of it disabled', async () => {
    installApi(5);
    await searchFirst();

    await waitForRange('Exibindo 1–5 de 5 resultados');
    expect(button('Primeira página')).toBeDisabled();
    expect(button('Anterior')).toBeDisabled();
    expect(button('Próxima')).toBeDisabled();
  });

  it('with nothing found, says so and shows no range such as 1–0', async () => {
    installApi(0);
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    await waitForRange('Nenhum resultado encontrado');
    expect(pagination()).not.toHaveTextContent(/\d–\d/);
    expect(button('Primeira página')).toBeDisabled();
    expect(button('Anterior')).toBeDisabled();
    expect(button('Próxima')).toBeDisabled();
    expect(button('Última página')).toBeDisabled();
  });

  it('shows no range at all before the first page has answered', async () => {
    const pending = deferred<Response>();
    installApi(45, () => pending.promise);
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    expect(screen.queryByRole('navigation', { name: 'Páginas dos resultados' })).toBeNull();
    expect(screen.queryByText(/Exibindo/)).toBeNull();

    await act(async () => pending.resolve(json(pageOf(new URL('http://api.test'), 45))));
    await waitForRange('Exibindo 1–6 de 45 resultados');
  });
});

describe('moving between pages', () => {
  it('shows the first pages, a gap and the last one, and goes to a page by its number', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');

    // 137 matches at 6 a page are 23 pages.
    expect(numbers()).toEqual(['1', '2', '3', '4', '5', '…', '23']);
    expect(within(pagination()).getByRole('button', { name: 'Página 1' })).toHaveAttribute(
      'aria-current',
      'page',
    );

    await user.click(within(pagination()).getByRole('button', { name: 'Página 4' }));
    await waitForRange('Exibindo 19–24 de 137 resultados');
    expect(api.blocks()).toEqual([block(1), block(4), block(5)]);
    expect(within(pagination()).getByRole('button', { name: 'Página 4' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('goes straight to the last page, and from there offers no page after it', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');

    await user.click(button('Última página'));

    await waitForRange('Exibindo 133–137 de 137 resultados');
    expect(api.last().searchParams.get('page')).toBe(block(23));
    expect(numbers()).toEqual(['1', '…', '19', '20', '21', '22', '23']);
    expect(button('Próxima')).toBeDisabled();
    expect(button('Última página')).toBeDisabled();
  });

  it('from a middle page, goes forward and back, asking only for what it does not hold', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await next(user, 'Exibindo 7–12 de 137 resultados');
    await next(user, 'Exibindo 13–18 de 137 resultados');

    expect(button('Anterior')).toBeEnabled();
    expect(button('Próxima')).toBeEnabled();

    await next(user, 'Exibindo 19–24 de 137 resultados');
    await user.click(button('Anterior'));
    await waitForRange('Exibindo 13–18 de 137 resultados');

    // Pages 2 and 3 came from blocks already held, and coming back to 3 asked
    // for nothing: only the block behind a page never reached is fetched.
    expect(api.blocks()).toEqual([block(1), block(3), block(5)]);
  });

  it('back to the first page from a later one, with its first and previous disabled', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await next(user, 'Exibindo 7–12 de 137 resultados');
    await next(user, 'Exibindo 13–18 de 137 resultados');

    await user.click(button('Primeira página'));

    await waitForRange('Exibindo 1–6 de 137 resultados');
    // Coming back asks for nothing: the first block is still held.
    expect(api.blocks()).toEqual([block(1), block(3)]);
    expect(shown()[0]).toHaveTextContent('Trecho 1.');
    expect(button('Primeira página')).toBeDisabled();
    expect(button('Anterior')).toBeDisabled();
  });

  it('keeps the expression, filters, order and page size, changing only the page', async () => {
    const api = installApi(137);
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    await user.click(await screen.findByRole('checkbox', { name: /^TJDFT\b/ }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');
    await waitForRange('Exibindo 1–6 de 137 resultados');
    const first = api.last();

    await next(user, 'Exibindo 7–12 de 137 resultados');

    const second = api.last();
    expect(second.searchParams.get('page')).toBe(block(3));
    expect(cut(second)).toBe(cut(first));
    expect(second.searchParams.get('q')).toBe(APPLIED);
    expect(second.searchParams.getAll('tribunal')).toEqual(['TJDFT']);
    expect(second.searchParams.get('order')).toBe('date');
    expect(second.searchParams.get('page_size')).toBe(String(BLOCK_SIZE));
  });

  it('never applies an expression or a filter still being edited', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');
    const applied = cut(api.last());

    const box = screen.getByRole('searchbox');
    await user.clear(box);
    await user.type(box, 'outra expressão');
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    await user.click(await screen.findByRole('checkbox', { name: /^STJ\b/ }));

    await next(user, 'Exibindo 7–12 de 137 resultados');

    expect(cut(api.last())).toBe(applied);
    expect(api.last().searchParams.get('q')).toBe(APPLIED);
    expect(api.last().searchParams.has('tribunal')).toBe(false);
    // What is being edited stays in the box, still to be applied.
    expect(box).toHaveValue('outra expressão');
  });
});

describe('starting over on the first page', () => {
  it('after a new search', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await next(user, 'Exibindo 7–12 de 137 resultados');

    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    await waitForRange('Exibindo 1–6 de 137 resultados');
    expect(api.last().searchParams.get('page')).toBe('1');
  });

  it('after new filters are applied', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await next(user, 'Exibindo 7–12 de 137 resultados');

    await user.click(screen.getByRole('button', { name: /filtros/i }));
    await user.click(await screen.findByRole('checkbox', { name: /^TJDFT\b/ }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    await waitForRange('Exibindo 1–6 de 137 resultados');
    expect(api.last().searchParams.get('page')).toBe('1');
    expect(api.last().searchParams.getAll('tribunal')).toEqual(['TJDFT']);
  });

  it('after another order is chosen', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await next(user, 'Exibindo 7–12 de 137 resultados');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');

    await waitForRange('Exibindo 1–6 de 137 resultados');
    expect(api.last().searchParams.get('page')).toBe('1');
    expect(api.last().searchParams.get('order')).toBe('date');
  });
});

describe('a page that fails', () => {
  it('shows neither the range nor the results of the page before, and retries the same page', async () => {
    let failing = true;
    const api = installApi(137, (url) =>
      url.searchParams.get('page') === '2' && failing
        ? json({ detail: 'boom' }, 500)
        : json(pageOf(url, 137)),
    );
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');

    // The third page is the first one the held block does not answer.
    await user.click(within(pagination()).getByRole('button', { name: 'Página 3' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível carregar a página 3. Tente novamente.',
    );
    // Page 1 is gone, and nothing claims page 2 was loaded.
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(screen.queryByRole('navigation', { name: 'Páginas dos resultados' })).toBeNull();
    expect(screen.queryByText(/Exibindo/)).toBeNull();

    failing = false;
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));

    await waitForRange('Exibindo 13–18 de 137 resultados');
    expect(api.blocks()).toEqual([block(1), block(3), block(3)]);
    expect(cut(api.searches[2])).toBe(cut(api.searches[0]));
  });

  it('on a page past the end, as the API answers it, says so and offers the way back', async () => {
    // The data shrank between pages: the API answers page 2 empty, total kept.
    installApi(137, (url) =>
      url.searchParams.get('page') === '2'
        ? json({ ...pageOf(url, 137), results: [], range_from: null, range_to: null })
        : json(pageOf(url, 137)),
    );
    const user = await searchFirst();

    await user.click(within(pagination()).getByRole('button', { name: 'Página 3' }));
    await waitForRange('Esta página não tem mais resultados de 137');

    expect(pagination()).not.toHaveTextContent(/\d–\d/);
    expect(button('Próxima')).toBeDisabled();
    expect(button('Primeira página')).toBeEnabled();
    expect(button('Anterior')).toBeEnabled();
  });
});

describe('disabled controls', () => {
  it('on the first page, ask the API for nothing', async () => {
    const api = installApi(137);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');

    await user.click(button('Primeira página'));
    await user.click(button('Anterior'));

    expect(api.searches).toHaveLength(1);
  });

  it('while a page loads, are all disabled, and a second click asks for nothing more', async () => {
    const pending = deferred<Response>();
    const api = installApi(137, (url) =>
      url.searchParams.get('page') === '2' ? pending.promise : json(pageOf(url, 137)),
    );
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');

    // Only a page whose block is not held loads; the second page is in hand.
    await user.click(within(pagination()).getByRole('button', { name: 'Página 3' }));

    await waitForRange('Carregando a página 3...');
    expect(button('Primeira página')).toBeDisabled();
    expect(button('Anterior')).toBeDisabled();
    expect(button('Próxima')).toBeDisabled();
    await user.click(button('Próxima'));
    expect(api.searches).toHaveLength(2);

    const second = new URL(`http://api.test/decisions?page=2&page_size=${BLOCK_SIZE}`);
    await act(async () => pending.resolve(json(pageOf(second, 137))));
    await waitForRange('Exibindo 13–18 de 137 resultados');
    expect(api.searches).toHaveLength(2);
  });
});

describe('by keyboard', () => {
  it('goes to the next page with Enter and lands on its first result', async () => {
    installApi(137);
    const user = await searchFirst();
    await waitForRange('Exibindo 1–6 de 137 resultados');

    button('Próxima').focus();
    await user.keyboard('{Enter}');

    await waitForRange('Exibindo 7–12 de 137 resultados');
    const [firstCard] = screen.getAllByRole('article');
    await waitFor(() =>
      expect(within(firstCard).getByRole('link', { name: /Ler a decisão/ })).toHaveFocus(),
    );
  });
});

describe('back from a decision to a later page', () => {
  const THIRD = 'Exibindo 13–18 de 137 resultados';
  // Another expression, with another total, so two searches cannot be mistaken
  // for one another.
  const OTHER = 'outra expressão';
  const byExpression: Answer = (url) =>
    json(pageOf(url, url.searchParams.get('q') === OTHER ? 45 : 137));

  const card = (identifier: number) =>
    screen.getByRole('link', { name: new RegExp(`Ler a decisão do processo 0700${identifier}-`) });
  const panel = () => screen.getByRole('complementary');
  const browserBack = () => act(() => screen.getByTestId('browser-back').click());

  // An expression, filters and an order applied, then two pages on:
  // the third page, where a reset to the first would show.
  async function onTheThirdPage(before: string[] = []) {
    const user = userEvent.setup();
    renderApp('/', before);
    const box = screen.getByLabelText('Pesquisar decisões');
    await user.clear(box);
    await user.type(box, 'dano moral');
    await user.click(screen.getByRole('button', { name: /filtros/i }));
    await user.click(await screen.findByRole('checkbox', { name: /^TJDFT\b/ }));
    const judged = screen.getByRole('group', { name: 'Data de julgamento' });
    await user.type(within(judged).getByLabelText('De'), '2026-01-01');
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await waitForRange('Exibindo 1–6 de 137 resultados');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');
    await waitForRange('Exibindo 1–6 de 137 resultados');
    await next(user, 'Exibindo 7–12 de 137 resultados');
    await next(user, THIRD);
    return user;
  }

  async function open(user: ReturnType<typeof userEvent.setup>, identifier: number) {
    await user.click(card(identifier));
    await waitFor(() => expect(currentAddress()).toBe(`/decisoes/tjdft-jurisdf/${identifier}`));
    await within(panel()).findByText(`RELATOR ${identifier}`);
  }

  // The third page as it was left: its range and total, its own page of
  // results, and the expression, filters and order it was searched with.
  async function expectThirdPage() {
    await waitFor(() => expect(currentAddress()).toBe('/'));
    await waitForRange(THIRD);
    expect(shown()).toHaveLength(PAGE_SIZE);
    expect(shown()[0]).toHaveTextContent('Trecho 13.');
    expect(shown()[PAGE_SIZE - 1]).toHaveTextContent('Trecho 18.');
    expect(screen.getByLabelText('Pesquisar decisões')).toHaveValue('dano moral');
    expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toHaveValue('date');
    expect(screen.getByRole('checkbox', { name: /^TJDFT\b/ })).toBeChecked();
    const judged = screen.getByRole('group', { name: 'Data de julgamento' });
    expect(within(judged).getByLabelText('De')).toHaveValue('2026-01-01');
    expect(screen.getByRole('button', { name: /Filtros/ })).toHaveTextContent('2');
  }

  // Paging on from the restored page asks for the next one of the same cut:
  // the page was restored, not only drawn.
  async function expectPagingOnFromThird(
    user: ReturnType<typeof userEvent.setup>,
    api: ReturnType<typeof installApi>,
  ) {
    const third = api.last();
    await next(user, 'Exibindo 19–24 de 137 resultados');
    // The fourth page came from the block already held; what was asked for is
    // the block behind the fifth, fetched ahead from the last page of a block.
    expect(api.last().searchParams.get('page')).toBe(block(5));
    expect(cut(api.last())).toBe(cut(third));
  }

  it("through the browser's Back, walking the history, is the same", async () => {
    const api = installApi(137, byExpression);
    const user = await onTheThirdPage();
    const asked = api.searches.length;

    await open(user, 15);
    await browserBack();

    await expectThirdPage();
    expect(api.searches).toHaveLength(asked);
    await expectPagingOnFromThird(user, api);
  });

  it('keeps the third page over one decision after another', async () => {
    const api = installApi(137, byExpression);
    const user = await onTheThirdPage();
    const asked = api.searches.length;

    await open(user, 15);
    await browserBack();
    await expectThirdPage();

    await open(user, 17);
    await browserBack();
    await expectThirdPage();

    // From one decision straight to another, then a single Back.
    await open(user, 16);
    await open(user, 18);
    await browserBack();
    await expectThirdPage();

    expect(api.searches).toHaveLength(asked);
  });

  it('starts on the first page again when, back on the list, a new search or filters are applied', async () => {
    const api = installApi(137, byExpression);
    const user = await onTheThirdPage();
    await open(user, 15);
    await browserBack();
    await expectThirdPage();

    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await waitForRange('Exibindo 1–6 de 137 resultados');
    expect(api.last().searchParams.get('page')).toBe('1');

    await next(user, 'Exibindo 7–12 de 137 resultados');
    await user.click(screen.getByRole('checkbox', { name: /^STJ\b/ }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await waitForRange('Exibindo 1–6 de 137 resultados');
    expect(api.last().searchParams.get('page')).toBe('1');
    expect(api.last().searchParams.getAll('tribunal').sort()).toEqual(['STJ', 'TJDFT']);
  });

  it('never brings back the page of another search, one started from a decision', async () => {
    const api = installApi(137, byExpression);
    const user = await onTheThirdPage();
    await open(user, 15);

    const box = screen.getByLabelText('Pesquisar decisões');
    await user.clear(box);
    await user.type(box, OTHER);
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    await waitFor(() => expect(currentAddress()).toBe('/'));
    await waitForRange('Exibindo 1–6 de 45 resultados');
    expect(api.last().searchParams.get('q')).toBe(OTHER);
    expect(api.last().searchParams.get('page')).toBe('1');
    expect(screen.queryByText(/de 137 resultados/)).toBeNull();
    expect(screen.queryByText(THIRD)).toBeNull();
  });

  it('leaves no second list entry behind when a page is changed from a decision', async () => {
    const api = installApi(137, byExpression);
    // An entry before the list, so the test can tell where Back leads.
    const user = await onTheThirdPage(['/antes']);
    await open(user, 15);

    await next(user, 'Exibindo 19–24 de 137 resultados');
    expect(currentAddress()).toBe('/');
    // The fourth page came from the block already held; what was asked for is
    // the block behind the fifth, fetched ahead from the last page of a block.
    expect(api.last().searchParams.get('page')).toBe(block(5));

    // One Back leaves the list: it does not land on a copy of it.
    await browserBack();
    expect(currentAddress()).toBe('/antes');
  });
});
