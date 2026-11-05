/**
 * The thesis the court wrote, on the card and on the reading screen.
 *
 * Two things break quietly here. The card's whole surface is a stretched link
 * to the decision, so an expander inside it opens the decision instead of
 * itself unless it sits above. And an environment serving a publication older
 * than this build sends no thesis field at all.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

import { readThesis } from '../api/decisions';
import DecisionDetail from '../components/DecisionDetail';
import DecisionResultCard from '../components/DecisionResultCard';

const MATCH = {
  court: 'TJDFT',
  case_number: '0706021-73.2023.8.07.0001',
  judging_body: '7ª TURMA CÍVEL',
  reporting_judge: 'ROBSON BARBOSA DE AZEVEDO',
  decided_on: '2025-09-17',
  source_url: 'https://jurisdf.tjdft.jus.br/acordaos/32175b86',
  source_url_reachable: true,
  snippet: 'Ementa: DIREITO CIVIL. APELAÇÃO.',
};

const TESES = [
  'A cláusula de êxito é válida quando há obtenção de resultado útil ao contratante.',
  'A correção monetária incide desde a data do trânsito em julgado.',
];

// The justification only exists on a list that came from an indicator: it
// answers for a classification this tool inferred, and a plain search has
// none to answer for.
function card(thesis?: string[], justifies: 'resultado' | 'aderencia' = 'resultado') {
  return render(
    <MemoryRouter>
      <DecisionResultCard
        decision={{ ...MATCH, thesis, deliberation: null }}
        justifies={justifies}
        to="/decisions/tjdft-jurisdf/2044172"
      />
    </MemoryRouter>,
  );
}

describe('readThesis', () => {
  it('reads what the API sends', () => {
    expect(readThesis(TESES)).toEqual(TESES);
  });

  it('survives an environment that serves no thesis field', () => {
    expect(readThesis(undefined)).toEqual([]);
    expect(readThesis(null)).toEqual([]);
  });

  it('drops what is not a usable entry', () => {
    expect(readThesis(['Uma tese.', '', '   ', 7, null])).toEqual(['Uma tese.']);
  });

  it('refuses a shape it cannot iterate', () => {
    expect(readThesis('uma tese solta')).toEqual([]);
    expect(readThesis({ 0: 'uma tese' })).toEqual([]);
  });
});

describe('a tese no card da lista', () => {
  it('abre uma entrada por item que o tribunal numerou', async () => {
    card(TESES);

    await userEvent.click(screen.getByText('Por que esta decisão está aqui'));

    expect(screen.getByText(TESES[0])).toBeVisible();
    expect(screen.getByText(TESES[1])).toBeVisible();
  });

  it('diz de quem é o texto, para não confundir com o que inferimos', () => {
    card(TESES);

    expect(screen.getByText('Tese firmada pelo tribunal')).toBeInTheDocument();
  });

  it('começa fechado, para a lista continuar varrível', () => {
    const { container } = card(TESES);

    expect(container.querySelector('details')?.open).toBe(false);
  });

  it('diz que o tribunal não escreveu tese, em vez de sumir', () => {
    // 94,2% do acervo não traz tese escrita. Esconder a justificativa nesses
    // casos deixaria a classificação sem nada que respondesse por ela; o
    // trecho acima é a evidência, e esta linha diz isso.
    card([]);

    expect(screen.getByText('Por que esta decisão está aqui')).toBeInTheDocument();
    expect(screen.getByText(/O tribunal não escreveu tese/)).toBeInTheDocument();
  });

  it('não quebra quando a API não manda o campo', () => {
    card(undefined);

    expect(screen.getByText(/O tribunal não escreveu tese/)).toBeInTheDocument();
    expect(screen.getByText(/DIREITO CIVIL/)).toBeInTheDocument();
  });

  it('não aparece numa lista que não veio de indicador nenhum', () => {
    // A regra que o card marca: falha se alguém o ligar em tudo. Numa busca
    // comum não há classificação nossa por que responder.
    render(
      <MemoryRouter>
        <DecisionResultCard
          decision={{ ...MATCH, thesis: TESES, deliberation: null }}
          to="/decisions/tjdft-jurisdf/2044172"
        />
      </MemoryRouter>,
    );

    expect(screen.queryByText('Por que esta decisão está aqui')).not.toBeInTheDocument();
  });

  it('fica acima do link esticado, senão abrir a tese abriria a decisão', () => {
    const { container } = card(TESES);

    const expander = container.querySelector('.decision-result-card__thesis');
    const stretched = container.querySelector('.decision-result-card__select');

    expect(expander).not.toBeNull();
    expect(stretched).not.toBeNull();
    // The stylesheet lifts both the official link and this one over the
    // stretched link. The class is what carries that rule.
    expect(expander).toHaveClass('decision-result-card__thesis');
  });
});

describe('a tese no detalhe', () => {
  const DETALHE = {
    source: 'tjdft-jurisdf',
    identifier: '2044172',
    court: 'TJDFT',
    case_number: '0706021-73.2023.8.07.0001',
    judging_body: '7ª TURMA CÍVEL',
    reporting_judge: 'ROBSON BARBOSA DE AZEVEDO',
    decided_on: '2025-09-17',
    small_claims: false,
    source_url: 'https://jurisdf.tjdft.jus.br/acordaos/32175b86',
    source_url_reachable: true,
    class_code: 198,
    judged_on: '2025-09-17',
    published_on: '2025-09-23',
    summary: 'Ementa: DIREITO CIVIL. APELAÇÃO.',
    outcome: 'RECURSOS CONHECIDOS E DESPROVIDOS. UNÂNIME.',
    thesis: TESES,
    full_text_available: true,
    sections: null,
  };

  function detail(thesis: string[]) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ ...DETALHE, thesis }), { status: 200 })),
    );

    return render(
      <MemoryRouter>
        <DecisionDetail id="detalhe" source="tjdft-jurisdf" identifier="2044172" />
      </MemoryRouter>,
    );
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('mostra a tese aberta, sem exigir clique', async () => {
    detail(TESES);

    expect(await screen.findByText('Tese firmada pelo tribunal')).toBeInTheDocument();
    expect(screen.getByText(TESES[0])).toBeVisible();
  });

  it('não mostra a seção quando o tribunal não escreveu tese', async () => {
    detail([]);

    await screen.findByText(/DIREITO CIVIL/);
    expect(screen.queryByText('Tese firmada pelo tribunal')).not.toBeInTheDocument();
  });
});
