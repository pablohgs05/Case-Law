import { Fragment, type ReactNode } from 'react';

import type { SearchDecisionMatch } from '../api/search';

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
};

function normalizeText(value: string | null | undefined): string {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim();
}

function getDisplayValue(value: string | null | undefined): string {
  const normalized = normalizeText(value);
  return normalized || 'Não informado';
}

function normalizeOfficialUrl(value: string | null | undefined): string | null {
  const normalized = normalizeText(value);

  if (!normalized) {
    return null;
  }

  try {
    const parsedUrl = new URL(normalized);
    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      return null;
    }

    return normalized;
  } catch {
    return null;
  }
}

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

function formatDate(value: string | null | undefined): string | null {
  const normalized = normalizeText(value);

  if (!normalized) {
    return null;
  }

  const isoDateMatch = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);

  if (isoDateMatch) {
    const [, year, month, day] = isoDateMatch;
    const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));

    if (Number.isNaN(date.getTime())) {
      return null;
    }

    return date.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
  }

  const parsedDate = new Date(normalized);

  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return parsedDate.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
}

function DecisionResultCard({ decision }: DecisionResultCardProps) {
  const officialUrl = normalizeOfficialUrl(decision.source_url);
  const linkIsUnavailable = !officialUrl || decision.source_url_reachable === false;

  const metadata = [
    { label: 'Processo', value: getDisplayValue(decision.case_number) },
    { label: 'Órgão julgador', value: getDisplayValue(decision.judging_body) },
    { label: 'Relator', value: getDisplayValue(decision.reporting_judge) },
    {
      label: 'Data de julgamento',
      value: formatDate(decision.decided_on) ?? 'Não informado',
    },
    {
      label: 'Data de publicação',
      value: formatDate(decision.published_on) ?? 'Não informado',
    },
  ];

  return (
    <article
      className="decision-result-card"
      aria-label={`Decisão ${decision.case_number ?? 'sem processo'}`}
    >
      <header className="decision-result-card__header">
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
          .filter((item) => item.value !== 'Não informado')
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
