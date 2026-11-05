import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { SearchDecisionMatch } from '../api/search';
import DecisionResultCard from '../components/DecisionResultCard';
import { selectIndicator } from '../search/indicatorSelection';

/**
 * Why a decision is in this list, said on the card.
 *
 * The justification answers for a classification this tool inferred. Volume
 * and timeline are fields copied from the source — there is nothing of the
 * court's to point at and no claim of ours to answer for — so turning it on
 * everywhere would promise a justification the tool cannot give.
 */

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
  snippet: 'Recurso conhecido e desprovido.',
  thesis: ['O prazo corre da ciência da primeira diligência infrutífera.'],
};

function card(over: Partial<React.ComponentProps<typeof DecisionResultCard>> = {}) {
  return render(
    <MemoryRouter>
      <DecisionResultCard decision={MATCH} to="/decisions/tjdft-jurisdf/2044172" {...over} />
    </MemoryRouter>,
  );
}

describe('a justificativa no card', () => {
  it('aparece na lista vinda do indicador de resultado', () => {
    card({ justifies: 'resultado' });

    expect(screen.getByText('Por que esta decisão está aqui')).toBeInTheDocument();
    expect(screen.getByText(/O resultado é leitura automática/)).toBeInTheDocument();
  });

  it('aparece na lista vinda do indicador de aderência', () => {
    card({ justifies: 'aderencia' });

    expect(screen.getByText('Por que esta decisão está aqui')).toBeInTheDocument();
    expect(screen.getByText(/A aderência é leitura automática/)).toBeInTheDocument();
  });

  it('não aparece nos indicadores sem inferência nossa', () => {
    // The rule the card states: it fails if someone turns it on for
    // everything. Court and period classify by a copied field.
    const original = { q: 'dano moral' };
    const porTribunal = selectIndicator(original, { kind: 'court', court: 'STJ', count: 2 });
    const porPeriodo = selectIndicator(original, {
      kind: 'period',
      period: '2026-03',
      granularity: 'month',
      count: 2,
    });

    for (const selecionado of [porTribunal, porPeriodo]) {
      const { unmount } = card({ justifies: selecionado.params?.highlight });
      expect(screen.queryByText('Por que esta decisão está aqui')).not.toBeInTheDocument();
      unmount();
    }
  });

  it('separa o que o tribunal escreveu do que a ferramenta leu', () => {
    // Verifiable in the test, not only visual: the court's own text is
    // attributed to the court, and the inference says it is one.
    card({ justifies: 'resultado' });

    const bloco = screen.getByText('Por que esta decisão está aqui').closest('details');
    expect(bloco).not.toBeNull();

    expect(within(bloco!).getByText('Tese firmada pelo tribunal')).toBeInTheDocument();
    expect(within(bloco!).getByText(/leitura automática desta ferramenta/)).toBeInTheDocument();
  });

  it('começa fechado, para seis cards não deixarem a lista invarrível', () => {
    const { container } = card({ justifies: 'resultado' });

    const bloco = container.querySelector('details');

    expect(bloco).not.toBeNull();
    expect(bloco).not.toHaveAttribute('open');
    expect(screen.queryByText(/O prazo corre da ciência/)).not.toBeVisible();
  });

  it('é alcançável pelo teclado', async () => {
    const user = userEvent.setup();
    card({ justifies: 'resultado' });

    const resumo = screen.getByText('Por que esta decisão está aqui');

    await user.tab();
    while (document.activeElement !== resumo && document.activeElement !== document.body) {
      await user.tab();
    }

    expect(resumo).toHaveFocus();
  });

  it('abrir não recarrega a lista nem move o card', async () => {
    // jsdom does not toggle <details> from a key the way a browser does, so
    // the click is what can be asserted here; the keyboard reach is above.
    const user = userEvent.setup();
    const { container } = card({ justifies: 'resultado' });

    const antes = container.querySelectorAll('article').length;
    await user.click(screen.getByText('Por que esta decisão está aqui'));

    expect(container.querySelector('details')).toHaveAttribute('open');
    expect(screen.getByText(/O prazo corre da ciência/)).toBeVisible();
    // Opening is local to the card: nothing re-renders the list around it.
    expect(container.querySelectorAll('article')).toHaveLength(antes);
  });

  it('fica acima do link esticado, senão abri-la abriria a decisão', () => {
    const { container } = card({ justifies: 'resultado' });

    const link = container.querySelector('.decision-result-card__select');
    const bloco = container.querySelector('details');

    expect(link).not.toBeNull();
    expect(bloco).not.toBeNull();
    expect(bloco!.compareDocumentPosition(link!) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });
});
