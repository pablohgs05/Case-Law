import { useState } from 'react';
import { Sparkle } from '@phosphor-icons/react';

import { SearchRequestError } from '../api/search';
import { identifyThesis, type IdentifiedThesis as Reading } from '../api/thesis';

/**
 * The thesis of a decision the court wrote none for, read when asked.
 *
 * Asked for, never automatic. The call costs the firm money and the collection
 * is a million decisions, so nothing happens until a person presses the
 * button — and once it has, the answer is kept on the server and the next
 * reader of the same decision pays nothing.
 *
 * What comes back is this tool's reading and is labelled as this tool's
 * reading, every time. It is shown with the passage of the ementa it was drawn
 * from, which the server found in the ementa before answering, so the reader
 * can check it against the text on the same screen rather than take it on
 * faith.
 */

type IdentifiedThesisProps = {
  source: string;
  identifier: string;
};

type State =
  | { kind: 'idle' }
  | { kind: 'reading' }
  | { kind: 'read'; reading: Reading }
  | { kind: 'failed'; message: string };

// Two refusals, two sentences. Collapsing them would tell a reader that the
// tool failed when in fact the decision has no thesis to find — which is
// the ordinary case for one that resolves only a procedural question.
const NO_THESIS =
  'Esta decisão não firma tese de direito material. É o caso de quem resolve apenas uma questão processual.';
const UNVERIFIED =
  'A ferramenta leu uma tese, mas não conseguiu apontá-la no texto da ementa. Por isso não mostra.';
const FAILED = 'Não foi possível ler a tese agora.';

// Same comparison the server makes before it accepts a quote: what counts
// is the words and their order, not the spacing or the accents.
function comparable(text: string): string {
  return text
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export default function IdentifiedThesis({ source, identifier }: IdentifiedThesisProps) {
  const [state, setState] = useState<State>({ kind: 'idle' });

  async function ask() {
    setState({ kind: 'reading' });

    try {
      setState({ kind: 'read', reading: await identifyThesis(source, identifier) });
    } catch (error) {
      setState({
        kind: 'failed',
        message: error instanceof SearchRequestError && error.detail ? error.detail : FAILED,
      });
    }
  }

  if (state.kind === 'idle' || state.kind === 'reading') {
    return (
      <button
        type="button"
        className="decision-result-card__read-thesis"
        onClick={() => void ask()}
        disabled={state.kind === 'reading'}
      >
        <Sparkle size={14} aria-hidden="true" />
        {state.kind === 'reading' ? 'Lendo a ementa…' : 'Identificar a tese com IA'}
      </button>
    );
  }

  if (state.kind === 'failed') {
    return (
      <p className="decision-result-card__thesis-reading" role="status">
        {state.message}
      </p>
    );
  }

  const { outcome, thesis, passage } = state.reading;

  // The instruction asks for the court's own words where they exist, so a good
  // reading often quotes the sentence it is drawn from — and the two fields
  // come back the same passage. Printing it twice under two headings would
  // make the tool look like it had found two things.
  const quotesItself = Boolean(passage) && comparable(thesis ?? '') === comparable(passage ?? '');

  if (outcome !== 'read' || !thesis) {
    return (
      <p className="decision-result-card__thesis-reading" role="status">
        {outcome === 'none' ? NO_THESIS : UNVERIFIED}
      </p>
    );
  }

  return (
    <div className="decision-result-card__read" role="status">
      {/* Said before the thesis, not after. A reader who skims has to meet the
          attribution before the sentence, because the sentence reads like
          something a court wrote. */}
      <p className="decision-result-card__thesis-origin">
        Tese identificada por IA — não é texto do tribunal
      </p>
      <p className="decision-result-card__read-thesis-text">{thesis}</p>
      {passage && !quotesItself && (
        <>
          <p className="decision-result-card__thesis-origin">
            Trecho da ementa que sustenta esta leitura
          </p>
          <blockquote className="decision-result-card__read-passage">{passage}</blockquote>
        </>
      )}
      {quotesItself && (
        <p className="decision-result-card__read-passage">
          Copiado da ementa, palavra por palavra.
        </p>
      )}
    </div>
  );
}
