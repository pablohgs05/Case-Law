import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { SearchDecisionMatch } from '../api/search';
import { rememberSession } from '../api/token';
import AppHeader from '../components/AppHeader';
import DecisionResultCard from '../components/DecisionResultCard';
import ReportsPage, { REPORTS_PATH } from '../pages/ReportsPage';
import { SessionContext, type Session } from '../session/sessionContext';
import { SIGNED_IN } from './renderApp';

/**
 * Reporting an incorrect classification (RF21), from where the tool owns it.
 *
 * Three promises. The report is tied to the decision and to the reading it
 * contests. The reader is told it arrived. And nothing on the card moves: the
 * classification shown is the published one, before the report and after.
 */

vi.mock('../api/client', async () => {
  const real = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...real, apiBaseUrl: 'http://localhost:8000', assertApiConfiguration: () => undefined };
});

const MATCH: SearchDecisionMatch = {
  source: 'tjdft-jurisdf',
  identifier: '2044172',
  court: 'TJDFT',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: '3ª TURMA CÍVEL',
  reporting_judge: 'JOÃO EGMONT',
  decided_on: '2026-06-11',
  small_claims: null,
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2044172',
  source_url_reachable: true,
  source_url_shared: false,
  deliberation: 'unanime',
  snippet: 'Recurso conhecido e <mark>desprovido</mark>.',
  thesis: ['O prazo corre da ciência da primeira diligência infrutífera.'],
};

const RECEIPT = {
  id: '5d7e1c8a-0000-4000-8000-000000000001',
  source: MATCH.source,
  identifier: MATCH.identifier,
  information: 'resultado',
  published_value: 'negado',
  description: 'O dispositivo diz provido em parte.',
  status: 'pendente',
  received_at: '2026-11-05T14:30:00Z',
  message:
    'Recebemos o seu reporte. A classificação publicada continua a mesma até que alguém o revise.',
};

function answering(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

function card(over: Partial<React.ComponentProps<typeof DecisionResultCard>> = {}) {
  return render(
    <MemoryRouter>
      <DecisionResultCard decision={MATCH} justifies="resultado" {...over} />
    </MemoryRouter>,
  );
}

async function openForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByText('Por que esta decisão está aqui'));
  await user.click(screen.getByRole('button', { name: 'Reportar classificação incorreta' }));
  return screen.getByRole('form', { name: 'Reportar classificação incorreta' });
}

function sentRequest(fetch: ReturnType<typeof vi.fn>) {
  const [url, init] = fetch.mock.calls[0] as [URL, RequestInit];
  return { url: url.toString(), init, body: JSON.parse(String(init.body)) as unknown };
}

beforeEach(() => {
  rememberSession('um-token');
});

afterEach(() => {
  rememberSession(null);
  vi.unstubAllGlobals();
});

describe('reportar dentro da justificativa', () => {
  it('o botão mora no bloco "Por que esta decisão está aqui"', () => {
    card();

    const bloco = screen.getByText('Por que esta decisão está aqui').closest('details');

    expect(bloco).not.toBeNull();
    expect(
      within(bloco!).getByRole('button', { name: 'Reportar classificação incorreta' }),
    ).toBeInTheDocument();
  });

  it('não é oferecido onde não há leitura nossa a contestar', () => {
    card({ justifies: undefined });

    expect(screen.queryByText('Reportar classificação incorreta')).not.toBeInTheDocument();
  });

  it('não é oferecido quando o card não sabe qual decisão é', () => {
    const { source: _source, identifier: _identifier, ...semIdentidade } = MATCH;
    card({ decision: semIdentidade });

    expect(screen.queryByText('Reportar classificação incorreta')).not.toBeInTheDocument();
  });

  it('vincula o reporte à decisão e à informação contestada', async () => {
    const fetch = answering(RECEIPT, 201);
    vi.stubGlobal('fetch', fetch);
    const user = userEvent.setup();
    card();

    const form = await openForm(user);
    // The reading the block was justifying comes chosen.
    expect(within(form).getByLabelText('Qual informação está incorreta?')).toHaveValue('resultado');
    await user.selectOptions(
      within(form).getByLabelText('Qual informação está incorreta?'),
      'deliberacao',
    );
    await user.type(within(form).getByLabelText('O que está incorreto?'), '  Houve voto vencido. ');
    await user.click(within(form).getByRole('button', { name: 'Enviar reporte' }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const { url, init, body } = sentRequest(fetch);
    expect(url).toBe('http://localhost:8000/decisions/tjdft-jurisdf/2044172/reports');
    expect(init.method).toBe('POST');
    expect(body).toEqual({ information: 'deliberacao', description: 'Houve voto vencido.' });
    // Who reported is the account behind the token, never a field the screen
    // fills in.
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer um-token');
  });

  it('a aderência chega escolhida quando é ela que o bloco justifica', async () => {
    const user = userEvent.setup();
    card({ justifies: 'aderencia' });

    const form = await openForm(user);

    expect(within(form).getByLabelText('Qual informação está incorreta?')).toHaveValue('aderencia');
  });

  it('confirma o recebimento ao usuário', async () => {
    vi.stubGlobal('fetch', answering(RECEIPT, 201));
    const user = userEvent.setup();
    card();

    const form = await openForm(user);
    await user.type(within(form).getByLabelText('O que está incorreto?'), 'Foi provido em parte.');
    await user.click(within(form).getByRole('button', { name: 'Enviar reporte' }));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Recebemos o seu reporte. A classificação publicada continua a mesma',
    );
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
  });

  it('a classificação mostrada no card continua a mesma depois do reporte', async () => {
    // Nothing on the card is rewritten from the report, and the search is not
    // asked again: the one request is the report itself.
    const fetch = answering({ ...RECEIPT, information: 'deliberacao' }, 201);
    vi.stubGlobal('fetch', fetch);
    const user = userEvent.setup();
    const { container } = card();

    const article = container.querySelector('article')!;
    const meta = () => article.querySelector('.decision-result-card__meta')!.textContent;
    const snippet = () => article.querySelector('.decision-result-card__snippet')!.innerHTML;
    const tese = () => article.querySelector('.decision-result-card__thesis-list')!.textContent;
    const leitura = () =>
      article.querySelector('.decision-result-card__thesis-reading')!.textContent;
    const antes = { meta: meta(), snippet: snippet(), tese: tese(), leitura: leitura() };
    expect(antes.meta).toContain('Unânime');

    const form = await openForm(user);
    await user.selectOptions(
      within(form).getByLabelText('Qual informação está incorreta?'),
      'deliberacao',
    );
    await user.type(within(form).getByLabelText('O que está incorreto?'), 'Foi por maioria.');
    await user.click(within(form).getByRole('button', { name: 'Enviar reporte' }));
    await screen.findByRole('status');

    expect({ meta: meta(), snippet: snippet(), tese: tese(), leitura: leitura() }).toEqual(antes);
    expect(meta()).toContain('Unânime');
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('não envia um relato vazio', async () => {
    const fetch = answering(RECEIPT, 201);
    vi.stubGlobal('fetch', fetch);
    const user = userEvent.setup();
    card();

    const form = await openForm(user);
    const relato = within(form).getByLabelText('O que está incorreto?');
    // `required` alone would stop the browser; this is the screen's own check,
    // for a relato made only of spaces.
    relato.removeAttribute('required');
    await user.type(relato, '   ');
    await user.click(within(form).getByRole('button', { name: 'Enviar reporte' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Descreva o que está incorreto.');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('diz quando não chegou, e guarda o que foi escrito', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    const user = userEvent.setup();
    card();

    const form = await openForm(user);
    await user.type(within(form).getByLabelText('O que está incorreto?'), 'Foi provido.');
    await user.click(within(form).getByRole('button', { name: 'Enviar reporte' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível falar');
    expect(screen.queryByText(/Recebemos o seu reporte/)).not.toBeInTheDocument();
    expect(within(form).getByLabelText('O que está incorreto?')).toHaveValue('Foi provido.');
  });
});

const LISTED = {
  reports: [
    {
      ...RECEIPT,
      information: 'tese',
      published_value: 'O prazo corre da ciência.',
      description: 'A tese é outra.',
      reported_by: {
        id: 'b0b0b0b0-0000-4000-8000-000000000002',
        name: 'Bruno Dias',
        email: 'bruno@almeidacosta.com.br',
      },
    },
  ],
};

function session(role: 'gerente' | 'usuario'): Session {
  return {
    status: 'signed in',
    person: { ...SIGNED_IN, role },
    signIn: async () => undefined,
    signOut: () => undefined,
  };
}

function reportsPage(role: 'gerente' | 'usuario') {
  return render(
    <MemoryRouter>
      <SessionContext.Provider value={session(role)}>
        <ReportsPage />
      </SessionContext.Provider>
    </MemoryRouter>,
  );
}

describe('a lista de reportes do gerente', () => {
  it('mostra cada reporte com a decisão, a informação, o relato e quem reportou', async () => {
    const fetch = answering(LISTED);
    vi.stubGlobal('fetch', fetch);
    reportsPage('gerente');

    const item = (await screen.findByText('A tese é outra.')).closest('li')!;

    expect((fetch.mock.calls[0] as [URL])[0].toString()).toBe('http://localhost:8000/reports');
    expect(within(item).getByText('Tese')).toBeInTheDocument();
    expect(within(item).getByText('aguardando revisão')).toBeInTheDocument();
    expect(within(item).getByText(/O prazo corre da ciência\./)).toBeInTheDocument();
    expect(within(item).getByText(/Bruno Dias · bruno@almeidacosta\.com\.br/)).toBeInTheDocument();
    expect(within(item).getByRole('link', { name: 'Abrir decisão' })).toHaveAttribute(
      'href',
      '/decisoes/tjdft-jurisdf/2044172',
    );
  });

  it('diz quando ainda não há reporte', async () => {
    vi.stubGlobal('fetch', answering({ reports: [] }));
    reportsPage('gerente');

    expect(await screen.findByText('Nenhum reporte recebido até agora.')).toBeInTheDocument();
  });

  it('não pede a lista para quem não é gerente', () => {
    const fetch = answering(LISTED);
    vi.stubGlobal('fetch', fetch);
    reportsPage('usuario');

    expect(screen.getByRole('alert')).toHaveTextContent('Só um gerente vê os reportes.');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('a barra leva o gerente aos reportes, e só o gerente', () => {
    const bar = (role: 'gerente' | 'usuario') =>
      render(
        <MemoryRouter>
          <SessionContext.Provider value={session(role)}>
            <AppHeader />
          </SessionContext.Provider>
        </MemoryRouter>,
      );

    const gerente = bar('gerente');
    expect(screen.getByRole('link', { name: /Reportes/ })).toHaveAttribute('href', REPORTS_PATH);
    gerente.unmount();

    bar('usuario');
    expect(screen.queryByRole('link', { name: /Reportes/ })).not.toBeInTheDocument();
  });
});
