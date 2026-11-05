import { act, fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { currentAddress, renderApp, SIGNED_IN } from './renderApp';
import { TEAM_PATH } from '../pages/TeamPage';

// Only the address of the API is replaced: the request code under test is the
// real one, so what is asked of the coverage endpoint is what the app sends.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// Courts no code knows by name: the rows have to come from the answer.
const COVERAGE = {
  documents: 1234567,
  first: '1998-04-02',
  last: '2026-09-17',
  courts: [
    {
      abbreviation: 'TRF1',
      name: 'Tribunal Regional Federal da 1ª Região',
      documents: 1234000,
      first: '1998-04-02',
      last: '2026-09-01',
    },
    {
      abbreviation: 'TJSP',
      name: 'Tribunal de Justiça de São Paulo',
      documents: 567,
      first: '2026-01-01',
      last: '2026-09-17',
    },
  ],
  state: 'loaded',
  // 02:30 in UTC is still the evening before in Brasília.
  updated_at: '2026-09-18T02:30:00Z',
};

const EMPTY = {
  documents: 0,
  first: null,
  last: null,
  courts: [],
  state: 'never_loaded',
  updated_at: null,
};

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

const page = (identifiers: string[]) => ({
  total: identifiers.length,
  page: 1,
  page_size: 20,
  results: identifiers.map((id) => ({ ...decision(id), snippet: `Trecho ${id}.` })),
});

type Answer = () => Response | Promise<Response>;

// Coverage and searches are counted apart, so "the coverage was asked with
// nothing" and "no new search" are both things a test can read.
function installApi({
  coverage = () => json(COVERAGE),
  search = () => json(page(['1001', '1002', '1003'])),
}: { coverage?: Answer; search?: Answer } = {}) {
  const coverageRequests: URL[] = [];
  const searches: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/indicators/coverage') {
        coverageRequests.push(url);
        return coverage();
      }
      if (url.pathname === '/decisions') {
        searches.push(url);
        return search();
      }
      const detail = url.pathname.match(/^\/decisions\/[^/]+\/([^/]+)$/);
      if (detail) {
        return json(decision(detail[1]));
      }
      return json({ courts: [{ abbreviation: 'TJDFT', name: 'TJDFT' }] });
    }),
  );
  return { coverageRequests, searches };
}

// Found by its navigation: jsdom calls every <header> a banner, the cards'
// included, where a browser keeps that role for the page's own bar.
const topBar = () =>
  screen.getByRole('navigation', { name: 'Informações do sistema' }).closest('header')!;

const coverageLink = () => within(topBar()).getByRole('link', { name: /Cobertura da base/ });

const summary = () => within(screen.getByRole('region', { name: 'Resumo da base' }));

const field = (label: string) => summary().getByText(label).nextElementSibling as HTMLElement;

// Nothing on the page may read like a value the code failed to format.
const expectNoRawValues = () =>
  expect(screen.getByRole('main')).not.toHaveTextContent(/null|undefined|NaN|Invalid Date/);

async function openCoverage() {
  const user = userEvent.setup();
  renderApp('/cobertura');
  return user;
}

// An expression and a court and period filter, applied: the cut the
// coverage must never inherit.
async function searchFiltered(expression: string) {
  const user = userEvent.setup();
  renderApp();
  const box = screen.getByLabelText('Pesquisar decisões');
  await user.clear(box);
  await user.type(box, expression);
  await user.click(screen.getByRole('button', { name: /filtros/i }));
  await user.click(await screen.findByRole('checkbox', { name: /TJDFT/ }));
  const judged = screen.getByRole('group', { name: 'Data de julgamento' });
  fireEvent.change(within(judged).getByLabelText('De'), { target: { value: '2026-01-01' } });
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  return user;
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the top bar', () => {
  it('holds the brand, the search, the two ways out and the account', () => {
    // Lista fechada de propósito: o que entra na barra entra por decisão, e
    // este teste é onde alguém percebe que acrescentou algo sem querer.

    installApi();
    renderApp();

    const bar = within(topBar());
    // A marca é a volta para a pesquisa, e é por isso que não há um segundo
    // link dizendo "Pesquisa" ao lado dela.
    expect(bar.getByRole('link', { name: 'Jusmap — início' })).toHaveAttribute('href', '/');
    expect(bar.getByRole('img', { name: 'Jusmap' })).toHaveAttribute('src', '/jusmap-logo.png');
    expect(bar.getAllByRole('link').map((link) => link.textContent)).toEqual([
      '',
      'Cobertura da baseInformações do sistema',
      'UsuáriosQuem tem acesso',
    ]);
    expect(bar.getByRole('searchbox', { name: 'Pesquisar decisões' })).toBeInTheDocument();
    // "Sair" vem primeiro porque a conta fica na linha da marca, acima da
    // linha da busca.
    expect(bar.getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Sair',
      'Filtros',
      'Pesquisar',
    ]);
    expect(bar.getByText('Ana Almeida Costa')).toBeInTheDocument();
  });

  it('não oferece a equipe a quem não é gerente', () => {
    installApi();
    renderApp('/', [], true, { ...SIGNED_IN, role: 'usuario' });

    const bar = within(topBar());

    expect(bar.queryByText('Usuários')).toBeNull();
    expect(bar.getByText('Ana Almeida Costa')).toBeInTheDocument();
  });

  it('on the coverage, keeps the brand and coverage link without a search', () => {
    installApi();
    renderApp('/cobertura');

    const bar = within(topBar());

    expect(bar.queryByRole('searchbox')).toBeNull();
    // Só o botão de sair: nada da busca sobra numa tela que não é dela.
    expect(bar.getAllByRole('button').map((button) => button.textContent)).toEqual(['Sair']);
  });

  it('reaches the coverage from the search screen', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();

    await user.click(coverageLink());

    expect(currentAddress()).toBe('/cobertura');
    expect(screen.getByRole('heading', { level: 1, name: 'Cobertura da base' })).toBeVisible();
    expect(coverageLink()).toHaveAttribute('aria-current', 'page');
  });
});

describe('the coverage as the base answers it', () => {
  it('shows the four values, formatted in Brazilian Portuguese', async () => {
    installApi();
    await openCoverage();

    expect(await summary().findByText('1.234.567')).toBeVisible();
    expect(summary().getByText('em 2 tribunais integrados')).toBeVisible();
    // Days alone keep their day, whatever the zone.
    expect(field('Primeiro registro')).toHaveTextContent('02/04/1998');
    expect(field('Registro mais recente')).toHaveTextContent('17/09/2026');
    // An instant is shown on Brasília's clock.
    expect(field('Última atualização')).toHaveTextContent('17/09/2026, 23:30');
    expect(field('Situação da base')).toHaveTextContent('Disponível');
    expectNoRawValues();
  });

  it('draws one row per court the answer carries, largest first', async () => {
    installApi();
    await openCoverage();

    const table = await screen.findByRole('table', { name: 'Cobertura por tribunal' });
    const [, ...rows] = within(table).getAllByRole('row');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('TRF1');
    expect(rows[0]).toHaveTextContent('Tribunal Regional Federal da 1ª Região');
    expect(rows[0]).toHaveTextContent('1.234.000');
    expect(rows[0]).toHaveTextContent('02/04/1998');
    expect(rows[0]).toHaveTextContent('Pesquisável');
    expect(rows[1]).toHaveTextContent('TJSP');
    expect(rows[1]).toHaveTextContent('567');
    expect(within(table).queryByText('STJ')).toBeNull();
    expect(screen.getByText('1.234.567 documentos no total')).toBeVisible();
  });

  it('says the numbers are the whole base, not the search', async () => {
    installApi();
    await openCoverage();

    expect(
      screen.getByText(/Consulte o alcance de toda a base disponível na plataforma/),
    ).toHaveTextContent('Estes dados não mudam com os termos ou filtros de uma pesquisa.');
    expect(
      screen.getByRole('complementary', { name: 'Como interpretar esta página' }),
    ).toHaveTextContent(/base inteira, não o resultado de uma pesquisa/);
  });

  it('shows no number while the answer is on its way', async () => {
    let answer!: (response: Response) => void;
    installApi({ coverage: () => new Promise<Response>((done) => (answer = done)) });
    await openCoverage();

    expect(screen.getByRole('region', { name: 'Resumo da base' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(screen.getByText('Carregando a cobertura por tribunal...')).toBeVisible();
    expect(screen.queryByText('0')).toBeNull();
    expect(screen.queryByText('Disponível')).toBeNull();

    await act(async () => answer(json(COVERAGE)));

    expect(await summary().findByText('1.234.567')).toBeVisible();
  });
});

describe('an empty base', () => {
  it('says there is nothing yet, with no dates and no rows', async () => {
    installApi({ coverage: () => json(EMPTY) });
    await openCoverage();

    const table = await screen.findByRole('table', { name: 'Cobertura por tribunal' });
    expect(
      await within(table).findByText('Ainda não há documentos disponíveis na base.'),
    ).toBeVisible();
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    // Zero is the answer, said as a number, not as something missing.
    expect(summary().getByText('0')).toBeVisible();
    expect(summary().getByText('nenhum tribunal integrado')).toBeVisible();
    expect(field('Primeiro registro')).toHaveTextContent('Sem registros');
    expect(field('Registro mais recente')).toHaveTextContent('Sem registros');
    expect(field('Situação da base')).toHaveTextContent('Ainda não coletada');
    expect(screen.queryByText('Disponível')).toBeNull();
    expectNoRawValues();
  });

  it('is not called available because the load finished', async () => {
    installApi({
      coverage: () => json({ ...EMPTY, state: 'loaded', updated_at: '2026-09-18T02:30:00Z' }),
    });
    await openCoverage();

    expect(await screen.findByText('Sem documentos')).toBeVisible();
    expect(screen.queryByText('Disponível')).toBeNull();
  });
});

describe('a coverage that could not be read', () => {
  it('says so, never as an empty base, and reads again on Tentar novamente', async () => {
    let failing = true;
    const { coverageRequests } = installApi({
      coverage: () => (failing ? json({ detail: 'down' }, 503) : json(COVERAGE)),
    });
    const user = await openCoverage();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível carregar a cobertura da base.',
    );
    expect(screen.queryByText('Ainda não há documentos disponíveis na base.')).toBeNull();
    expect(screen.queryByText('0')).toBeNull();
    expect(field('Situação da base')).toHaveTextContent('Indisponível');
    expectNoRawValues();

    failing = false;
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }));

    expect(await summary().findByText('1.234.567')).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(coverageRequests).toHaveLength(2);
  });

  it('treats a network failure the same way', async () => {
    installApi({ coverage: () => Promise.reject(new TypeError('Failed to fetch')) });
    await openCoverage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Tentar novamente');
    expect(screen.queryByText('Ainda não há documentos disponíveis na base.')).toBeNull();
  });
});

describe('an answer missing some fields', () => {
  it('keeps what came and says what did not, without calling the base empty', async () => {
    installApi({
      coverage: () =>
        json({
          documents: 10,
          first: null,
          last: 'not a date',
          courts: [
            { abbreviation: 'TRF1', name: null, documents: 'ten', first: null, last: '2026-02-30' },
          ],
          state: 'loaded',
          updated_at: null,
        }),
    });
    await openCoverage();

    expect(await summary().findByText('10')).toBeVisible();
    expect(field('Primeiro registro')).toHaveTextContent('Não informado');
    expect(field('Registro mais recente')).toHaveTextContent('Não informado');
    expect(field('Última atualização')).toHaveTextContent('Não informado');
    expect(field('Situação da base')).toHaveTextContent('Disponível');

    const table = screen.getByRole('table', { name: 'Cobertura por tribunal' });
    const [, row] = within(table).getAllByRole('row');
    expect(row).toHaveTextContent('TRF1');
    expect(within(row).getAllByText('Não informado')).toHaveLength(4);
    expect(screen.queryByText('Ainda não há documentos disponíveis na base.')).toBeNull();
    expectNoRawValues();
  });

  it('does not take courts it was not sent for no courts', async () => {
    installApi({ coverage: () => json({ ...COVERAGE, courts: undefined }) });
    await openCoverage();

    expect(await summary().findByText('1.234.567')).toBeVisible();
    expect(summary().getByText('tribunais não informados')).toBeVisible();
    expect(screen.getByText('A cobertura por tribunal não foi informada.')).toBeVisible();
    expect(screen.queryByText('Ainda não há documentos disponíveis na base.')).toBeNull();
  });
});

describe('the coverage beside a search', () => {
  it('is asked with nothing from a filtered search', async () => {
    const { coverageRequests, searches } = installApi();
    const user = await searchFiltered('dano moral');
    await screen.findAllByRole('article');
    // The search itself did carry the cut.
    expect(searches[0].searchParams.get('tribunal')).toBe('TJDFT');

    await user.click(coverageLink());

    expect(await summary().findByText('1.234.567')).toBeVisible();
    expect(coverageRequests).toHaveLength(1);
    expect(coverageRequests[0].search).toBe('');
  });

  it('stays the whole base after a search that found nothing', async () => {
    const { coverageRequests } = installApi({
      search: () => json({ total: 0, page: 1, page_size: 20, results: [] }),
    });
    const user = await searchFiltered('termo inexistente');
    await screen.findAllByText(/Nenhuma decisão foi encontrada/);

    await user.click(coverageLink());

    expect(await summary().findByText('1.234.567')).toBeVisible();
    expect(field('Situação da base')).toHaveTextContent('Disponível');
    expect(screen.queryByText('Ainda não há documentos disponíveis na base.')).toBeNull();
    expect(coverageRequests[0].search).toBe('');
  });
});

describe('going to the coverage and back', () => {
  it('finds the search as it was, with no new search', async () => {
    const { searches } = installApi();
    const user = await searchFiltered('dano moral');
    await screen.findAllByRole('article');

    await user.click(coverageLink());
    await summary().findByText('1.234.567');
    await user.click(screen.getByRole('button', { name: 'Voltar à pesquisa' }));

    expect(currentAddress()).toBe('/');
    expect(screen.getByLabelText('Pesquisar decisões')).toHaveValue('dano moral');
    expect(screen.getAllByRole('article')).toHaveLength(3);
    expect(screen.getByRole('button', { name: /Filtros/ })).toHaveTextContent('2');
    expect(searches).toHaveLength(1);
  });

  it('returns to the decision it was opened from', async () => {
    installApi();
    const user = await searchFiltered('dano moral');
    await user.click(
      await screen.findByRole('link', { name: /Ler a decisão do processo 07001002/ }),
    );
    const decisionAddress = currentAddress();

    await user.click(coverageLink());
    // Clicking it again on the page itself leaves no second copy behind.
    await user.click(coverageLink());
    await user.click(screen.getByRole('button', { name: 'Voltar à pesquisa' }));

    expect(currentAddress()).toBe(decisionAddress);
  });

  it('goes to the search when the page was opened from a link', async () => {
    installApi();
    const user = await openCoverage();

    await user.click(screen.getByRole('button', { name: 'Voltar à pesquisa' }));

    expect(currentAddress()).toBe('/');
    expect(screen.getByLabelText('Pesquisar decisões')).toBeVisible();
  });
});

describe('a volta para a pesquisa', () => {
  it('da cobertura aberta pela pesquisa, volta para onde o leitor estava', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();

    await user.click(coverageLink());
    expect(currentAddress()).toBe('/cobertura');

    await user.click(screen.getByRole('button', { name: /Voltar à pesquisa/ }));

    expect(currentAddress()).toBe('/');
  });

  it('da cobertura aberta pela tela de usuários, volta para a pesquisa e não para ela', async () => {
    // O defeito: a volta era um passo no histórico, e quando a tela de
    // usuários passou a existir, "um passo atrás" deixou de ser a pesquisa.
    // O botão dizia "voltar à pesquisa" e levava para os usuários.
    installApi();
    const user = userEvent.setup();
    renderApp(TEAM_PATH);

    await user.click(coverageLink());
    expect(currentAddress()).toBe('/cobertura');

    await user.click(screen.getByRole('button', { name: /Voltar à pesquisa/ }));

    expect(currentAddress()).toBe('/');
  });

  it('a marca leva à pesquisa de qualquer tela', async () => {
    // É por ela que se volta, e é por isso que não existe um segundo link
    // dizendo "Pesquisa" ao lado: dois caminhos para a mesma sala.
    installApi();
    const user = userEvent.setup();

    for (const partida of [TEAM_PATH, '/cobertura']) {
      const { unmount } = renderApp(partida);

      await user.click(within(topBar()).getByRole('link', { name: 'Jusmap — início' }));

      expect(currentAddress()).toBe('/');
      unmount();
    }
  });

  it('a tela de usuários oferece a volta', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp(TEAM_PATH);

    await user.click(screen.getByRole('button', { name: /Voltar à pesquisa/ }));

    expect(currentAddress()).toBe('/');
  });
});
