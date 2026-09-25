import { act, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Decision } from '../api/decisions';
import DecisionDetail from '../components/DecisionDetail';
import { renderApp } from './renderApp';

// Only the address is replaced: the request code under test is the real one.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

const STRUCTURED: Decision = {
  source: 'tjdft-jurisdf',
  identifier: '2119440',
  court: 'TJDFT',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: '3ª TURMA CÍVEL',
  reporting_judge: 'JOÃO EGMONT',
  decided_on: '2026-06-11',
  small_claims: false,
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2119440',
  source_url_reachable: true,
  class_code: 1116,
  judged_on: '2026-06-11',
  published_on: '2026-06-18',
  summary:
    'EXECUÇÃO FISCAL. PRESCRIÇÃO INTERCORRENTE. I. CASO EM EXAME 1. Apelação. II. QUESTÃO EM DISCUSSÃO 2. Termo inicial. III. RAZÕES DE DECIDIR 3. O prazo corre. IV. DISPOSITIVO 4. Desprovida.',
  outcome: 'APELAÇÃO CONHECIDA E DESPROVIDA.',
  full_text_available: true,
  sections: {
    headnote: 'EXECUÇÃO FISCAL. PRESCRIÇÃO INTERCORRENTE.',
    case: '1. Apelação interposta contra sentença que julgou extinta a execução fiscal.',
    question: '2. Definir o termo inicial da suspensão.',
    reasoning: '3. O prazo corre da ciência da primeira diligência infrutífera.',
    ruling: '4. Apelação conhecida e desprovida.\nTese de julgamento: "o prazo corre da ciência".',
  },
};

const PROSE: Decision = {
  ...STRUCTURED,
  identifier: '2150999',
  case_number: '0702646-44.2026.8.07.0006',
  sections: null,
  summary:
    'Ementa. Direito do Consumidor. Recurso inominado.\nI. Caso em exame\n1. Recurso da parte autora.\n2. Fato relevante.',
};

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

type Handler = (url: URL) => Response | Promise<Response>;

// A stand-in for the API: detail by `source/identifier`, search by `q`.
function installApi(detail: Handler, search?: Handler) {
  const requested: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requested.push(url);
      if (/^\/decisions\/[^/]+\/[^/]+$/.test(url.pathname)) return detail(url);
      if (url.pathname === '/decisions' && search) return search(url);
      throw new Error(`unexpected request ${url}`);
    }),
  );
  return {
    details: () => requested.filter((url) => url.pathname.split('/').length === 4),
  };
}

const byIdentifier =
  (decisions: Decision[]): Handler =>
  (url) => {
    const identifier = decodeURIComponent(url.pathname.split('/').pop() ?? '');
    const found = decisions.find((decision) => decision.identifier === identifier);
    return found ? json(found) : json({ detail: 'Decision not found.' }, 404);
  };

function renderDetail(decision: Decision) {
  installApi(() => json(decision));
  render(<DecisionDetail id="detail" source={decision.source} identifier={decision.identifier} />);
  return screen.findByRole('heading', { level: 2 });
}

const meta = () =>
  Object.fromEntries(
    screen
      .getAllByRole('term')
      .map((term) => [term.textContent, term.nextElementSibling?.textContent]),
  );

// jsdom lays nothing out, so it has no scrollIntoView; browsers do.
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the metadata', () => {
  it('shows the fields of the decision asked for, both dates told apart', async () => {
    await renderDetail(STRUCTURED);

    expect(meta()).toEqual({
      'Número do processo': '0712598-03.2019.8.07.0003',
      Relator: 'JOÃO EGMONT',
      'Órgão julgador': '3ª TURMA CÍVEL',
      'Classe processual (código CNJ)': '1116',
      'Data do julgamento': '11/06/2026',
      'Data da publicação': '18/06/2026',
    });
  });

  it('asks the endpoint by collection and identifier, not by case number', async () => {
    const api = installApi(() => json(STRUCTURED));
    render(<DecisionDetail id="d" source="tjdft-jurisdf" identifier="2119440" />);

    await screen.findByRole('heading', { level: 2 });
    expect(api.details()[0].pathname).toBe('/decisions/tjdft-jurisdf/2119440');
  });

  it('leaves missing fields out, with no empty label and no placeholder text', async () => {
    await renderDetail({
      ...STRUCTURED,
      case_number: null,
      reporting_judge: '   ',
      judging_body: null,
      class_code: null,
      judged_on: null,
      published_on: '2026-13-45',
    });

    expect(Object.keys(meta())).toEqual(['Data da decisão']);
    const panel = screen.getByRole('complementary');
    expect(panel.textContent).not.toMatch(/null|undefined|Invalid Date|NaN|2027/);
  });
});

describe('a structured ementa', () => {
  it('shows the four sections, labelled and in order, with every word', async () => {
    await renderDetail(STRUCTURED);

    const s = STRUCTURED.sections!;
    // Each label with the text under it, in order: a text under the wrong
    // label would read as a different part of the judgement.
    const parts = screen
      .getAllByRole('heading', { level: 4 })
      .map((heading) => [heading.textContent, heading.nextElementSibling?.textContent]);
    expect(parts).toEqual([
      ['I. Caso em exame', s.case],
      ['II. Questão em discussão', s.question],
      ['III. Razões de decidir', s.reasoning],
      ['IV. Dispositivo', s.ruling],
    ]);
    expect(screen.getByText((_, node) => node?.textContent === s.headnote)).toBeInTheDocument();
  });

  it('falls back to the whole text when a section comes back empty', async () => {
    await renderDetail({ ...STRUCTURED, sections: { ...STRUCTURED.sections!, question: ' ' } });

    expect(screen.queryAllByRole('heading', { level: 4 })).toHaveLength(0);
    expect(screen.getByText((_, node) => node?.textContent === STRUCTURED.summary)).toBeTruthy();
  });
});

describe('a free prose ementa', () => {
  it('is shown whole, line breaks included, with no section inferred', async () => {
    await renderDetail(PROSE);

    expect(screen.queryAllByRole('heading', { level: 4 })).toHaveLength(0);
    const text = screen.getByText((_, node) => node?.textContent === PROSE.summary);
    expect(text.tagName).toBe('P');
  });

  it('keeps the last paragraph of a very long text', async () => {
    const paragraphs = Array.from({ length: 300 }, (_, n) => `${n + 1}. Parágrafo de teste.`);
    paragraphs.push('ÚLTIMO PARÁGRAFO: recurso conhecido e desprovido.');
    await renderDetail({ ...PROSE, summary: paragraphs.join('\n') });

    expect(screen.getByText(/ÚLTIMO PARÁGRAFO: recurso conhecido e desprovido\.$/)).toBeTruthy();
  });

  it('says so when there is no ementa at all', async () => {
    await renderDetail({ ...PROSE, summary: '' });

    expect(screen.getByText(/A ementa desta decisão não está disponível/)).toBeInTheDocument();
  });
});

describe('text from the API', () => {
  it('is shown as text, never run as markup', async () => {
    const hostile = '<img src=x onerror="window.__hit=1"><script>window.__hit=2</script>Fim.';
    await renderDetail({ ...PROSE, summary: hostile, reporting_judge: '<b>RELATOR</b>' });

    const panel = screen.getByRole('complementary');
    expect(panel.querySelector('img, script, b')).toBeNull();
    expect(screen.getByText(hostile)).toBeInTheDocument();
    expect(screen.getByText('<b>RELATOR</b>')).toBeInTheDocument();
    expect((window as unknown as { __hit?: number }).__hit).toBeUndefined();
  });
});

describe('the official source', () => {
  it('opens the real address in a new tab, and says so', async () => {
    await renderDetail(STRUCTURED);

    const link = screen.getByRole('link', { name: /Abrir fonte oficial/ });
    expect(link).toHaveAttribute('href', STRUCTURED.source_url);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveTextContent('(abre em nova aba)');
  });

  it.each([
    ['found broken by the load', { source_url_reachable: false }],
    ['not a web address', { source_url: 'javascript:alert(1)' }],
    ['missing', { source_url: '' }],
  ])('is unavailable, not a link to nowhere, when %s', async (_, change) => {
    await renderDetail({ ...STRUCTURED, ...change });

    const action = screen.getByRole('link', { name: /Abrir fonte oficial/ });
    expect(action).not.toHaveAttribute('href');
    expect(action).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByText('Link indisponível no momento.')).toBeInTheDocument();
  });

  it('is offered when nobody has checked the link yet', async () => {
    await renderDetail({ ...STRUCTURED, source_url_reachable: null });

    expect(screen.getByRole('link', { name: /Abrir fonte oficial/ })).toHaveAttribute('href');
  });
});

describe('the panel states', () => {
  it('says it is loading, with nothing from any decision yet', async () => {
    const pending = deferred<Response>();
    installApi(() => pending.promise);
    render(<DecisionDetail id="d" source="s" identifier="1" />);

    expect(screen.getByRole('status')).toHaveTextContent('Carregando decisão');
    expect(screen.queryByRole('term')).toBeNull();

    await act(async () => pending.resolve(json(STRUCTURED)));
    expect(await screen.findByText('JOÃO EGMONT')).toBeInTheDocument();
  });

  it('says a missing decision was not found', async () => {
    installApi(() => json({ detail: 'Decision not found.' }, 404));
    render(<DecisionDetail id="d" source="s" identifier="0" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Decisão não encontrada');
    expect(screen.queryByRole('button', { name: 'Tentar novamente' })).toBeNull();
  });

  it('offers a retry when the server fails, and loads on it', async () => {
    let calls = 0;
    installApi(() => (++calls === 1 ? json({ detail: 'down' }, 503) : json(STRUCTURED)));
    const user = userEvent.setup();
    render(<DecisionDetail id="d" source="s" identifier="1" />);

    await user.click(await screen.findByRole('button', { name: 'Tentar novamente' }));

    expect(await screen.findByText('JOÃO EGMONT')).toBeInTheDocument();
  });
});

describe('choosing decisions from the results', () => {
  const RESULTS = [STRUCTURED, PROSE].map((decision) => ({
    ...decision,
    snippet: `Trecho de ${decision.identifier}.`,
  }));

  const searchAnswer = () => json({ total: 57, page: 1, page_size: 20, results: RESULTS });

  async function searchAndWait() {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findByRole('heading', { level: 2, name: /0712598/ });
    return user;
  }

  it('opens the first result, and another one only swaps the right side', async () => {
    installApi(byIdentifier([STRUCTURED, PROSE]), searchAnswer);
    const user = await searchAndWait();
    const box = screen.getByLabelText('Pesquisar decisões');
    const query = (box as HTMLInputElement).value;

    await user.click(screen.getByRole('link', { name: /Ler a decisão do processo 0702646/ }));

    expect(await screen.findByRole('heading', { level: 2, name: /0702646/ })).toBeInTheDocument();
    expect(screen.getByText('57')).toBeInTheDocument();
    expect(screen.getAllByRole('article')).toHaveLength(2);
    expect(box).toHaveValue(query);
    expect(screen.getByRole('link', { name: /Ler a decisão do processo 0702646/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
  });

  it('is chosen from the keyboard too', async () => {
    installApi(byIdentifier([STRUCTURED, PROSE]), searchAnswer);
    await searchAndWait();

    const second = screen.getByRole('link', { name: /Ler a decisão do processo 0702646/ });
    second.focus();
    const user = userEvent.setup();
    await user.keyboard('{Enter}');

    expect(await screen.findByRole('heading', { level: 2, name: /0702646/ })).toBeInTheDocument();
    expect(second).toHaveFocus();
  });

  it('never lets a late answer replace the decision chosen after it', async () => {
    const late = deferred<Response>();
    installApi((url) => {
      if (url.pathname.endsWith('/2150999')) return late.promise;
      return json(STRUCTURED);
    }, searchAnswer);
    const user = await searchAndWait();

    await user.click(screen.getByRole('link', { name: /Ler a decisão do processo 0702646/ }));
    await user.click(screen.getByRole('link', { name: /Ler a decisão do processo 0712598/ }));
    await act(async () => late.resolve(json(PROSE)));

    expect(await screen.findByRole('heading', { level: 2, name: /0712598/ })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 2, name: /0702646/ })).toBeNull();
  });

  it('goes back to the chosen card with the search as it was', async () => {
    installApi(byIdentifier([STRUCTURED, PROSE]), searchAnswer);
    const user = await searchAndWait();
    await user.click(screen.getByRole('link', { name: /Ler a decisão do processo 0702646/ }));
    await screen.findByRole('heading', { level: 2, name: /0702646/ });
    // Reading the decision below the list, focus is in the panel, not the card.
    const back = screen.getByRole('button', { name: 'Voltar aos resultados' });
    back.focus();

    fireEvent.click(back);

    const card = screen.getByRole('link', { name: /Ler a decisão do processo 0702646/ });
    expect(card).toHaveFocus();
    expect(card.scrollIntoView).toHaveBeenCalled();
    expect(screen.getByText('57')).toBeInTheDocument();
    expect(within(screen.getByRole('list')).getAllByRole('article')).toHaveLength(2);
  });
});
