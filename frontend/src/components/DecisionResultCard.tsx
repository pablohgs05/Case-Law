import { Fragment, type ReactNode } from 'react';
import { Link, type To } from 'react-router-dom';
import { ArrowRight, ArrowSquareOut } from '@phosphor-icons/react';

import { readThesis } from '../api/decisions';
import IdentifiedThesis from './IdentifiedThesis';
import type { Highlight, SearchDecisionMatch } from '../api/search';
import {
  DELIBERATION_LABELS,
  deliberationStateOf,
  formatDate,
  getDisplayValue,
  NOT_INFORMED,
  normalizeOfficialUrl,
  normalizeText,
} from './decisionFormat';

type DecisionCardData = Pick<
  SearchDecisionMatch,
  | 'court'
  | 'case_number'
  | 'judging_body'
  | 'reporting_judge'
  | 'decided_on'
  | 'source_url'
  | 'source_url_reachable'
  | 'deliberation'
  | 'snippet'
  | 'thesis'
> & {
  published_on?: string | null;
  // Where the decision lives, which is how the API is asked about it.
  // Optional because the card renders without them — and then the thesis
  // cannot be asked for, so the button is not offered.
  source?: string;
  identifier?: string;
};

type DecisionResultCardProps = {
  decision: DecisionCardData;
  // Which indicator put this card here, when one did. The justification only
  // makes sense for a classification this tool inferred: court and period are
  // fields copied from the source, so there is nothing of the court's to
  // point at and no claim of ours to answer for.
  justifies?: Highlight;
  // The address of the decision in full. Without it the card only links to
  // the court.
  to?: To;
  // How following it changes the history, as a router link takes them.
  replace?: boolean;
  state?: unknown;
  // Called as the card is followed, for what the address alone does not do.
  onOpen?: () => void;
  onSelect?: () => void;
  openButtonId?: string;
  // The decision open in the detail panel, marked so the list says which.
  selected?: boolean;
  // Its place in the whole result, counting from 1 across pages.
  rank?: number;
};

function renderSafeSnippet(value: string | null | undefined): ReactNode[] {
  const normalized = normalizeText(value);

  if (!normalized) {
    return ['Trecho indisponível.'];
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(normalized, 'text/html');
  const root = doc.body;

  const walk = (node: ChildNode, keyPrefix: string): ReactNode[] => {
    const fragments: ReactNode[] = [];

    Array.from(node.childNodes).forEach((child, index) => {
      const key = `${keyPrefix}-${index}`;

      if (child.nodeType === Node.TEXT_NODE) {
        const text = child.textContent ?? '';
        if (text) {
          fragments.push(<Fragment key={key}>{text}</Fragment>);
        }
        return;
      }

      if (child.nodeType !== Node.ELEMENT_NODE) {
        return;
      }

      const element = child as Element;
      const renderedChildren = walk(child, key);

      if (element.tagName === 'MARK') {
        fragments.push(<mark key={key}>{renderedChildren}</mark>);
        return;
      }

      if (renderedChildren.length > 0) {
        fragments.push(...renderedChildren);
      }
    });

    return fragments;
  };

  const renderedNodes = root.childNodes.length > 0 ? walk(root, 'snippet-root') : [];
  return renderedNodes.length > 0 ? renderedNodes : ['Trecho indisponível.'];
}

function DecisionResultCard({
  decision,
  justifies,
  to,
  replace,
  state,
  onOpen,
  onSelect,
  openButtonId,
  selected = false,
  rank,
}: DecisionResultCardProps) {
  const officialUrl = normalizeOfficialUrl(decision.source_url);
  const linkIsUnavailable = !officialUrl || decision.source_url_reachable === false;

  // The court and the case number head the card and the date sits beside
  // them, so the list below carries only what they do not.
  // The card has no dispositive, so an undecided vote stays unsaid.
  const deliberation = deliberationStateOf(decision.deliberation);
  const metadata = [
    { label: 'Órgão julgador', value: getDisplayValue(decision.judging_body) },
    { label: 'Relator', value: getDisplayValue(decision.reporting_judge) },
    {
      label: 'Deliberação',
      value: deliberation ? DELIBERATION_LABELS[deliberation] : NOT_INFORMED,
    },
    {
      label: 'Data de publicação',
      value: formatDate(decision.published_on) ?? NOT_INFORMED,
    },
  ];
  const decided = formatDate(decision.decided_on);
  const thesis = readThesis(decision.thesis);

  return (
    <article
      className={
        selected ? 'decision-result-card decision-result-card--selected' : 'decision-result-card'
      }
      aria-label={`Decisão ${decision.case_number ?? 'sem processo'}`}
    >
      {/* The whole card opens the decision, as in the reference. A real link
          stretched over the card, to the decision's own address: it can be
          opened in another tab or copied. The official link is a sibling, not
          a child, and sits above it, so it never opens this one as well. */}
      {to && (
        <Link
          to={to}
          replace={replace}
          state={state}
          id={openButtonId}
          className="decision-result-card__select"
          onClick={onOpen}
          aria-current={selected ? 'true' : undefined}
        >
          <span className="sr-only">
            Ler a decisão
            {normalizeText(decision.case_number) ? ` do processo ${decision.case_number}` : ''}
          </span>
        </Link>
      )}

      {rank !== undefined && (
        <span className="decision-result-card__rank" aria-hidden="true">
          {String(rank).padStart(2, '0')}
        </span>
      )}

      <div className="decision-result-card__body">
        <header className="decision-result-card__header">
          <div className="decision-result-card__title">
            <span className="decision-result-card__court">{getDisplayValue(decision.court)}</span>
            <span className="decision-result-card__process">
              {getDisplayValue(decision.case_number)}
            </span>
          </div>
          {decided && <span className="decision-result-card__date">{decided}</span>}
        </header>

        <p className="decision-result-card__snippet">{renderSafeSnippet(decision.snippet)}</p>

        {/* Closed by default: the thesis block runs to 441 characters on
            average, and six of them open would stop the list being scannable.
            It sits above the stretched link, like the official link does, so
            opening it does not open the decision. */}
        {justifies && (
          <details className="decision-result-card__thesis">
            <summary>Por que esta decisão está aqui</summary>
            {thesis.length > 0 ? (
              <>
                <p className="decision-result-card__thesis-origin">Tese firmada pelo tribunal</p>
                <ol className="decision-result-card__thesis-list">
                  {thesis.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ol>
              </>
            ) : normalizeText(decision.snippet) ? (
              /* No thesis written, so the evidence is the snippet above —
                 which this list cut around the dispositive or the citation,
                 not around what was typed. */
              <>
                <p className="decision-result-card__thesis-origin">
                  O tribunal não escreveu tese. O trecho acima é a passagem que produziu a
                  classificação.
                </p>
                {/* The court wrote none, so the reader may ask this tool to
                    read one out of the ementa. Behind a press, never on
                    render: the call costs money and most cards are scrolled
                    past. */}
                {decision.source && decision.identifier && (
                  <IdentifiedThesis source={decision.source} identifier={decision.identifier} />
                )}
              </>
            ) : (
              <p className="decision-result-card__thesis-origin">
                O tribunal não escreveu tese nem dispositivo para esta decisão.
              </p>
            )}
            <p className="decision-result-card__thesis-reading">
              {justifies === 'resultado'
                ? 'O resultado é leitura automática desta ferramenta, a partir do texto acima.'
                : 'A aderência é leitura automática desta ferramenta, a partir do texto acima.'}
            </p>
          </details>
        )}

        <dl className="decision-result-card__meta">
          {metadata
            .filter((item) => item.value !== NOT_INFORMED)
            .map((item) => (
              <div className="decision-result-card__meta-item" key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
        </dl>

        <div className="decision-result-card__actions" aria-live="polite">
          {onSelect && (
            <button type="button" className="indicator-document__open" onClick={onSelect}>
              Abrir decisão
            </button>
          )}
          {officialUrl && decision.source_url_reachable !== false ? (
            <a
              className="decision-result-card__source-link"
              href={officialUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Abrir fonte oficial em nova aba"
            >
              <ArrowSquareOut size={12} aria-hidden="true" />
              Fonte oficial
              <span className="sr-only"> (abre em nova aba)</span>
            </a>
          ) : (
            <span
              className="decision-result-card__source-link decision-result-card__source-link--disabled"
              aria-disabled="true"
              aria-label="Fonte oficial indisponível"
              tabIndex={-1}
              role="link"
            >
              Fonte oficial
              <span className="sr-only"> (indisponível)</span>
            </span>
          )}

          {linkIsUnavailable && (
            <span className="decision-result-card__source-status">
              Link indisponível no momento.
            </span>
          )}
        </div>
      </div>

      {to && <ArrowRight className="decision-result-card__arrow" size={14} aria-hidden="true" />}
    </article>
  );
}

export default DecisionResultCard;
