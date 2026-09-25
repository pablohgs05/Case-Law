import { Fragment, type ReactNode } from 'react';
import { Link, type To } from 'react-router-dom';
import { ArrowRight } from '@phosphor-icons/react';

import type { SearchDecisionMatch } from '../api/search';
import {
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
  | 'snippet'
> & {
  published_on?: string | null;
};

type DecisionResultCardProps = {
  decision: DecisionCardData;
  // The address of the decision in full. Without it the card only links to
  // the court.
  to?: To;
  // How following it changes the history, as a router link takes them.
  replace?: boolean;
  state?: unknown;
  // Called as the card is followed, for what the address alone does not do.
  onOpen?: () => void;
  openButtonId?: string;
  // The decision open in the detail panel, marked so the list says which.
  selected?: boolean;
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
  to,
  replace,
  state,
  onOpen,
  openButtonId,
  selected = false,
}: DecisionResultCardProps) {
  const officialUrl = normalizeOfficialUrl(decision.source_url);
  const linkIsUnavailable = !officialUrl || decision.source_url_reachable === false;

  const metadata = [
    { label: 'Processo', value: getDisplayValue(decision.case_number) },
    { label: 'Órgão julgador', value: getDisplayValue(decision.judging_body) },
    { label: 'Relator', value: getDisplayValue(decision.reporting_judge) },
    {
      label: 'Data de julgamento',
      value: formatDate(decision.decided_on) ?? NOT_INFORMED,
    },
    {
      label: 'Data de publicação',
      value: formatDate(decision.published_on) ?? NOT_INFORMED,
    },
  ];

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

      <header className="decision-result-card__header">
        {to && <ArrowRight className="decision-result-card__arrow" size={16} aria-hidden="true" />}
        <div className="decision-result-card__title">
          <span className="decision-result-card__court">{getDisplayValue(decision.court)}</span>
          <span className="decision-result-card__separator">•</span>
          <span className="decision-result-card__process">
            {getDisplayValue(decision.case_number)}
          </span>
        </div>
      </header>

      <div className="decision-result-card__content">
        <p className="decision-result-card__snippet">{renderSafeSnippet(decision.snippet)}</p>
      </div>

      <div className="decision-result-card__actions" aria-live="polite">
        {officialUrl && decision.source_url_reachable !== false ? (
          <a
            className="decision-result-card__source-link"
            href={officialUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Abrir fonte oficial em nova aba"
          >
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
          <span className="decision-result-card__source-status">Link indisponível no momento.</span>
        )}
      </div>

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
    </article>
  );
}

export default DecisionResultCard;
