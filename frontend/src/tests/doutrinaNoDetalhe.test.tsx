import { render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Suggestion } from '../api/doctrine';
import { commonGround, workKind } from '../components/doctrineFormat';
import RelatedDoctrine from '../components/RelatedDoctrine';

// O mesmo que `filterRequests` faz, e pelo mesmo motivo: `VITE_API_URL` vem do
// `.env`, que não é versionado. Sem isto a suíte passa na máquina de quem tem
// o arquivo e quebra no CI, que não tem.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://localhost:8000',
  assertApiConfiguration: () => undefined,
}));

/**
 * The doctrine block, and the promise it has to keep.
 *
 * Three kinds of claim share the detail screen: the court's own words, this
 * tool's reading of them, and scholarship by other people. The third is the
 * only one that lives somewhere else, and a reader who confuses it with the
 * first could quote a stranger as if it were the court.
 *
 * Its four states also have to read apart. "Nothing found" is an answer and
 * "unavailable" is a failure, and writing them alike would turn the normal
 * case — four decisions in five — into the look of a broken screen.
 */

const WORK: Suggestion = {
  repository: 'bdjur',
  identifier: 'oai:bdjur.stj.jus.br:2011/92171',
  title: 'Quae sunt Cesaris, Cesari: a imunidade tributária dos templos de qualquer culto',
  alternative_titles: [],
  authors: ['Bossi, Pedro Pimenta'],
  subjects: ['Imunidade tributária, aspectos constitucionais', 'Templo', 'Associação religiosa'],
  type: 'Artigo',
  date: '2015',
  year: 2015,
  language: 'pt-br',
  publication: 'Escola da Magistratura do TRF da 4ª região',
  reference: 'Revista de Doutrina da 4ª Região, n. 65, abr. 2015.',
  url: 'https://bdjur.stj.jus.br/handle/2011/92171',
  score: 43.71,
  matched_on: ['templ', 'cult', 'religi', 'imun', 'tribut'],
};

function answering(body: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 503,
    json: async () => body,
  });
}

function block() {
  return render(<RelatedDoctrine source="stj-espelhos" identifier="123" headingId="doutrina" />);
}

beforeEach(() => {
  vi.stubGlobal('fetch', answering({ results: [] }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('os quatro estados', () => {
  it('carregando diz que está procurando', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    block();

    expect(screen.getByRole('status')).toHaveTextContent(/Procurando doutrina/);
  });

  it('com sugestões mostra cada obra', async () => {
    vi.stubGlobal('fetch', answering({ results: [WORK] }));
    block();

    expect(await screen.findByText(WORK.title)).toBeInTheDocument();
  });

  it('nenhuma encontrada é resposta, e diz por quê', async () => {
    block();

    const texto = await screen.findByText(/Nenhuma doutrina relacionada/);

    expect(texto).toBeInTheDocument();
    expect(texto).toHaveTextContent(/quatro decisões em cada cinco/);
    // Uma resposta não se anuncia como falha.
    expect(screen.queryByText(/Não foi possível consultar/)).not.toBeInTheDocument();
  });

  it('indisponível é falha, e não se parece com a resposta vazia', async () => {
    vi.stubGlobal('fetch', answering({ detail: 'A base não responde.' }, false));
    block();

    const falha = await screen.findByText(/Não foi possível consultar a doutrina/);

    expect(falha).toBeInTheDocument();
    expect(screen.queryByText(/Nenhuma doutrina relacionada/)).not.toBeInTheDocument();
  });

  it('a falha diz que a decisão continua inteira', async () => {
    // A regra de degradação, escrita na tela e não só no backend: quem lê
    // precisa saber que perdeu este bloco e nada mais.
    vi.stubGlobal('fetch', answering({}, false));
    block();

    expect(await screen.findByText(/A decisão acima está completa/)).toBeInTheDocument();
  });
});

describe('a procedência', () => {
  it('diz que a doutrina é de terceiros e fica no acervo de origem', async () => {
    vi.stubGlobal('fetch', answering({ results: [WORK] }));
    block();

    await screen.findByText(WORK.title);

    expect(screen.getByText(/Publicada por terceiros/)).toBeInTheDocument();
    expect(screen.getByText(/não por este tribunal nem por esta ferramenta/)).toBeInTheDocument();
  });

  it('todo título é o link para o repositório de origem', async () => {
    vi.stubGlobal('fetch', answering({ results: [WORK] }));
    block();

    const link = await screen.findByRole('link', { name: new RegExp(WORK.title.slice(0, 30)) });

    expect(link).toHaveAttribute('href', WORK.url);
    expect(link).toHaveAttribute('target', '_blank');
    // Sem isto a aba aberta pode mexer na nossa.
    expect(link.getAttribute('rel')).toContain('noopener');
  });

  it('não traz texto de obra além do que o metadado dá', async () => {
    vi.stubGlobal('fetch', answering({ results: [WORK] }));
    const { container } = block();

    await screen.findByText(WORK.title);

    // O card mostra título, autoria, tipo/ano, onde saiu e o motivo. Nada de
    // resumo, nada de corpo do artigo.
    const card = container.querySelector('.work');
    expect(card?.textContent).not.toContain('Resumo');
    expect(card?.querySelectorAll('p')).toHaveLength(3);
  });
});

describe('o motivo do casamento', () => {
  it('aparece em cada sugestão, em palavras e não em radicais', async () => {
    vi.stubGlobal('fetch', answering({ results: [WORK] }));
    const { container } = block();

    await screen.findByText(WORK.title);
    const card = container.querySelector('.work');

    expect(within(card as HTMLElement).getByText(/Assuntos em comum/)).toBeInTheDocument();
    expect(card?.textContent).toContain('Imunidade tributária, aspectos constitucionais');
    // Separados por ponto médio, porque o assunto catalogado já tem vírgula
    // dentro dele e duas vírgulas seguidas viram uma linha só.
    expect(card?.textContent).toContain(' · Templo');
    // O radical é o registro do casamento, não o que se mostra ao leitor: o
    // que falha aqui é alguém renderizar `matched_on` direto.
    expect(card?.textContent).not.toContain(WORK.matched_on.join(', '));
    expect(card?.textContent).not.toContain('templ,');
  });

  it('cai no título quando a obra não tem assunto nenhum', () => {
    // 45% da coleção não traz assunto. Sem esta queda o motivo some justo
    // onde o leitor mais precisa dele.
    const semAssunto = { ...WORK, subjects: [] };

    expect(commonGround(semAssunto)).toEqual({
      kind: 'words',
      items: ['imunidade', 'tributária', 'templos', 'culto'],
    });
  });

  it('casa o radical com a palavra acentuada que o gerou', () => {
    const obra = {
      ...WORK,
      subjects: ['Litigância de má-fé', 'Constituição, interpretação'],
      matched_on: ['litiganc', 'constituica'],
    };

    expect(commonGround(obra)).toEqual({
      kind: 'subjects',
      items: ['Litigância de má-fé', 'Constituição, interpretação'],
    });
  });

  it('não mostra a notação de catálogo como motivo', () => {
    // 37 obras trazem assunto como "Brasil. [Lei n. 11.340, de 7 de agosto de
    // 2006]": é registro de autoridade, não tema, e na tela lê-se como ruído
    // no lugar onde deveria estar a razão da sugestão.
    const obra = {
      ...WORK,
      subjects: ['Brasil. [Constituição (1988), Artigo n. 150]', 'Templo'],
      matched_on: ['constituica', 'templ'],
    };

    expect(commonGround(obra)).toEqual({ kind: 'subjects', items: ['Templo'] });
  });

  it('cai no título quando só sobrava notação de catálogo', () => {
    const obra = {
      ...WORK,
      subjects: ['Brasil. [Constituição (1988), Artigo n. 150]'],
      matched_on: ['constituica'],
    };

    expect(commonGround(obra).kind).not.toBe('subjects');
  });

  it('mostra no máximo três assuntos, para caber numa olhada', async () => {
    const quatro = {
      ...WORK,
      subjects: ['Imunidade tributária', 'Templo', 'Culto religioso', 'Tributo municipal'],
      matched_on: ['imun', 'templ', 'religi', 'tribut'],
    };
    vi.stubGlobal('fetch', answering({ results: [quatro] }));
    const { container } = block();

    await screen.findByText(WORK.title);

    const motivo = container.querySelector('.work__ground')?.textContent ?? '';
    expect(motivo).toContain('Imunidade tributária');
    expect(motivo).not.toContain('Tributo municipal');
  });

  it('não promete motivo quando não há termo nenhum', () => {
    expect(commonGround({ ...WORK, matched_on: [] })).toEqual({ kind: 'none' });
  });

  it('o tipo e o ano andam juntos, e cada um sobrevive sozinho', () => {
    expect(workKind({ type: 'Artigo', date: '2015' })).toBe('Artigo, 2015');
    expect(workKind({ type: null, date: '1997/1998' })).toBe('1997/1998');
    expect(workKind({ type: null, date: null })).toBeNull();
  });
});

describe('a lista', () => {
  it('não quebra com obra sem autoria nem publicação', async () => {
    vi.stubGlobal(
      'fetch',
      answering({ results: [{ ...WORK, authors: [], publication: null, type: null, date: null }] }),
    );
    const { container } = block();

    await screen.findByText(WORK.title);

    expect(container.querySelectorAll('.work')).toHaveLength(1);
  });

  it('abandona a resposta que chega depois de trocar de decisão', async () => {
    const lenta = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', lenta);

    const { unmount } = block();
    unmount();

    await waitFor(() => expect(lenta).toHaveBeenCalled());
  });
});
