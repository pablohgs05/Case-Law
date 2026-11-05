import { act, fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

// Only the address of the API is replaced: the request code under test is the
// real one, so what the aggregation is asked is what the app sends.
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

// 45 matches over three pages, so a later page can be asked for.
// Paged as the API pages: the size asked for is the size answered.
function page(url: URL) {
  const number = Number(url.searchParams.get('page') ?? 1);
  const pageSize = Number(url.searchParams.get('page_size') ?? 1);
  const offset = (number - 1) * pageSize;
  const size = Math.max(0, Math.min(pageSize, 45 - offset));
  return {
    total: 45,
    page: number,
    page_size: pageSize,
    range_from: size ? offset + 1 : null,
    range_to: size ? offset + size : null,
    results: Array.from({ length: size }, (_, i) => ({
      ...decision(`${number}${String(i).padStart(3, '0')}`),
      snippet: 'Trecho.',
    })),
  };
}

// Out of order on purpose, with a tie: the screen must rank them itself.
const VOLUME = {
  total: 11,
  courts: [
    { abbreviation: 'TJSP', name: 'Tribunal de Justiça de São Paulo', decisions: 3 },
    { abbreviation: 'TRF3', name: 'Tribunal Regional Federal da 3ª Região', decisions: 4 },
    { abbreviation: 'TJMG', name: 'Tribunal de Justiça de Minas Gerais', decisions: 2 },
    { abbreviation: 'STJ', name: 'Superior Tribunal de Justiça', decisions: 2 },
  ],
};
const RANKED = ['TRF3', 'TJSP', 'STJ', 'TJMG'];

const ONE_COURT = (count: number) => ({
  total: count,
  courts: [{ abbreviation: 'TJDFT', name: 'Tribunal de Justiça do DF', decisions: count }],
});

// 14:42 in UTC is 11:42 in Brasília: the date shown is the API's, read on
// the project's clock, never the moment the screen asked.
const LAST_UPDATE = { state: 'loaded', updated_at: '2026-09-18T14:42:03Z', records: 7 };

type Answer = (url: URL) => Response | Promise<Response>;

// The aggregation, the freshness and the search are counted apart, so "no new
// count" and "sent only the cut" are numbers a test can read.
function installApi({
  volume = () => json(VOLUME),
  lastUpdate = () => json(LAST_UPDATE),
}: { volume?: Answer; lastUpdate?: Answer } = {}) {
  const volumes: URL[] = [];
  const searches: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/indicators/volume-by-court') {
        volumes.push(url);
        return volume(url);
      }
      if (url.pathname === '/indicators/last-update') {
        return lastUpdate(url);
      }
      if (url.pathname === '/decisions') {
        searches.push(url);
        return json(page(url));
      }
      const detail = url.pathname.match(/^\/decisions\/[^/]+\/([^/]+)$/);
      if (detail) {
        return json(decision(detail[1]));
      }
      return json({
        courts: [{ abbreviation: 'TJDFT', name: 'Tribunal de Justiça do DF' }],
      });
    }),
  );
  return { volumes, searches };
}

const tab = (name: string) => screen.getByRole('tab', { name });
const panorama = () => within(screen.getByRole('tabpanel', { name: 'Panorama' }));
const chartCard = () => within(screen.getByRole('article', { name: 'Volume por tribunal' }));
const bars = () =>
  [...document.querySelectorAll('.volume-chart__row')].map((row) => [
    row.querySelector('.volume-chart__label')?.textContent,
    row.querySelector('.volume-chart__value')?.textContent,
  ]);
async function search(user: ReturnType<typeof userEvent.setup>, expression: string) {
  const box = screen.getByLabelText('Pesquisar decisões');
  await user.clear(box);
  await user.type(box, expression);
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article', { name: /Ler a decisão|processo/ }).catch(() => null);
}

async function applyFilters(user: ReturnType<typeof userEvent.setup>, from: string) {
  const toggle = screen.getByRole('button', { name: /filtros/i });
  if (toggle.getAttribute('aria-expanded') !== 'true') {
    await user.click(toggle);
  }
  const court = await screen.findByRole('checkbox', { name: /TJDFT/ });
  if (!(court as HTMLInputElement).checked) {
    await user.click(court);
  }
  const judged = screen.getByRole('group', { name: 'Data de julgamento' });
  fireEvent.change(within(judged).getByLabelText('De'), { target: { value: from } });
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the result tabs', () => {
  it('are Documentos and Panorama, and nothing else', async () => {
    installApi();
    renderApp();

    await userEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'Documentos',
      'Panorama',
    ]);
    expect(tab('Documentos')).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText(/Mapa da tese/i)).toBeNull();
    expect(screen.queryByText(/Diferencial/i)).toBeNull();
    expect(screen.queryByText(/tese defensável/i)).toBeNull();
  });

  it('move with the arrows, Home and End, keeping one tab in the Tab order', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    tab('Documentos').focus();
    await user.keyboard('{ArrowRight}');
    expect(tab('Panorama')).toHaveFocus();
    expect(tab('Panorama')).toHaveAttribute('aria-selected', 'true');
    expect(tab('Documentos')).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('tabpanel', { name: 'Panorama' })).toBeVisible();

    await user.keyboard('{Home}');
    expect(tab('Documentos')).toHaveFocus();
    expect(screen.getByRole('tabpanel', { name: 'Documentos' })).toBeVisible();

    await user.keyboard('{End}');
    expect(tab('Panorama')).toHaveFocus();

    // The panorama has no control of its own, so Tab reaches the panel itself.
    await user.tab();
    expect(screen.getByRole('tabpanel', { name: 'Panorama' })).toHaveFocus();
  });

  it('keep the search as it was: expression, filters, order, page and results', async () => {
    const { searches } = installApi();
    const user = userEvent.setup();
    renderApp();
    await applyFilters(user, '2026-01-01');
    await search(user, 'dano moral');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');
    await screen.findAllByRole('article');
    await user.click(screen.getByRole('button', { name: /próxima/i }));
    expect(await screen.findByText(/7–12 de 45/)).toBeVisible();
    const asked = searches.length;

    await user.click(tab('Panorama'));
    await chartCard().findByText('11 decisões no recorte');
    await user.click(tab('Documentos'));

    expect(screen.getByLabelText('Pesquisar decisões')).toHaveValue('dano moral');
    expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toHaveValue('date');
    expect(screen.getByRole('button', { name: /Filtros/ })).toHaveTextContent('2');
    expect(screen.getByText(/7–12 de 45/)).toBeVisible();
    expect(searches).toHaveLength(asked);
  });
});

describe('the aggregation request', () => {
  it('carries the applied expression and filters, never the page, the order or an edit', async () => {
    const { volumes } = installApi();
    const user = userEvent.setup();
    renderApp();
    await applyFilters(user, '2026-01-01');
    await search(user, 'dano moral');
    // Typed after the search: not applied, so not counted.
    await user.type(screen.getByLabelText('Pesquisar decisões'), ' material');

    await user.click(tab('Panorama'));
    await chartCard().findByText('11 decisões no recorte');

    expect(volumes).toHaveLength(1);
    const sent = volumes[0].searchParams;
    expect([...sent.keys()].sort()).toEqual(['date_from', 'q', 'tribunal']);
    expect(sent.get('q')).toBe('dano moral');
    expect(sent.getAll('tribunal')).toEqual(['TJDFT']);
    expect(sent.get('date_from')).toBe('2026-01-01');
  });

  it('is not repeated, nor changed, by another page or order of the same cut', async () => {
    const { volumes } = installApi();
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));
    await chartCard().findByText('11 decisões no recorte');

    // Looked at after each change on its own: another order starts the list on
    // its first page again, which would hide a page that leaked into the cut.
    await user.click(tab('Documentos'));
    await user.click(screen.getByRole('button', { name: /próxima/i }));
    await screen.findByText(/7–12 de 45/);
    await user.click(tab('Panorama'));

    expect(chartCard().getByText('11 decisões no recorte')).toBeVisible();
    expect(volumes).toHaveLength(1);

    await user.click(tab('Documentos'));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');
    await screen.findAllByRole('article');
    await user.click(tab('Panorama'));

    expect(chartCard().getByText('11 decisões no recorte')).toBeVisible();
    expect(volumes).toHaveLength(1);
  });

  it('follows new filters, including ones applied while the documents were up', async () => {
    const { volumes } = installApi({
      volume: (url) =>
        json(url.searchParams.get('date_from') === '2026-06-01' ? ONE_COURT(5) : VOLUME),
    });
    const user = userEvent.setup();
    renderApp();
    await applyFilters(user, '2026-01-01');
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));
    await chartCard().findByText('11 decisões no recorte');

    await user.click(tab('Documentos'));
    await applyFilters(user, '2026-06-01');
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');
    await user.click(tab('Panorama'));

    // The previous cut's counts are never shown for the new one.
    expect(chartCard().queryByText('11 decisões no recorte')).toBeNull();
    expect(await chartCard().findByText('5 decisões no recorte')).toBeVisible();
    expect(volumes).toHaveLength(2);
    expect(volumes[1].searchParams.get('date_from')).toBe('2026-06-01');
  });

  it('keeps the newest cut when an older answer arrives late', async () => {
    const answers: Record<string, (response: Response) => void> = {};
    installApi({
      volume: (url) =>
        new Promise<Response>((done) => (answers[url.searchParams.get('q') ?? ''] = done)),
    });
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));
    await user.click(tab('Documentos'));
    await search(user, 'dano material');
    await user.click(tab('Panorama'));

    await act(async () => answers['dano material'](json(ONE_COURT(5))));
    await act(async () => answers['dano moral'](json(VOLUME)));

    expect(chartCard().getByText('5 decisões no recorte')).toBeVisible();
    expect(chartCard().queryByText('11 decisões no recorte')).toBeNull();
  });
});

describe('the interactive chart', () => {
  it('rank the courts largest first even when the API does not, ties by abbreviation', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));
    await chartCard().findByText('11 decisões no recorte');

    expect(bars().map(([court]) => court)).toEqual(RANKED);
  });

  it('shows each court and count directly in an accessible chart button', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));
    await chartCard().findByText('11 decisões no recorte');

    const expected = [
      ['TRF3', '4'],
      ['TJSP', '3'],
      ['STJ', '2'],
      ['TJMG', '2'],
    ];
    expect(bars()).toEqual(expected);
    expect(screen.queryByRole('article', { name: 'Composição do recorte' })).toBeNull();
    for (const [court, count] of expected) {
      const target = screen.getByRole('button', {
        name: `Consultar documentos de ${court}: ${count} decisões`,
      });
      expect(target.closest('[aria-hidden="true"]')).toBeNull();
    }
  });

  it('measure the bars from zero on whole, round ticks', async () => {
    installApi({ volume: () => json(ONE_COURT(11700)) });
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));
    await panorama().findByText('11.700 decisões no recorte');

    const ticks = [...document.querySelectorAll('.volume-chart__tick')].map((t) => t.textContent);
    expect(ticks).toEqual(['0', '5.000', '10.000', '15.000']);
    const bar = document.querySelector('.volume-chart__bar') as HTMLElement;
    expect(bar.style.width).toBe('78%');
    expect(chartCard().getByText('11.700', { selector: '.volume-chart__value' })).toBeVisible();
  });

  it('say when the base was last updated, as the API reports it', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));

    expect(await chartCard().findByText('18/09/2026, 11:42')).toBeVisible();
    expect(chartCard().getByText(/Última atualização:/)).toBeVisible();
  });

  it('say the date is unavailable rather than show the time of the request', async () => {
    installApi({ lastUpdate: () => json({ detail: 'down' }, 503) });
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));

    expect(await chartCard().findByText('Indisponível')).toBeVisible();
    expect(chartCard().getByText('11 decisões no recorte')).toBeVisible();
  });
});

describe('the panorama without counts to draw', () => {
  it('asks for a search before there is one, and counts nothing', () => {
    const { volumes } = installApi();
    renderApp('/', [], false);

    expect(
      screen.getByRole('heading', { name: 'Comece pela questão jurídica que deseja investigar' }),
    ).toBeVisible();
    expect(screen.queryByRole('tab', { name: 'Panorama' })).not.toBeInTheDocument();
    expect(volumes).toHaveLength(0);
    expect(document.querySelector('.volume-chart')).toBeNull();
  });

  it('shows it is loading, with no number, until the count arrives', async () => {
    let answer!: (response: Response) => void;
    installApi({ volume: () => new Promise<Response>((done) => (answer = done)) });
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));

    expect(screen.getByRole('article', { name: 'Volume por tribunal' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(chartCard().getByText('Carregando o volume por tribunal')).toBeInTheDocument();
    expect(chartCard().queryByText(/decisões no recorte/)).toBeNull();

    await act(async () => answer(json(VOLUME)));

    expect(await chartCard().findByText('11 decisões no recorte')).toBeVisible();
  });

  it('says nothing was found, with no empty chart, when the cut has no decision', async () => {
    installApi({ volume: () => json({ total: 0, courts: [] }) });
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));

    expect(
      await chartCard().findByText(
        'Nenhuma decisão encontrada para os filtros aplicados. Ajuste os termos ou amplie o período.',
      ),
    ).toBeVisible();
    expect(document.querySelector('.volume-chart')).toBeNull();
    expect(screen.queryByRole('article', { name: 'Composição do recorte' })).toBeNull();
  });

  it('says it failed, never as no decisions, and asks again on Tentar novamente', async () => {
    let failing = true;
    const { volumes } = installApi({
      volume: () => (failing ? json({ detail: 'down' }, 503) : json(VOLUME)),
    });
    const user = userEvent.setup();
    renderApp();
    await search(user, 'dano moral');
    await user.click(tab('Panorama'));

    expect(await chartCard().findByRole('alert')).toHaveTextContent(
      'Não foi possível carregar o volume por tribunal.',
    );
    expect(panorama().queryByText(/Nenhuma decisão encontrada/)).toBeNull();

    failing = false;
    await user.click(chartCard().getByRole('button', { name: 'Tentar novamente' }));

    expect(await chartCard().findByText('11 decisões no recorte')).toBeVisible();
    expect(volumes).toHaveLength(2);
  });
});
