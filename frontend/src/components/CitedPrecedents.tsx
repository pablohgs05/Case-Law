import { ArrowSquareOut, Robot, Warning } from '@phosphor-icons/react';

import type { CitedPrecedent } from '../api/precedents';
import {
  adherenceLabel,
  ADHERENCE_MEANINGS,
  officialUrl,
  orderCited,
  precedentName,
  standingOf,
} from './precedentFormat';

/**
 * What the court cited, and what this tool read into it.
 *
 * The two are not the same kind of claim and must not look alike. The
 * enunciado and the snippet are quotations — the reader can put them in a
 * petition. The adherence is an inference from wording, which they cannot. So
 * the quotations sit in the body as quotations, and the reading sits below a
 * rule, named as a reading, with its own icon and wording.
 */

type CitedPrecedentsProps = { precedents: CitedPrecedent[]; headingId: string };

function Standing({ status }: { status: string | null }) {
  const standing = standingOf(status);

  if (standing === 'superseded') {
    return (
      <p className="precedent__standing precedent__standing--superseded">
        <Warning size={14} weight="fill" aria-hidden="true" />
        <span>
          Precedente {status}. A decisão que o aplicou continua sendo um fato, mas o enunciado não
          vale hoje.
        </span>
      </p>
    );
  }

  // Nothing at all when the status is unknown, which is every reconstructed
  // súmula: a warning that appears on all of them stops being read, and it
  // would compete with the one above, which is the one that matters. The
  // section says it once instead.
  if (standing === 'unknown') {
    return null;
  }

  return <p className="precedent__standing">Situação: {status}</p>;
}

function Precedent({ precedent }: { precedent: CitedPrecedent }) {
  const name = precedentName(precedent);
  const source = precedent.court_stated ? officialUrl(precedent) : null;
  const reading = precedent.adherence;

  return (
    <article className="precedent" aria-label={name}>
      <header className="precedent__header">
        <h4 className="precedent__name">{name}</h4>
        {source && (
          <a className="precedent__source" href={source} target="_blank" rel="noopener noreferrer">
            <ArrowSquareOut size={14} aria-hidden="true" />
            Fonte oficial
            <span className="sr-only"> de {name} (abre em nova aba)</span>
          </a>
        )}
      </header>

      <Standing status={precedent.status} />

      {!precedent.court_stated && (
        <p className="precedent__standing precedent__standing--unknown">
          O acórdão não disse de qual corte é este tema. O STJ e o STF têm um com esse número, e
          dizem coisas diferentes — por isso o enunciado não é mostrado.
        </p>
      )}

      {precedent.text ? (
        <blockquote className="precedent__text">{precedent.text}</blockquote>
      ) : (
        <p className="precedent__text precedent__text--missing">
          O enunciado deste precedente não está no acervo. A citação é real; o texto precisa ser
          conferido na fonte oficial.
        </p>
      )}

      {precedent.snippet && (
        <div className="precedent__quote">
          <p className="precedent__quote-label">Onde aparece no acórdão</p>
          <p className="precedent__quote-text">…{precedent.snippet}…</p>
        </div>
      )}

      {/* Below the rule, and said in words: everything above is the court's,
          this line is ours. A reader can cite the first and not the second. */}
      {reading && (
        <footer className="precedent__reading">
          <p className="precedent__reading-label">
            <Robot size={14} aria-hidden="true" />
            Leitura automática desta ferramenta
          </p>
          <p className="precedent__reading-value">
            <strong>{adherenceLabel(reading)}</strong>
            {ADHERENCE_MEANINGS[reading] && <span> — {ADHERENCE_MEANINGS[reading]}</span>}
          </p>
        </footer>
      )}
    </article>
  );
}

function CitedPrecedents({ precedents, headingId }: CitedPrecedentsProps) {
  if (precedents.length === 0) {
    return null;
  }

  const ordered = orderCited(precedents);

  return (
    <section className="precedents" aria-labelledby={headingId}>
      <h3 id={headingId} className="decision-detail__section-title">
        Precedentes citados
      </h3>
      <p className="precedents__lead">
        Súmulas e temas que esta decisão invoca. O enunciado e o trecho são do acórdão; o rótulo ao
        final de cada bloco é leitura automática, não texto do tribunal. O acervo não registra se um
        precedente segue valendo, salvo quando marcado abaixo — confira na fonte oficial antes de
        citar.
      </p>

      <div className="precedents__list">
        {ordered.map((precedent) => (
          <Precedent
            key={`${precedent.court}-${precedent.kind}-${precedent.number}`}
            precedent={precedent}
          />
        ))}
      </div>
    </section>
  );
}

export default CitedPrecedents;
