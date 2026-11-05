import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { readConcentration, type Concentration } from '../api/indicators';
import ConcentrationPanel from '../components/ConcentrationPanel';
import type { ConcentrationState } from '../components/concentrationFormat';
import { selectIndicator } from '../search/indicatorSelection';
import { resetBuffer } from '../search/resultsBuffer';
import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

// One collection, answered by both routes: the indicator groups it and the
// search filters it. A fake that gave each route a number of its own could
// never catch a slice opening onto decisions other than the ones it counted.
// Two spellings of one judge on purpose, and two decisions without a judge.
type Row = { n: number; body: string; judge: string | null; date: string };
const SPREAD: [string | null, string, number][] = [
  ['JOÃO SILVA', 'CORTE ESPECIAL', 40],
  ['JOAO SILVA', 'TERCEIRA TURMA', 25],
  ['MARIA SOUZA', 'TERCEIRA TURMA', 10],
  ['PEDRO LIMA', 'QUARTA TURMA', 8],
  ['ANA COSTA', 'QUINTA TURMA', 6],
  ['RUI BARROS', 'SEXTA TURMA', 4],
  ['LIA MOTA', 'PRIMEIRA SEÇÃO', 3],
  [null, 'SEGUNDA SEÇÃO', 2],
];
const COLLECTION: Row[] = SPREAD.flatMap(([judge, body, howMany], group) =>
  Array.from({ length: howMany }, (_, i) => ({
    n: group * 100 + i,
    body,
    judge,
    date: i % 2 ? '2024-03-10' : '2023-03-10',
  })),
);

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function cut(url: URL): Row[] {
  const p = url.searchParams;
  const keep = (values: string[], value: string | null) =>
    !values.length || (value !== null && values.includes(value));
  return COLLECTION.filter(
    (row) =>
      keep(p.getAll('orgao_julgador'), row.body) &&
      keep(p.getAll('relator'), row.judge) &&
      !p.getAll('orgao_julgador_excluido').includes(row.body) &&
      (row.judge === null || !p.getAll('relator_excluido').includes(row.judge)) &&
      (!p.get('date_from') || row.date >= p.get('date_from')!),
  );
}

function concentrate(rows: Row[], key: 'body' | 'judge', limit: number) {
  const counted = new Map<string, number>();
  let missing = 0;
  for (const row of rows) {
    const name = row[key];
    if (name === null) missing += 1;
    else counted.set(name, (counted.get(name) ?? 0) + 1);
  }
  const named = [...counted].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
  const share = (n: number) => Math.round((n / rows.length) * 1000) / 10;
  const rest = named.slice(limit).reduce((sum, [, n]) => sum + n, 0) + missing;
  return {
    groups: named
      .slice(0, limit)
      .map(([name, decisions]) => ({ name, decisions, share: share(decisions) })),
    other: rest
      ? { groups: Math.max(0, named.length - limit), decisions: rest, share: share(rest) }
      : null,
    missing,
  };
}

function decision(row: Row) {
  return {
    source: 'teste',
    identifier: String(row.n),
    court: 'STJ',
    case_number: `processo-${row.n}`,
    judging_body: row.body,
    reporting_judge: row.judge,
    decided_on: row.date,
    small_claims: null,
    source_url: 'https://example.test/decision',
    source_url_reachable: true,
    deliberation: null,
    snippet: 'Dano <mark>moral</mark>.',
  };
}

function api({ concentrationFails = false } = {}) {
  const requests: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requests.push(url);
      const rows = cut(url);
      switch (url.pathname) {
        case '/courts':
          return json({ courts: [{ abbreviation: 'STJ', name: 'Superior Tribunal de Justiça' }] });
        case '/filters':
          return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
        case '/indicators/last-update':
          return json({ state: 'loaded', updated_at: '2026-10-22T12:00:00Z' });
        case '/indicators/volume-by-court':
          return json({
            total: rows.length,
            courts: [{ abbreviation: 'STJ', name: 'Superior', decisions: rows.length }],
          });
        case '/indicators/concentration': {
          if (concentrationFails) return json({ detail: 'down' }, 503);
          const limit = Number(url.searchParams.get('limit') ?? 5);
          return json({
            total: rows.length,
            limit,
            judging_bodies: concentrate(rows, 'body', limit),
            reporting_judges: concentrate(rows, 'judge', limit),
          });
        }
        case '/decisions': {
          const page = Number(url.searchParams.get('page') ?? 1);
          const size = Number(url.searchParams.get('page_size') ?? 6);
          return json({
            total: rows.length,
            page,
            page_size: size,
            results: rows.slice((page - 1) * size, page * size).map(decision),
          });
        }
        default:
          // The first result's detail, opened beside the list.
          return json({
            ...decision(COLLECTION[0]),
            class_code: 198,
            judged_on: '2023-03-10',
            published_on: null,
            summary: 'Texto da decisão.',
            outcome: null,
            full_text_available: false,
            sections: null,
          });
      }
    }),
  );
  return requests;
}

const lastOf = (requests: URL[], path: string) =>
  requests.filter((u) => u.pathname === path).slice(-1)[0];

beforeEach(() => {
  resetBuffer();
  // jsdom has no native dialog API.
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

async function openConcentration() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await user.click(screen.getByRole('button', { name: 'Onde e por quem o tema é decidido' }));
  await screen.findByRole('button', { name: /Consultar documentos do relator JOÃO SILVA/ });
  return user;
}

describe('the concentration in the Panorama', () => {
  it('shows both rankings with the rest folded into one counted group', async () => {
    api();
    await openConcentration();
    const judges = screen.getByRole('region', { name: 'Por relator' });
    const bodies = screen.getByRole('region', { name: 'Por órgão julgador' });

    const judgeTargets = within(judges).getAllByRole('button');
    expect(judgeTargets.map((b) => b.getAttribute('aria-label'))).toEqual([
      'Consultar documentos do relator JOÃO SILVA: 40 decisões',
      'Consultar documentos do relator JOAO SILVA: 25 decisões',
      'Consultar documentos do relator MARIA SOUZA: 10 decisões',
      'Consultar documentos do relator PEDRO LIMA: 8 decisões',
      'Consultar documentos do relator ANA COSTA: 6 decisões',
      'Consultar documentos dos demais relatores: 9 decisões',
    ]);
    const rest = judgeTargets[judgeTargets.length - 1];
    expect(rest).toHaveTextContent('Demais relatores');
    expect(rest).toHaveTextContent('2 relatores fora das 5 primeiras posições');
    expect(rest).toHaveTextContent('com 2 decisões sem relator informado');
    expect(within(bodies).getAllByRole('button')).toHaveLength(6);
    const region = document.getElementById('dimension-concentration')!;
    expect(within(region).getByText('98 decisões no recorte')).toBeInTheDocument();
  });

  it('asks for the same cut as the other indicators, filters included', async () => {
    const requests = api();
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: /Filtros/ }));
    fireEvent.change(
      within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText('De'),
      { target: { value: '2024-01-01' } },
    );
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await user.click(screen.getByRole('tab', { name: 'Panorama' }));
    await user.click(screen.getByRole('button', { name: 'Onde e por quem o tema é decidido' }));
    await screen.findByRole('button', { name: /Consultar documentos do relator JOÃO SILVA: 20/ });

    const asked = new URLSearchParams(lastOf(requests, '/indicators/concentration').search);
    expect(asked.get('limit')).toBe('5');
    asked.delete('limit');
    expect(asked.toString()).toBe(
      lastOf(requests, '/indicators/volume-by-court').searchParams.toString(),
    );
    expect(asked.get('date_from')).toBe('2024-01-01');
    expect(asked.get('q')).toBeTruthy();
  });

  it('opens a judge onto exactly the decisions it counted, keeping the search', async () => {
    const requests = api();
    const user = await openConcentration();
    await user.click(
      screen.getByRole('button', { name: /Consultar documentos do relator JOAO SILVA/ }),
    );

    const drawer = screen.getByRole('dialog', { name: 'JOAO SILVA: 25 decisões' });
    await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
    const search = lastOf(requests, '/decisions').searchParams;
    expect(search.getAll('relator')).toEqual(['JOAO SILVA']);
    expect(search.get('q')).toBe(
      lastOf(requests, '/indicators/concentration').searchParams.get('q'),
    );
    expect(within(drawer).queryByText(/A consulta retornou/)).toBeNull();
    expect(
      within(drawer).getByRole('button', {
        name: 'Remover seleção do indicador Relator: JOAO SILVA',
      }),
    ).toBeInTheDocument();
  });

  it('opens a judging body through the judging-body filter', async () => {
    const requests = api();
    const user = await openConcentration();
    await user.click(
      screen.getByRole('button', {
        name: /Consultar documentos do órgão julgador TERCEIRA TURMA/,
      }),
    );

    const drawer = screen.getByRole('dialog', { name: 'TERCEIRA TURMA: 35 decisões' });
    await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
    expect(lastOf(requests, '/decisions').searchParams.getAll('orgao_julgador')).toEqual([
      'TERCEIRA TURMA',
    ]);
    expect(within(drawer).queryByText(/A consulta retornou/)).toBeNull();
  });

  it('opens the folded rest as the cut minus the ranked names, missing values included', async () => {
    const requests = api();
    const user = await openConcentration();
    await user.click(
      screen.getByRole('button', { name: /Consultar documentos dos demais relatores/ }),
    );

    const drawer = screen.getByRole('dialog', { name: 'Demais relatores: 9 decisões' });
    await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
    const search = lastOf(requests, '/decisions').searchParams;
    expect(search.getAll('relator_excluido')).toEqual([
      'JOÃO SILVA',
      'JOAO SILVA',
      'MARIA SOUZA',
      'PEDRO LIMA',
      'ANA COSTA',
    ]);
    expect(search.getAll('relator')).toEqual([]);
    expect(within(drawer).queryByText(/A consulta retornou/)).toBeNull();
  });

  it('closing the drawer returns to the concentration without asking for it again', async () => {
    const requests = api();
    const user = await openConcentration();
    const before = requests.filter((u) => u.pathname.startsWith('/indicators/')).length;
    await user.click(
      screen.getByRole('button', { name: /Consultar documentos do relator MARIA SOUZA/ }),
    );
    const drawer = screen.getByRole('dialog');
    await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
    await user.click(within(drawer).getByRole('button', { name: 'Voltar ao Panorama' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(
      screen.getByRole('button', { name: 'Onde e por quem o tema é decidido' }),
    ).toHaveAttribute('aria-expanded', 'true');
    expect(requests.filter((u) => u.pathname.startsWith('/indicators/'))).toHaveLength(before);
  });

  it('a failed concentration offers a retry that asks again', async () => {
    const requests = api({ concentrationFails: true });
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await user.click(screen.getByRole('tab', { name: 'Panorama' }));
    await user.click(screen.getByRole('button', { name: 'Onde e por quem o tema é decidido' }));
    const region = document.getElementById('dimension-concentration')!;
    const alert = await within(region).findByRole('alert');
    const asked = requests.filter((u) => u.pathname === '/indicators/concentration').length;

    await user.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));

    await waitFor(() =>
      expect(requests.filter((u) => u.pathname === '/indicators/concentration').length).toBe(
        asked + 1,
      ),
    );
  });
});

const dimension = (groups: [string, number][], other: number | null = null, missing = 0) => ({
  groups: groups.map(([name, decisions]) => ({ name, decisions, share: decisions })),
  other: other === null ? null : { groups: 3, decisions: other, share: other },
  missing,
});

function loaded(total: number): ConcentrationState {
  const concentration: Concentration = {
    total,
    limit: 5,
    judging_bodies: dimension([['CORTE ESPECIAL', total]]),
    reporting_judges: dimension([['JOÃO SILVA', total]]),
  };
  return { status: 'loaded', concentration };
}

describe('the concentration panel on its own', () => {
  it.each([12, 29])('says a cut of %i decisions is too small instead of drawing it', (total) => {
    render(<ConcentrationPanel concentration={loaded(total)} onRetry={() => undefined} />);

    expect(screen.getByText(/poucas para indicar concentração/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Consultar documentos/ })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Por relator' })).toBeNull();
  });

  it('draws a cut of exactly the minimum', () => {
    render(<ConcentrationPanel concentration={loaded(30)} onRetry={() => undefined} />);

    expect(screen.queryByText(/poucas para indicar concentração/)).toBeNull();
    expect(screen.getByRole('region', { name: 'Por relator' })).toBeInTheDocument();
  });

  it('keeps no-match apart from a small cut', () => {
    render(<ConcentrationPanel concentration={loaded(0)} onRetry={() => undefined} />);

    expect(screen.getByText(/Nenhuma decisão encontrada/)).toBeInTheDocument();
    expect(screen.queryByText(/poucas para indicar/)).toBeNull();
  });

  it('shows no rest group when nothing is left over', () => {
    render(<ConcentrationPanel concentration={loaded(40)} onRetry={() => undefined} />);

    expect(screen.queryByText(/Demais/)).toBeNull();
  });

  it('a rest made only of missing values still says what it holds', () => {
    const state: ConcentrationState = {
      status: 'loaded',
      concentration: {
        total: 40,
        limit: 5,
        judging_bodies: dimension([['CORTE ESPECIAL', 40]]),
        reporting_judges: {
          groups: [{ name: 'JOÃO SILVA', decisions: 38, share: 95 }],
          other: { groups: 0, decisions: 2, share: 5 },
          missing: 2,
        },
      },
    };
    render(
      <ConcentrationPanel
        concentration={state}
        onRetry={() => undefined}
        onSelect={() => undefined}
      />,
    );

    expect(
      screen.getByRole('button', { name: /Consultar documentos dos demais relatores: 2/ }),
    ).toHaveTextContent('Fora das 5 primeiras posições, com 2 decisões sem relator informado');
  });

  it('every slice is disabled while the screen cannot open it', () => {
    render(
      <ConcentrationPanel
        concentration={{
          status: 'loaded',
          concentration: {
            total: 50,
            limit: 5,
            judging_bodies: dimension([['CORTE ESPECIAL', 40]], 10),
            reporting_judges: dimension([['JOÃO SILVA', 40]], 10),
          },
        }}
        onRetry={() => undefined}
        onSelect={() => undefined}
        selectionDisabled
      />,
    );

    for (const target of screen.getAllByRole('button', { name: /Consultar documentos/ }))
      expect(target).toBeDisabled();
  });
});

describe('reading the answer', () => {
  it('keeps each name exactly as the source wrote it and drops a nameless group', () => {
    const read = readConcentration({
      total: 3,
      limit: 5,
      judging_bodies: { groups: [], other: null, missing: 0 },
      reporting_judges: {
        groups: [
          { name: 'JOÃO  SILVA ', decisions: 1, share: 33.3 },
          { name: 'joão silva', decisions: 1, share: 33.3 },
          { name: '   ', decisions: 1, share: 33.3 },
        ],
        other: null,
        missing: 0,
      },
    });

    expect(read.reporting_judges.groups.map((g) => g.name)).toEqual(['JOÃO  SILVA ', 'joão silva']);
  });

  it('survives an answer it cannot read', () => {
    const read = readConcentration('nonsense');

    expect(read.total).toBeNull();
    expect(read.judging_bodies).toEqual({ groups: [], other: null, missing: null });
  });
});

describe('selecting a slice', () => {
  const original = {
    q: 'dano moral',
    tribunal: ['STJ'],
    relator: ['JOÃO SILVA', 'JOAO SILVA'],
    date_from: '2024-01-01',
    page: 3,
  };

  it('narrows a named judge inside every filter already applied', () => {
    const selected = selectIndicator(original, {
      kind: 'concentration',
      field: 'relator',
      name: 'JOAO SILVA',
      ranked: ['JOÃO SILVA', 'JOAO SILVA'],
      count: 25,
    });

    expect(selected.params).toEqual({ ...original, page: 1, relator: ['JOAO SILVA'] });
    expect(selected.contextLabel).toBe('Relator: JOAO SILVA');
  });

  it('never widens a judge filter into a judge outside it', () => {
    const selected = selectIndicator(original, {
      kind: 'concentration',
      field: 'relator',
      name: 'MARIA SOUZA',
      ranked: [],
      count: 0,
    });

    expect(selected.params).toBeNull();
  });

  it('opens the rest by excluding the ranked names, keeping the field filter', () => {
    const selected = selectIndicator(original, {
      kind: 'concentration',
      field: 'orgao_julgador',
      name: null,
      ranked: ['CORTE ESPECIAL', 'TERCEIRA TURMA'],
      count: 9,
    });

    expect(selected.params).toEqual({
      ...original,
      page: 1,
      orgao_julgador_excluido: ['CORTE ESPECIAL', 'TERCEIRA TURMA'],
    });
    expect(selected.label).toBe('Demais órgãos julgadores');
    expect(selected.contextLabel).toBe('Órgão julgador: Demais órgãos julgadores');
  });
});
