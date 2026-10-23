import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import OutcomeSharePanel from '../components/OutcomeSharePanel';
import type { OutcomeState } from '../components/outcomeFormat';
import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

// One collection, answered by both routes. The search counts rows and the
// indicator aggregates them, so a fake that served each a number of its own
// could never catch the two disagreeing. Three decisions carry no outcome on
// purpose: the denominator is then smaller than the cut, which is the whole
// point of the card.
const OUTCOMES = ['negado', 'provido', 'parcialmente_provido', null] as const;

const COLLECTION = [
  ...Array.from({ length: 120 }, (_, i) => ({ court: 'STJ', n: i, outcome: OUTCOMES[0] })),
  ...Array.from({ length: 40 }, (_, i) => ({ court: 'STJ', n: 200 + i, outcome: OUTCOMES[1] })),
  ...Array.from({ length: 20 }, (_, i) => ({ court: 'TJDFT', n: 400 + i, outcome: OUTCOMES[2] })),
  ...Array.from({ length: 20 }, (_, i) => ({ court: 'TJDFT', n: 600 + i, outcome: OUTCOMES[3] })),
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function decision(n: number, court: string) {
  return {
    source: 'teste',
    identifier: `${court}${n}`,
    court,
    case_number: `0700${n}-11.2026.8.07.0001`,
    judging_body: '1ª TURMA CÍVEL',
    reporting_judge: 'RELATOR',
    decided_on: '2026-05-20',
    small_claims: false,
    source_url: `https://exemplo.test/${court}${n}`,
    source_url_reachable: true,
    deliberation: 'unanime',
    class_code: 198,
    judged_on: '2026-05-20',
    published_on: '2026-05-25',
    summary: `Ementa ${court}${n}.`,
    outcome: null,
    full_text_available: true,
    sections: null,
    snippet: 'Trecho.',
  };
}

function installApi({ shareFails = false } = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));

      if (url.pathname === '/decisions') {
        return json({
          total: COLLECTION.length,
          page: 1,
          page_size: 20,
          range_from: 1,
          range_to: 20,
          results: COLLECTION.slice(0, 20).map((d) => decision(d.n, d.court)),
        });
      }

      if (url.pathname === '/indicators/outcome-share') {
        if (shareFails) {
          return json({ detail: 'Indisponível.' }, 503);
        }
        const counted = new Map<string, number>();
        let unclassified = 0;
        for (const row of COLLECTION) {
          if (row.outcome === null) {
            unclassified += 1;
          } else {
            counted.set(row.outcome, (counted.get(row.outcome) ?? 0) + 1);
          }
        }
        const classified = COLLECTION.length - unclassified;
        return json({
          total: COLLECTION.length,
          classified,
          unclassified,
          outcomes: [...counted].map(([outcome, decisions]) => ({
            outcome,
            decisions,
            share: Math.round((decisions / classified) * 1000) / 10,
          })),
        });
      }

      if (url.pathname === '/indicators/volume-by-court') {
        return json({ total: COLLECTION.length, courts: [] });
      }

      if (url.pathname === '/indicators/last-update') {
        return json({ state: 'loaded', updated_at: '2026-09-18T14:42:03Z', records: 7 });
      }

      const detail = url.pathname.match(/^\/decisions\/[^/]+\/([^/]+)$/);
      if (detail) {
        return json(decision(0, 'STJ'));
      }

      return json({ courts: [{ abbreviation: 'STJ', name: 'STJ' }] });
    }),
  );
}

const digits = (text: string | null | undefined) => Number((text ?? '').replace(/\D/g, ''));

const card = () => within(screen.getByRole('article', { name: 'Resultado dos recursos' }));

async function search(user: ReturnType<typeof userEvent.setup>, expression: string) {
  const box = screen.getByLabelText('Pesquisar decisões');
  await user.clear(box);
  await user.type(box, expression);
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article', { name: /Ler a decisão|processo/ }).catch(() => null);
}

async function openPanorama(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await user.click(screen.getByRole('button', { name: 'Como os recursos foram julgados' }));
  await screen.findByRole('article', { name: 'Resultado dos recursos' });
}

const loaded = (over: Partial<Record<string, unknown>> = {}): OutcomeState => ({
  status: 'loaded',
  outcome: {
    total: 5869,
    classified: 5722,
    unclassified: 147,
    outcomes: [
      { outcome: 'negado', decisions: 4343, share: 75.9 },
      { outcome: 'provido', decisions: 1147, share: 20.0 },
      { outcome: 'parcialmente_provido', decisions: 232, share: 4.1 },
    ],
    ...over,
  },
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the four states the card has to keep apart', () => {
  const states: [string, OutcomeState, RegExp][] = [
    ['before any search', { status: 'idle' }, /Pesquise um tema/],
    ['the indicator failed', { status: 'failed', message: 'Falhou.' }, /Falhou\./],
    [
      'the cut matched nothing',
      {
        status: 'loaded',
        outcome: { total: 0, classified: 0, unclassified: 0, outcomes: [] },
      },
      /Nenhuma decisão encontrada/,
    ],
    [
      'it matched and nothing could be read',
      {
        status: 'loaded',
        outcome: { total: 12, classified: 0, unclassified: 12, outcomes: [] },
      },
      /Nenhuma decisão do recorte teve o resultado declarado/,
    ],
  ];

  // Found by what they say, never by a class name: a reader tells them apart by
  // the words, and two states that share a message are one state.
  it.each(states)('%s', (_name, state, said) => {
    render(<OutcomeSharePanel outcome={state} onRetry={() => {}} />);

    expect(screen.getByText(said)).toBeInTheDocument();
  });

  it('offers a way to ask again only when it failed', () => {
    render(<OutcomeSharePanel outcome={states[1][1]} onRetry={() => {}} />);

    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
  });
});

describe('the denominator', () => {
  it('is on screen with no interaction, and so is what fell outside it', () => {
    render(<OutcomeSharePanel outcome={loaded()} onRetry={() => {}} />);

    expect(screen.getByText('5.722')).toBeInTheDocument();
    expect(screen.getByText(/com resultado declarado/)).toBeInTheDocument();
    expect(screen.getByText(/147 sem declaração/)).toBeInTheDocument();
  });

  it('is never the cut: the two are different numbers and both are said', () => {
    render(<OutcomeSharePanel outcome={loaded()} onRetry={() => {}} />);

    expect(screen.getByText(/5\.869 decisões no recorte/)).toBeInTheDocument();
    expect(screen.getByText('5.722')).toBeInTheDocument();
  });

  it('draws the same outcomes, in the same order, as the list states', () => {
    const { container } = render(<OutcomeSharePanel outcome={loaded()} onRetry={() => {}} />);

    const drawn = [...container.querySelectorAll('.outcome-chart__part')];
    const listed = [...container.querySelectorAll('.outcome-list__swatch')];

    expect(drawn.map((part) => part.getAttribute('data-outcome'))).toEqual(
      listed.map((swatch) => swatch.getAttribute('data-outcome')),
    );

    // Lengths over the denominator the list states, not over the cut.
    const widths = drawn.map((part) => Number((part as HTMLElement).style.width.replace('%', '')));
    expect(widths[0]).toBeCloseTo((4343 / 5722) * 100, 1);
    expect(widths.reduce((sum, w) => sum + w, 0)).toBeCloseTo(100, 1);
  });

  it('hides the drawing from screen readers, which read the list instead', () => {
    const { container } = render(<OutcomeSharePanel outcome={loaded()} onRetry={() => {}} />);

    expect(container.querySelector('.outcome-chart')).toHaveAttribute('aria-hidden', 'true');
  });

  it('carries every outcome as text, with its own count beside its share', () => {
    render(<OutcomeSharePanel outcome={loaded()} onRetry={() => {}} />);

    for (const [label, count, share] of [
      ['Negado', '4.343', '75,9%'],
      ['Provido', '1.147', '20,0%'],
      ['Parcialmente provido', '232', '4,1%'],
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
      expect(screen.getByText(count)).toBeInTheDocument();
      expect(screen.getByText(share)).toBeInTheDocument();
    }
  });
});

describe('the panel and the results agree on the same cut', () => {
  it('adds the parts back up to the denominator, and that to the cut', async () => {
    installApi();
    const user = userEvent.setup();
    renderApp();

    await search(user, 'dano moral');
    await openPanorama(user);

    const panel = card();
    const cut = digits(panel.getByText(/decis(ão|ões) no recorte/).textContent);
    // The denominator holds both numbers, so each is read from the element
    // that carries it alone.
    const denominator = panel.getByText(/com resultado declarado/);
    const classified = digits(denominator.querySelector('strong')?.textContent);
    const unclassified = digits(panel.getByText(/sem declaração/).textContent);

    const counts = [...document.querySelectorAll('.outcome-list__count')].map((node) =>
      digits(node.textContent),
    );

    expect(cut).toBe(COLLECTION.length);
    expect(classified + unclassified).toBe(cut);
    expect(counts.reduce((sum, n) => sum + n, 0)).toBe(classified);
  });

  it('keeps the results readable when the indicator alone is unavailable', async () => {
    installApi({ shareFails: true });
    const user = userEvent.setup();
    renderApp();

    await search(user, 'dano moral');

    // The failure belongs to the panorama, so the list the reader came for is
    // untouched by it.
    const total = await screen.findByText(String(COLLECTION.length));
    expect(total).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Panorama' }));
    await user.click(screen.getByRole('button', { name: 'Como os recursos foram julgados' }));

    expect(await screen.findByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
  });
});
