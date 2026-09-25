import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import DecisionResultCard from '../components/DecisionResultCard';

const decision = {
  court: 'TJDFT',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: '3ª TURMA CÍVEL',
  reporting_judge: 'JOÃO EGMONT',
  decided_on: '2026-06-11',
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2119440',
  source_url_reachable: true,
  snippet: 'Contrato de transporte. <mark>Dano moral</mark> configurado.',
};

describe('DecisionResultCard', () => {
  it('shows the metadata a reader needs to judge relevance', () => {
    render(<DecisionResultCard decision={decision} />);

    expect(screen.getByText('TJDFT')).toBeInTheDocument();
    expect(screen.getByText('3ª TURMA CÍVEL')).toBeInTheDocument();
    expect(screen.getByText('JOÃO EGMONT')).toBeInTheDocument();

    // The case number is written twice on purpose: once in the header, where
    // it identifies the card, and once in the metadata list beside its label.
    expect(screen.getAllByText('0712598-03.2019.8.07.0003')).toHaveLength(2);
  });

  it('leaves out a field the search did not send, rather than an empty label', () => {
    render(<DecisionResultCard decision={{ ...decision, judging_body: null }} />);

    expect(screen.queryByText('Órgão julgador')).not.toBeInTheDocument();
    expect(screen.getByText('Relator')).toBeInTheDocument();
  });
});
