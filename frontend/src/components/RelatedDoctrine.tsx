import { useEffect, useState } from 'react';
import { ArrowSquareOut, WarningCircle } from '@phosphor-icons/react';

import { getRelatedDoctrine, type Suggestion } from '../api/doctrine';
import {
  commonGround,
  COMMON_GROUND_LABELS,
  GROUND_SEPARATOR,
  MAX_COMMON_GROUND,
  workKind,
} from './doctrineFormat';

/**
 * What other people wrote about the subject this decision settled.
 *
 * Three kinds of claim now share this screen and they must not look alike: the
 * ementa is the court's, the thesis and the adherence are this tool's reading,
 * and this block is nobody's here — it is third-party scholarship we point at
 * and never reproduce. So every card is built around its outbound link, and
 * the section says in one line where the works live.
 *
 * It fetches on its own. The decision is already on screen when this starts,
 * and nothing here can keep it from being read: a failure turns into a line
 * inside this block and stops there.
 */

type RelatedDoctrineProps = { source: string; identifier: string; headingId: string };

type State =
  { status: 'loading' } | { status: 'loaded'; suggestions: Suggestion[] } | { status: 'failed' };

const LIMIT = 5;

function Work({ suggestion }: { suggestion: Suggestion }) {
  const ground = commonGround(suggestion);
  const kind = workKind(suggestion);
  const authors = suggestion.authors.join('; ');

  return (
    <article className="work" aria-label={suggestion.title}>
      <h4 className="work__title">
        <a
          className="work__link"
          href={suggestion.url}
          target="_blank"
          rel="noreferrer noopener"
          // The title is the link because the link is the point: the work is
          // at the repository and this screen only shows the way there.
        >
          {suggestion.title}
          <ArrowSquareOut size={14} weight="bold" aria-hidden="true" />
        </a>
      </h4>

      {authors && <p className="work__authors">{authors}</p>}

      {(kind || suggestion.publication) && (
        <p className="work__imprint">
          {[kind, suggestion.publication].filter(Boolean).join(' · ')}
        </p>
      )}

      {ground.kind !== 'none' && (
        <p className="work__ground">
          <span className="work__ground-label">{COMMON_GROUND_LABELS[ground.kind]}:</span>{' '}
          {ground.items.slice(0, MAX_COMMON_GROUND).join(GROUND_SEPARATOR)}
        </p>
      )}
    </article>
  );
}

export default function RelatedDoctrine({ source, identifier, headingId }: RelatedDoctrineProps) {
  const [state, setState] = useState<State>({ status: 'loading' });

  useEffect(() => {
    // Mounted once per decision — the call site keys this block on the pair —
    // so there is no stale state to reset here. The flag is for the answer
    // that lands after the reader has already moved on.
    const controller = new AbortController();
    let active = true;

    getRelatedDoctrine(source, identifier, { signal: controller.signal, limit: LIMIT }).then(
      (suggestions) => {
        if (active) {
          setState({ status: 'loaded', suggestions });
        }
      },
      () => {
        if (active) {
          setState({ status: 'failed' });
        }
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, [source, identifier]);

  return (
    <section className="doctrine" aria-labelledby={headingId}>
      <h3 id={headingId} className="decision-detail__section-title">
        Doutrina sobre o assunto
      </h3>

      <p className="doctrine__lead">
        Publicada por terceiros, não por este tribunal nem por esta ferramenta. Os textos ficam no
        acervo de origem, e cada título abre lá.
      </p>

      {state.status === 'loading' && (
        <p className="doctrine__state" role="status">
          Procurando doutrina relacionada…
        </p>
      )}

      {/* An answer and a failure read alike if they are written alike, and
          they are not the same news: the first means the matching ran and
          found nothing above the threshold, the second that it did not run. */}
      {state.status === 'failed' && (
        <p className="doctrine__state doctrine__state--failed">
          <WarningCircle size={15} weight="fill" aria-hidden="true" />
          <span>
            Não foi possível consultar a doutrina agora. A decisão acima está completa; só este
            bloco ficou de fora.
          </span>
        </p>
      )}

      {state.status === 'loaded' && state.suggestions.length === 0 && (
        <p className="doctrine__state">
          Nenhuma doutrina relacionada. A busca rodou e não encontrou nada próximo o bastante — o
          que acontece com quatro decisões em cada cinco, porque tese de processo não tem assunto de
          direito material para casar.
        </p>
      )}

      {state.status === 'loaded' && state.suggestions.length > 0 && (
        <div className="doctrine__list">
          {state.suggestions.map((suggestion) => (
            <Work
              key={`${suggestion.repository}:${suggestion.identifier}`}
              suggestion={suggestion}
            />
          ))}
        </div>
      )}
    </section>
  );
}
