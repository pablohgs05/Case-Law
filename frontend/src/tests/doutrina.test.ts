import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getRelatedDoctrine,
  readDoctrineResults,
  readSuggestion,
  readSuggestions,
  readWork,
  searchDoctrine,
} from '../api/doctrine';

// O mesmo que `filterRequests` faz, e pelo mesmo motivo: `VITE_API_URL` vem do
// `.env`, que não é versionado. Sem isto a suíte passa na máquina de quem tem
// o arquivo e quebra no CI, que não tem.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://localhost:8000',
  assertApiConfiguration: () => undefined,
}));

/**
 * Reading the doctrine answers defensively.
 *
 * This client sits in front of a collection that answers nothing for four
 * decisions in five, so an empty list has to be an ordinary answer. And every
 * field may be missing: the API is read as data, never trusted to have the
 * shape the types promise.
 */

const WORK = {
  repository: 'bdjur',
  identifier: 'oai:bdjur.stj.jus.br:2011/98958',
  title: 'A avaliação do regime jurídico da litigância de má-fé',
  alternative_titles: ['Evaluation of the Portuguese framework'],
  authors: ['Gouveia, Mariana'],
  subjects: ['Litigância de má-fé'],
  type: 'Artigo',
  date: '2014',
  year: 2014,
  language: 'pt-br',
  publication: 'Revista de Processo',
  reference: 'Revista de Processo, v. 39, 2014.',
  url: 'https://bdjur.stj.jus.br/handle/2011/98958',
};

function answer(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

beforeEach(() => {
  vi.stubGlobal('fetch', answer({ results: [] }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('a leitura de uma obra', () => {
  it('aceita o registro completo', () => {
    expect(readWork(WORK)).toEqual(WORK);
  });

  it('descarta a obra sem título ou sem link', () => {
    // Sem título a tela mostra uma linha em branco com link; sem link o leitor
    // não alcança a obra. Nos dois casos não há o que apresentar.
    expect(readWork({ ...WORK, title: '   ' })).toBeNull();
    expect(readWork({ ...WORK, url: undefined })).toBeNull();
  });

  it('devolve lista vazia onde a resposta não trouxe lista', () => {
    // 45% da coleção não tem assunto nenhum, e a tela não deve precisar
    // distinguir ausente de vazio.
    const obra = readWork({ ...WORK, subjects: null, authors: 'Gouveia' });

    expect(obra?.subjects).toEqual([]);
    expect(obra?.authors).toEqual([]);
  });

  it('não inventa data a partir do ano, nem ano a partir da data', () => {
    const obra = readWork({ ...WORK, date: '1997/1998', year: null });

    expect(obra?.date).toBe('1997/1998');
    expect(obra?.year).toBeNull();
  });
});

describe('a leitura de uma sugestão', () => {
  it('mantém os termos que casaram', () => {
    const sugestao = readSuggestion({ ...WORK, score: 9.3, matched_on: ['litiganc', 'ma-f'] });

    expect(sugestao?.matched_on).toEqual(['litiganc', 'ma-f']);
    expect(sugestao?.score).toBe(9.3);
  });

  it('sobrevive a uma resposta sem nota e sem termos', () => {
    const sugestao = readSuggestion(WORK);

    expect(sugestao?.score).toBeNull();
    expect(sugestao?.matched_on).toEqual([]);
  });

  it('ignora a sugestão que não dá para apresentar', () => {
    const lidas = readSuggestions({
      results: [{ ...WORK, score: 9.3 }, { score: 20 }, null],
    });

    expect(lidas).toHaveLength(1);
  });

  it('lê lista vazia de um corpo sem results', () => {
    expect(readSuggestions({})).toEqual([]);
    expect(readSuggestions(null)).toEqual([]);
  });
});

describe('a leitura da busca', () => {
  it('lê o total e a página', () => {
    const corpo = readDoctrineResults({ total: 12, page: 2, page_size: 20, results: [WORK] });

    expect(corpo.total).toBe(12);
    expect(corpo.page).toBe(2);
    expect(corpo.results).toHaveLength(1);
  });

  it('não lê total negativo como total', () => {
    expect(readDoctrineResults({ total: -1, results: [] }).total).toBeNull();
  });
});

describe('as chamadas', () => {
  it('pede a doutrina de uma decisão com o identificador escapado', async () => {
    const fetchMock = answer({ results: [{ ...WORK, score: 9.3, matched_on: ['ma-f'] }] });
    vi.stubGlobal('fetch', fetchMock);

    const sugestoes = await getRelatedDoctrine('stj-espelhos', '0712598-03/2019');

    const [chamada] = fetchMock.mock.calls[0] as [string];
    expect(chamada).toContain('/decisions/stj-espelhos/0712598-03%2F2019/doctrine');
    expect(sugestoes).toHaveLength(1);
  });

  it('leva o limite quando pedido', async () => {
    const fetchMock = answer({ results: [] });
    vi.stubGlobal('fetch', fetchMock);

    await getRelatedDoctrine('stj-espelhos', '123', { limit: 3 });

    expect((fetchMock.mock.calls[0] as [string])[0]).toContain('limit=3');
  });

  it('decisão sem doutrina devolve lista vazia, não erro', async () => {
    vi.stubGlobal('fetch', answer({ results: [] }));

    await expect(getRelatedDoctrine('stj-espelhos', '123')).resolves.toEqual([]);
  });

  it('propaga a falha com o detalhe da API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'A base não está respondendo agora.' }),
      }),
    );

    await expect(getRelatedDoctrine('stj-espelhos', '123')).rejects.toMatchObject({
      status: 503,
    });
  });

  it('busca na doutrina levando termo, página e tamanho', async () => {
    const fetchMock = answer({ total: 0, page: 1, page_size: 5, results: [] });
    vi.stubGlobal('fetch', fetchMock);

    await searchDoctrine('litigância de má-fé', { page: 2, pageSize: 5 });

    const [chamada] = fetchMock.mock.calls[0] as [string];
    expect(chamada).toContain('q=litig%C3%A2ncia+de+m%C3%A1-f%C3%A9');
    expect(chamada).toContain('page=2');
    expect(chamada).toContain('page_size=5');
  });
});
