import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import DecisionResultCard from '../components/DecisionResultCard';

const base: Parameters<typeof DecisionResultCard>[0]['decision'] = {
  court: 'TJDFT',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: '3ª TURMA CÍVEL',
  reporting_judge: 'JOÃO EGMONT',
  decided_on: '2026-06-11',
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2119440',
  source_url_reachable: true,
  snippet: 'Trecho qualquer.',
};

function renderCard(overrides: Partial<typeof base> = {}) {
  render(<DecisionResultCard decision={{ ...base, ...overrides }} />);
  return screen.getByRole('link', { name: /fonte oficial/i });
}

describe('a link that reaches the document', () => {
  it('points at the court, not at us', () => {
    expect(renderCard()).toHaveAttribute('href', base.source_url);
  });

  it('opens in a new tab, so the search is not lost', () => {
    expect(renderCard()).toHaveAttribute('target', '_blank');
  });

  it('does not hand the court page a handle on ours', () => {
    expect(renderCard()).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('is reachable by keyboard', () => {
    expect(renderCard()).not.toHaveAttribute('aria-disabled', 'true');
  });
});

describe('a link the load found broken', () => {
  it('cannot be followed', () => {
    const link = renderCard({ source_url_reachable: false });

    expect(link).not.toHaveAttribute('href');
    expect(link).toHaveAttribute('aria-disabled', 'true');
  });

  it('is skipped by the keyboard instead of being a dead stop', () => {
    expect(renderCard({ source_url_reachable: false })).toHaveAttribute('tabindex', '-1');
  });

  it('says why', () => {
    render(<DecisionResultCard decision={{ ...base, source_url_reachable: false }} />);

    expect(screen.getByText('Link indisponível no momento.')).toBeInTheDocument();
  });
});

describe('a decision with no link at all', () => {
  it('is still shown, without a link to nowhere', () => {
    const link = renderCard({ source_url: '' });

    expect(link).not.toHaveAttribute('href');
    expect(screen.getByText('TJDFT')).toBeInTheDocument();
  });

  it('is treated as broken rather than as working', () => {
    expect(renderCard({ source_url: '' })).toHaveAttribute('aria-disabled', 'true');
  });
});

describe('a link nobody has checked yet', () => {
  it('is offered, because unverified is not broken', () => {
    const link = renderCard({ source_url_reachable: null });

    expect(link).toHaveAttribute('href', base.source_url);
    expect(link).not.toHaveAttribute('aria-disabled', 'true');
  });
});
