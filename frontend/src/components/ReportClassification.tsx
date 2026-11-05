import { useId, useState, type FormEvent } from 'react';
import { Flag } from '@phosphor-icons/react';

import {
  CONTESTED_LABELS,
  MAX_REPORT_LENGTH,
  ReportError,
  reportClassification,
  type ContestedInformation,
} from '../api/reports';

type ReportClassificationProps = {
  decision: { source: string; identifier: string };
  // The reading the block was justifying, chosen first: it is the one the
  // reader was looking at when they disagreed.
  contested: ContestedInformation;
};

type State =
  | { kind: 'closed' }
  | { kind: 'writing'; failure: string | null }
  | { kind: 'sending' }
  | { kind: 'received'; message: string };

const ORDER: ContestedInformation[] = ['resultado', 'deliberacao', 'aderencia', 'tese'];

/**
 * Where a reader says the tool read a decision wrong.
 *
 * It lives inside "Por que esta decisão está aqui" because that is where the
 * tool owns each reading, and so where disagreeing with one makes sense. The
 * receipt says, in as many words, that nothing changed: a report asks for a
 * review, and the classification on screen is still the published one.
 */
export default function ReportClassification({ decision, contested }: ReportClassificationProps) {
  const [state, setState] = useState<State>({ kind: 'closed' });
  const [information, setInformation] = useState<ContestedInformation>(contested);
  const [description, setDescription] = useState('');
  const id = useId();

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!description.trim()) {
      setState({ kind: 'writing', failure: 'Descreva o que está incorreto.' });
      return;
    }

    setState({ kind: 'sending' });

    try {
      const receipt = await reportClassification(decision, information, description.trim());
      setDescription('');
      setState({ kind: 'received', message: receipt.message });
    } catch (error) {
      setState({
        kind: 'writing',
        failure:
          error instanceof ReportError
            ? error.message
            : 'Não foi possível enviar o reporte. Tente novamente.',
      });
    }
  }

  if (state.kind === 'closed') {
    return (
      <div className="classification-report">
        <button
          type="button"
          className="classification-report__open"
          onClick={() => setState({ kind: 'writing', failure: null })}
        >
          <Flag size={12} aria-hidden="true" />
          Reportar classificação incorreta
        </button>
      </div>
    );
  }

  if (state.kind === 'received') {
    return (
      <div className="classification-report">
        <p className="classification-report__receipt" role="status">
          {state.message}
        </p>
      </div>
    );
  }

  const sending = state.kind === 'sending';

  return (
    <div className="classification-report">
      <form
        className="classification-report__form"
        aria-label="Reportar classificação incorreta"
        onSubmit={(event) => void submit(event)}
      >
        <label className="classification-report__field" htmlFor={`${id}-informacao`}>
          Qual informação está incorreta?
        </label>
        <select
          id={`${id}-informacao`}
          value={information}
          disabled={sending}
          onChange={(event) => setInformation(event.target.value as ContestedInformation)}
        >
          {ORDER.map((value) => (
            <option key={value} value={value}>
              {CONTESTED_LABELS[value]}
            </option>
          ))}
        </select>

        <label className="classification-report__field" htmlFor={`${id}-relato`}>
          O que está incorreto?
        </label>
        <textarea
          id={`${id}-relato`}
          rows={3}
          required
          maxLength={MAX_REPORT_LENGTH}
          disabled={sending}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <small className="classification-report__hint">
          O reporte vai para revisão. Ele não altera a classificação publicada.
        </small>

        {state.kind === 'writing' && state.failure && (
          <p className="classification-report__failure" role="alert">
            {state.failure}
          </p>
        )}

        <div className="classification-report__actions">
          <button type="submit" className="classification-report__send" disabled={sending}>
            {sending ? 'Enviando…' : 'Enviar reporte'}
          </button>
          <button
            type="button"
            className="classification-report__cancel"
            disabled={sending}
            onClick={() => setState({ kind: 'closed' })}
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
