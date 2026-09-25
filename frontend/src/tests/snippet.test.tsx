import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import DecisionResultCard from '../components/DecisionResultCard';

const base = {
  court: 'TJDFT',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: '3ª TURMA CÍVEL',
  reporting_judge: 'JOÃO EGMONT',
  decided_on: '2026-06-11',
  source_url: 'https://jurisdf.tjdft.jus.br/detalhes/2119440',
  source_url_reachable: true,
  snippet: '',
};

function renderSnippet(snippet: string) {
  const { container } = render(<DecisionResultCard decision={{ ...base, snippet }} />);
  return container.querySelector('.decision-result-card__snippet') as HTMLElement;
}

function tagsInside(snippet: HTMLElement) {
  return [...snippet.querySelectorAll('*')].map((node) => node.tagName);
}

describe('the matched passage', () => {
  it('marks the term the reader searched for', () => {
    renderSnippet('Contrato de transporte. <mark>Dano moral</mark> configurado.');

    const marks = screen.getAllByText('Dano moral');
    expect(marks).toHaveLength(1);
    expect(marks[0].tagName).toBe('MARK');
  });

  it('marks every occurrence, not only the first', () => {
    const snippet = renderSnippet(
      '<mark>prescrição</mark> intercorrente e a <mark>prescrição</mark> quinquenal',
    );

    expect(snippet.querySelectorAll('mark')).toHaveLength(2);
  });

  it('keeps the words around the match', () => {
    const snippet = renderSnippet('Contrato de transporte. <mark>Dano moral</mark> configurado.');

    expect(snippet.textContent).toBe('Contrato de transporte. Dano moral configurado.');
  });

  it('marks an exact phrase as one piece', () => {
    const snippet = renderSnippet('Houve <mark>dano moral</mark> no caso.');
    const marks = snippet.querySelectorAll('mark');

    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe('dano moral');
  });

  it('shows the opening of the ementa when nothing matched literally', () => {
    const snippet = renderSnippet('PROCESSUAL CIVIL. EXECUÇÃO FISCAL. Apelação desprovida.');

    expect(snippet.querySelectorAll('mark')).toHaveLength(0);
    expect(snippet.textContent).toContain('EXECUÇÃO FISCAL');
  });

  it('says so when there is no passage at all', () => {
    expect(renderSnippet('').textContent).toBe('Trecho indisponível.');
  });
});

describe('what the court wrote is never treated as markup', () => {
  it('renders a script tag as text, not as a script', () => {
    const snippet = renderSnippet('Cláusula <script>alert(1)</script> abusiva.');

    expect(tagsInside(snippet)).toEqual([]);
    expect(snippet.textContent).toBe('Cláusula alert(1) abusiva.');
  });

  it('drops an image that would fire on error', () => {
    const snippet = renderSnippet('Valor <img src="x" onerror="alert(1)"> devido.');

    expect(tagsInside(snippet)).toEqual([]);
    expect(snippet.textContent).toBe('Valor  devido.');
  });

  it('renders an anchor as text, so no link is injected into the card', () => {
    const snippet = renderSnippet('Veja <a href="https://exemplo.invalido">aqui</a>.');

    expect(tagsInside(snippet)).toEqual([]);
    expect(snippet.textContent).toBe('Veja aqui.');
  });

  it('keeps an ampersand the court actually wrote', () => {
    const snippet = renderSnippet('Empresa <mark>Silva</mark> &amp; Souza Ltda.');

    expect(snippet.textContent).toBe('Empresa Silva & Souza Ltda.');
  });

  it('marks only mark, whatever else the text carries', () => {
    const snippet = renderSnippet('<b>Negrito</b> e <mark>destaque</mark> e <i>itálico</i>.');

    expect(tagsInside(snippet)).toEqual(['MARK']);
    expect(snippet.textContent).toBe('Negrito e destaque e itálico.');
  });
});
