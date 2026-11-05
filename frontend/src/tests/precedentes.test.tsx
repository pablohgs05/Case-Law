import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AdherenceShare, CitedPrecedent, MostCited } from '../api/precedents';
import AdherencePanel from '../components/AdherencePanel';
import CitedPrecedents from '../components/CitedPrecedents';
import type { AdherenceState, MostCitedState } from '../components/precedentFormat';

/**
 * The two promises this screen makes.
 *
 * In the detail, that a reader can tell what the court wrote from what this
 * tool inferred — only the first can go in a petition. In the panorama, that
 * all three denominators are on screen without anyone clicking: most decisions
 * cite nothing, so a share of the citations reads as a share of the cut unless
 * the other two are there beside it.
 */

const precedent = (over: Partial<CitedPrecedent> = {}): CitedPrecedent => ({
  court: 'STJ',
  kind: 'sumula',
  number: 7,
  text: 'A pretensão de simples reexame de prova não enseja recurso especial.',
  status: null,
  settled_on: null,
  snippet: 'reexame de provas. incidencia da sumula n. 7 do stj.',
  adherence: 'seguiu',
  resolved: true,
  court_stated: true,
  ...over,
});

const share = (over: Partial<AdherenceShare> = {}): AdherenceShare => ({
  decisions: 1788,
  citing: 497,
  links: 1715,
  determined: 1301,
  undetermined: 414,
  adherences: [
    { adherence: 'seguiu', links: 913, decisions: 870, share: 70.2 },
    { adherence: 'afastou', links: 300, decisions: 290, share: 23.1 },
    { adherence: 'distinguiu', links: 60, decisions: 58, share: 4.6 },
    { adherence: 'mencionou', links: 28, decisions: 27, share: 2.2 },
  ],
  ...over,
});

const loaded = (over: Partial<AdherenceShare> = {}): AdherenceState => ({
  status: 'loaded',
  adherence: share(over),
});

const ranked = (precedents: MostCited[] = []): MostCitedState => ({
  status: 'loaded',
  precedents,
});

function showDetail(precedents: CitedPrecedent[]) {
  render(<CitedPrecedents precedents={precedents} headingId="precedentes" />);
}

function showPanel(adherence: AdherenceState, mostCited: MostCitedState = ranked()) {
  render(<AdherencePanel adherence={adherence} mostCited={mostCited} onRetry={() => {}} />);
}

describe('the precedents a decision cites', () => {
  it('separates what the court wrote from what the tool read', () => {
    showDetail([precedent()]);

    const block = screen.getByRole('article', { name: 'Súmula 7 do STJ' });

    // The quotation is the court's and carries no hedging.
    expect(within(block).getByText(/A pretensão de simples reexame de prova/)).toBeInTheDocument();

    // The inference is named as one, in words, not only by placement or colour.
    expect(within(block).getByText(/Leitura automática desta ferramenta/)).toBeInTheDocument();
    expect(within(block).getByText('Seguiu')).toBeInTheDocument();
  });

  it('says what the label means rather than leaving the verb to be guessed', () => {
    showDetail([precedent({ adherence: 'mencionou' })]);

    expect(screen.getByText('Apenas mencionou')).toBeInTheDocument();
    expect(screen.getByText(/sem juízo de aplicação/)).toBeInTheDocument();
  });

  it('marks a cancelled precedent instead of mentioning it in passing', () => {
    showDetail([precedent({ status: 'cancelada' })]);

    const warning = screen.getByText(/Precedente cancelada/);

    expect(warning).toBeInTheDocument();
    expect(warning.textContent).toMatch(/não vale hoje/);
  });

  it('never reads an unknown status as current', () => {
    showDetail([precedent({ status: null })]);

    // Said once for the section rather than on every block: the catalogue
    // carries no status for any reconstructed súmula, so a warning repeated
    // on all of them would stop being read and would compete with the one
    // that marks a cancelled precedent.
    expect(screen.getByText(/confira na fonte oficial antes de citar/)).toBeInTheDocument();
    expect(screen.queryByText(/em vigor/i)).toBeNull();
    expect(screen.queryByText(/^Situação:/)).toBeNull();
  });

  it('shows a citation the catalogue has no text for, instead of hiding it', () => {
    showDetail([precedent({ number: 999, text: null, resolved: false })]);

    expect(screen.getByRole('article', { name: 'Súmula 999 do STJ' })).toBeInTheDocument();
    expect(screen.getByText(/A citação é real/)).toBeInTheDocument();
  });

  it('offers the official source, which is what a petition cites', () => {
    showDetail([precedent({ court: 'STF', number: 284 })]);

    const link = screen.getByRole('link', { name: /Fonte oficial de Súmula 284 do STF/ });

    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('href')).toContain('stf.jus.br');
  });

  it('does not name a court the acórdão never named', () => {
    showDetail([precedent({ kind: 'tema', number: 793, court_stated: false, resolved: false })]);

    // Both courts have a Tema 793, saying different things. Naming one would
    // be a claim the decision never made — it cost 11,252 citations the wrong
    // enunciado before the court was read from the text.
    expect(screen.getByRole('article', { name: 'Tema 793' })).toBeInTheDocument();
    expect(screen.queryByText(/Tema 793 do STJ/)).toBeNull();
    expect(screen.getByText(/não disse de qual corte é este tema/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Fonte oficial/ })).toBeNull();
  });

  it('renders nothing at all when the decision cites none', () => {
    const { container } = render(<CitedPrecedents precedents={[]} headingId="precedentes" />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe('the adherence of a cut', () => {
  it('puts all three denominators on screen without any interaction', () => {
    showPanel(loaded());

    expect(screen.getByText('1.788')).toBeInTheDocument();
    expect(screen.getByText(/decisões no recorte/)).toBeInTheDocument();
    expect(screen.getByText('497')).toBeInTheDocument();
    expect(screen.getByText('citam algum precedente')).toBeInTheDocument();
    expect(screen.getByText('1.301')).toBeInTheDocument();
    expect(screen.getByText(/citações com uso determinado/)).toBeInTheDocument();
  });

  it('reports the citations it could not settle rather than dropping them', () => {
    showPanel(loaded());

    expect(screen.getByText(/414 indeterminadas/)).toBeInTheDocument();
  });

  it('reads every slice of the chart as text beside it', () => {
    showPanel(loaded());

    for (const [label, value] of [
      ['Seguiu', '70,2%'],
      ['Afastou', '23,1%'],
      ['Distinguiu', '4,6%'],
      ['Apenas mencionou', '2,2%'],
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
      expect(screen.getByText(value)).toBeInTheDocument();
    }
  });

  it('hides the drawing from assistive technology, which reads the list', () => {
    const { container } = render(
      <AdherencePanel adherence={loaded()} mostCited={ranked()} onRetry={() => {}} />,
    );

    const chart = container.querySelector('.outcome-chart');

    expect(chart).toHaveAttribute('aria-hidden', 'true');
  });

  it('tells a cut that cites nothing apart from one it could not read', () => {
    showPanel(loaded({ citing: 0, links: 0, determined: 0, undetermined: 0, adherences: [] }));

    expect(
      screen.getByText(/Nenhuma decisão deste recorte cita súmula ou tema/),
    ).toBeInTheDocument();
  });

  it('tells a cut whose wording settled nothing apart from one that cites nothing', () => {
    showPanel(loaded({ determined: 0, undetermined: 1715, adherences: [] }));

    expect(screen.getByText(/não permitiu determinar como os usaram/)).toBeInTheDocument();
  });

  it('says it is loading rather than showing a number it does not have', () => {
    showPanel({ status: 'loading' });

    expect(screen.getByText('Carregando a aderência aos precedentes')).toBeInTheDocument();
    expect(screen.queryByText(/citações com uso determinado/)).toBeNull();
  });

  it('offers a way back from a failure, as an alert', () => {
    showPanel({ status: 'failed', message: 'A busca não respondeu.' });

    expect(screen.getByRole('alert')).toHaveTextContent('A busca não respondeu.');
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
  });
});

describe('the most cited precedents', () => {
  it('ranks them with the count of each', () => {
    showPanel(
      loaded(),
      ranked([
        {
          court: 'STJ',
          kind: 'sumula',
          number: 7,
          text: 'enunciado',
          citations: 612,
          decisions: 598,
        },
      ]),
    );

    expect(screen.getByText('Súmula 7 do STJ')).toBeInTheDocument();
    expect(screen.getByText(/612 citações/)).toBeInTheDocument();
    expect(screen.getByText(/598 decisões/)).toBeInTheDocument();
  });

  it('keeps one the catalogue never carried', () => {
    showPanel(
      loaded(),
      ranked([
        { court: 'STJ', kind: 'sumula', number: 999, text: null, citations: 3, decisions: 3 },
      ]),
    );

    expect(screen.getByText('Súmula 999 do STJ')).toBeInTheDocument();
    expect(screen.getByText('Enunciado fora do acervo.')).toBeInTheDocument();
  });

  it('says so when the cut cites nothing', () => {
    showPanel(loaded(), ranked([]));

    expect(screen.getByText(/Nenhum precedente citado/)).toBeInTheDocument();
  });
});
