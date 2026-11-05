import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { SearchDecisionMatch } from '../api/search';
import DecisionResultCard from '../components/DecisionResultCard';

/**
 * Asking this tool to read a thesis the court did not write.
 *
 * Two things matter more than the happy path. The call costs the firm money,
 * so it must not happen because a card was rendered. And what comes back is
 * ours, not the court's, so it must never appear under the court's name.
 */

vi.mock('../api/client', () => ({
  // A string, as the real module exports it. A function here would pass
  // while the real call fails to compile.
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

const identify = vi.fn();

vi.mock('../api/thesis', () => ({
  identifyThesis: (source: string, identifier: string) => identify(source, identifier),
}));

const WITHOUT_THESIS: SearchDecisionMatch = {
  source: 'stj-espelhos',
  identifier: '1501855',
  court: 'STJ',
  case_number: '1501855',
  judging_body: 'SEXTA TURMA',
  reporting_judge: 'SEBASTIÃO REIS JÚNIOR',
  decided_on: '2017-05-16',
  small_claims: null,
  source_url: 'https://processo.stj.jus.br/1501855',
  source_url_reachable: true,
  source_url_shared: false,
  deliberation: 'maioria',
  snippet: 'RECURSO ESPECIAL. PENAL. Negar provimento.',
  thesis: [],
};

function card(decision: SearchDecisionMatch = WITHOUT_THESIS) {
  return render(
    <MemoryRouter>
      <DecisionResultCard decision={decision} justifies="resultado" />
    </MemoryRouter>,
  );
}

async function openJustification() {
  await userEvent.click(screen.getByText('Por que esta decisão está aqui'));
}

describe('tese identificada sob demanda', () => {
  beforeEach(() => {
    identify.mockReset();
  });

  it('não chama a API só por renderizar o card', () => {
    card();

    expect(identify).not.toHaveBeenCalled();
  });

  it('não chama a API só por abrir a justificativa', async () => {
    card();

    await openJustification();

    expect(identify).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Identificar a tese com IA/ })).toBeVisible();
  });

  it('pede a leitura quando a pessoa aperta, e só então', async () => {
    identify.mockResolvedValue({
      outcome: 'read',
      thesis: 'A pretensão de reexame de prova não enseja recurso especial.',
      passage: 'SÚMULA 7/STJ. MATÉRIA FÁTICO-PROBATÓRIA.',
      model: 'gemini-3.5-flash',
      cached: false,
    });
    card();
    await openJustification();

    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    await waitFor(() => expect(identify).toHaveBeenCalledWith('stj-espelhos', '1501855'));
    expect(identify).toHaveBeenCalledTimes(1);
  });

  it('diz que a tese é da ferramenta antes de mostrar a tese', async () => {
    identify.mockResolvedValue({
      outcome: 'read',
      thesis: 'A pretensão de reexame de prova não enseja recurso especial.',
      passage: 'SÚMULA 7/STJ. MATÉRIA FÁTICO-PROBATÓRIA.',
      model: 'gemini-3.5-flash',
      cached: false,
    });
    card();
    await openJustification();
    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    const aviso = await screen.findByText(/não é texto do tribunal/i);
    const tese = await screen.findByText(/A pretensão de reexame de prova/);

    // The attribution has to come first in the document, not merely be present:
    // a reader who skims meets the sentence before the label otherwise.
    expect(aviso.compareDocumentPosition(tese) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('mostra o trecho da ementa que sustenta a leitura', async () => {
    identify.mockResolvedValue({
      outcome: 'read',
      thesis: 'A pretensão de reexame de prova não enseja recurso especial.',
      passage: 'SÚMULA 7/STJ. MATÉRIA FÁTICO-PROBATÓRIA.',
      model: 'gemini-3.5-flash',
      cached: false,
    });
    card();
    await openJustification();
    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    expect(await screen.findByText('SÚMULA 7/STJ. MATÉRIA FÁTICO-PROBATÓRIA.')).toBeVisible();
  });

  it('diz que não conseguiu confirmar, em vez de ficar em silêncio', async () => {
    identify.mockResolvedValue({
      outcome: 'unverified',
      thesis: null,
      passage: null,
      model: null,
      cached: false,
    });
    card();
    await openJustification();

    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    expect(await screen.findByText(/não conseguiu apontá-la no texto da ementa/i)).toBeVisible();
  });

  it('repete o que o servidor disse quando a leitura falha', async () => {
    const { SearchRequestError } = await import('../api/search');
    identify.mockRejectedValue(
      new SearchRequestError(501, 'A leitura automática de tese não está configurada.'),
    );
    card();
    await openJustification();

    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    expect(await screen.findByText(/não está configurada/)).toBeVisible();
  });

  it('não repete o mesmo texto sob dois títulos', async () => {
    // Happened on the first real reading: the instruction asks for the court's
    // own words, so a good answer often quotes the sentence it came from and
    // both fields come back the same passage.
    const mesmo =
      'Em eventos patrocinados pelo Poder Público, a administração responde pela omissão.';
    identify.mockResolvedValue({
      outcome: 'read',
      thesis: mesmo,
      passage: mesmo,
      model: 'gemini-2.5-flash',
      cached: false,
    });
    card();
    await openJustification();

    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    expect(await screen.findAllByText(mesmo)).toHaveLength(1);
    expect(screen.queryByText(/Trecho da ementa que sustenta/)).toBeNull();
    expect(screen.getByText(/Copiado da ementa, palavra por palavra/)).toBeVisible();
  });

  it('separa "não há tese" de "não consegui confirmar"', async () => {
    // Medido em 16 decisões reais: 3 não firmam tese de direito material e
    // nenhuma teve trecho inventado. Tratar as duas como a mesma falha
    // culparia a ferramenta por um fato da decisão.
    identify.mockResolvedValue({
      outcome: 'none',
      thesis: null,
      passage: null,
      model: 'gemini-3.5-flash-lite',
      cached: false,
    });
    card();
    await openJustification();

    await userEvent.click(screen.getByRole('button', { name: /Identificar a tese com IA/ }));

    expect(await screen.findByText(/não firma tese de direito material/i)).toBeVisible();
    expect(screen.queryByText(/não conseguiu apontá-la/i)).toBeNull();
  });

  it('não oferece o botão quando o tribunal escreveu a tese', async () => {
    card({ ...WITHOUT_THESIS, thesis: ['A tese que o tribunal firmou.'] });

    await openJustification();

    expect(screen.queryByRole('button', { name: /Identificar a tese com IA/ })).toBeNull();
    expect(screen.getByText('Tese firmada pelo tribunal')).toBeVisible();
  });
});
