import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Decision } from '../api/decisions';
import DecisionDetail from '../components/DecisionDetail';
import DecisionResultCard from '../components/DecisionResultCard';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

const DECISION: Decision = {
  thesis: [],
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
  source_url_shared: false,
  class_code: 1116,
  judged_on: '2026-06-11',
  published_on: '2026-06-18',
  summary: 'EXECUÇÃO FISCAL. PRESCRIÇÃO INTERCORRENTE.',
  outcome: 'APELAÇÃO CONHECIDA E DESPROVIDA. UNÂNIME.',
  deliberation: 'unanime',
  full_text_available: true,
  sections: null,
};

const CARD = {
  court: 'TJDFT',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: '3ª TURMA CÍVEL',
  reporting_judge: 'JOÃO EGMONT',
  decided_on: '2026-06-11',
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2119440',
  source_url_reachable: true,
  deliberation: 'unanime' as string | null,
  snippet: 'Trecho qualquer.',
};

function renderDetail(overrides: Partial<Decision> = {}) {
  const decision = { ...DECISION, ...overrides };
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(JSON.stringify(decision), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    ),
  );
  render(<DecisionDetail id="detail" source={decision.source} identifier={decision.identifier} />);
  return screen.findByRole('heading', { level: 2 });
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the vote the panel took', () => {
  it('reads a unanimous decision as unanimous', async () => {
    await renderDetail({ deliberation: 'unanime' });

    expect(screen.getByText('Unânime')).toBeInTheDocument();
    expect(screen.queryByText('Por maioria')).not.toBeInTheDocument();
  });

  it('reads a divided decision as decided by majority', async () => {
    await renderDetail({
      deliberation: 'maioria',
      outcome: 'CONHECER. NEGAR PROVIMENTO. MAIORIA.',
    });

    expect(screen.getByText('Por maioria')).toBeInTheDocument();
    expect(screen.queryByText('Unânime')).not.toBeInTheDocument();
  });

  // These two and the one below are a pair. They read the same on a quick look
  // and mean opposite things about the source, so each denies the other's
  // label: unify the states and one of them fails.
  it('says the vote went unread when the court did publish a dispositive', async () => {
    await renderDetail({ deliberation: null });

    expect(screen.getByText('Não informado')).toBeInTheDocument();
    expect(screen.queryByText('Não aplicável')).not.toBeInTheDocument();
  });

  it('says the question does not arise when the court published none', async () => {
    await renderDetail({ deliberation: null, outcome: null });

    expect(screen.getByText('Não aplicável')).toBeInTheDocument();
    expect(screen.queryByText('Não informado')).not.toBeInTheDocument();
  });

  it('shows the sentence the label was read from, so the reader can check it', async () => {
    await renderDetail({
      deliberation: 'unanime',
      outcome: 'APELAÇÃO CONHECIDA E DESPROVIDA. UNÂNIME.',
    });

    expect(screen.getByText('APELAÇÃO CONHECIDA E DESPROVIDA. UNÂNIME.')).toBeInTheDocument();
  });

  it('says so in words, never in colour alone', async () => {
    await renderDetail({ deliberation: 'maioria' });

    // Found by its text, with no class or style consulted: a reader who sees
    // no colour still reads the state.
    const label = screen.getByText('Por maioria');

    expect(label.textContent).toBe('Por maioria');
  });

  it('never reads the vote from the result of the appeal', async () => {
    await renderDetail({
      deliberation: 'maioria',
      outcome: 'RECURSO CONHECIDO E DESPROVIDO. MAIORIA.',
    });

    expect(screen.getByText('Por maioria')).toBeInTheDocument();
  });
});

describe('the vote on the result card', () => {
  it('names it beside the other fields of the decision', () => {
    render(<DecisionResultCard decision={{ ...CARD, deliberation: 'maioria' }} />);

    expect(screen.getByText('Deliberação')).toBeInTheDocument();
    expect(screen.getByText('Por maioria')).toBeInTheDocument();
  });

  // The card has no dispositive, so it cannot tell the two undecided states
  // apart. Saying either one would be a guess the reader could not check.
  it('leaves the field out rather than guess which undecided state it is', () => {
    render(<DecisionResultCard decision={{ ...CARD, deliberation: null }} />);

    expect(screen.queryByText('Deliberação')).not.toBeInTheDocument();
    expect(screen.queryByText('Não informado')).not.toBeInTheDocument();
    expect(screen.queryByText('Não aplicável')).not.toBeInTheDocument();
  });
});
