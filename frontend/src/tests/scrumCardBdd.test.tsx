import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import DecisionResultCard from '../components/DecisionResultCard';

describe('SCRUM-55: cartão de decisão — cenários propostos na planning', () => {
  it.each(['\n', '', '   '])('exibe orientação quando o trecho é %s', (snippet) => {
    // Given: componente isolado com props controladas; nenhuma API ou rede.
    const decision = {
      court: 'TJDFT',
      case_number: '123',
      judging_body: null,
      reporting_judge: null,
      decided_on: '2026-03-10',
      source_url: '',
      source_url_reachable: false,
      deliberation: null,
      snippet,
    };

    // When: o componente recebe uma decisão sem trecho utilizável.
    render(<DecisionResultCard decision={decision} />);

    // Then: o usuário vê uma orientação e continua identificando a decisão.
    expect(screen.getByText('Trecho indisponível.')).toBeInTheDocument();
    expect(screen.getByRole('article', { name: 'Decisão 123' })).toBeInTheDocument();
    expect(screen.getByText('TJDFT')).toBeInTheDocument();
  });
});
