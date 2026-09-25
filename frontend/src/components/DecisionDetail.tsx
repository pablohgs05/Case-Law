import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowSquareOut } from '@phosphor-icons/react';

import { DecisionRequestError, getDecision, type Decision } from '../api/decisions';
import { formatDate, normalizeOfficialUrl, normalizeText } from './decisionFormat';

type DetailState =
  | { status: 'loading' }
  | { status: 'loaded'; decision: Decision }
  | { status: 'not-found' }
  | { status: 'failed' };

type DecisionDetailProps = {
  id: string;
  source: string;
  identifier: string;
  // The way back out of this decision, when there is one to offer.
  back?: { label: string; onClick: () => void };
};

type MetadataItem = { label: string; value: string };

// Only what the decision actually carries. An absent field is left out rather
// than shown with an empty value, so no label stands alone.
function metadataOf(decision: Decision): MetadataItem[] {
  const judged = formatDate(decision.judged_on);
  const published = formatDate(decision.published_on);

  const items: (MetadataItem | null)[] = [
    textItem('Número do processo', decision.case_number),
    textItem('Relator', decision.reporting_judge),
    textItem('Órgão julgador', decision.judging_body),
    decision.class_code !== null && Number.isFinite(decision.class_code)
      ? { label: 'Classe processual (código CNJ)', value: String(decision.class_code) }
      : null,
    judged ? { label: 'Data do julgamento', value: judged } : null,
    published ? { label: 'Data da publicação', value: published } : null,
  ];

  // Neither date on its own: the reference date the API always sends, named for
  // what it is rather than passed off as one of the two.
  if (!judged && !published) {
    const decided = formatDate(decision.decided_on);
    items.push(decided ? { label: 'Data da decisão', value: decided } : null);
  }

  return items.filter((item): item is MetadataItem => item !== null);
}

function textItem(label: string, value: string | null): MetadataItem | null {
  const normalized = normalizeText(value);
  return normalized ? { label, value: normalized } : null;
}

function DecisionDetail({ id, source, identifier, back }: DecisionDetailProps) {
  const [state, setState] = useState<DetailState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // Opening another decision remounts this panel; a retry runs this again.
    // Either way the request in flight is abandoned, so a late answer never
    // replaces the one on screen.
    const controller = new AbortController();
    let active = true;

    getDecision(source, identifier, { signal: controller.signal }).then(
      (decision) => {
        if (active) {
          setState({ status: 'loaded', decision });
        }
      },
      (error: unknown) => {
        if (!active) {
          return;
        }
        const missing = error instanceof DecisionRequestError && error.status === 404;
        setState({ status: missing ? 'not-found' : 'failed' });
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, [source, identifier, attempt]);

  const retry = () => {
    setState({ status: 'loading' });
    setAttempt((current) => current + 1);
  };

  const titleId = `${id}-title`;

  return (
    <aside
      id={id}
      className="decision-detail"
      aria-labelledby={titleId}
      aria-busy={state.status === 'loading'}
    >
      {back && (
        <div className="decision-detail__toolbar">
          <button type="button" className="decision-detail__back" onClick={back.onClick}>
            <ArrowLeft size={16} aria-hidden="true" />
            {back.label}
          </button>
        </div>
      )}

      {state.status === 'loading' && (
        <>
          <h2 id={titleId} className="sr-only">
            Decisão
          </h2>
          <p className="search-state search-state--loading" role="status">
            Carregando decisão...
          </p>
        </>
      )}

      {state.status === 'not-found' && (
        <div className="search-state search-state--error" role="alert">
          <h2 id={titleId} className="decision-detail__state-title">
            Decisão não encontrada
          </h2>
          <p>
            Ela não está mais disponível na base. Decisões sob segredo de justiça também não são
            exibidas.
          </p>
        </div>
      )}

      {state.status === 'failed' && (
        <div className="search-state search-state--error" role="alert">
          <h2 id={titleId} className="decision-detail__state-title">
            Não foi possível carregar a decisão
          </h2>
          <p>Verifique a conexão e tente novamente.</p>
          <button type="button" className="search-state__retry" onClick={retry}>
            Tentar novamente
          </button>
        </div>
      )}

      {state.status === 'loaded' && <DecisionContent decision={state.decision} titleId={titleId} />}
    </aside>
  );
}

type DecisionContentProps = {
  decision: Decision;
  titleId: string;
};

function DecisionContent({ decision, titleId }: DecisionContentProps) {
  const metadata = metadataOf(decision);
  const court = normalizeText(decision.court);
  const caseNumber = normalizeText(decision.case_number);

  return (
    <>
      <header className="decision-detail__header">
        {court && <span className="decision-detail__court">{court}</span>}
        <h2 id={titleId} tabIndex={-1} className="decision-detail__title">
          {caseNumber ? `Processo ${caseNumber}` : 'Decisão sem número de processo informado'}
        </h2>
      </header>

      {metadata.length > 0 && (
        <dl className="decision-detail__meta">
          {metadata.map((item) => (
            <div className="decision-detail__meta-item" key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      )}

      <Ementa decision={decision} headingId={`${titleId}-ementa`} />

      <OfficialSource decision={decision} />
    </>
  );
}

// The national court council's order, with the names the backend recognises
// them by. The API sends the sections without the labels the court wrote, so
// these name them. "Dispositivo" covers both "DISPOSITIVO" and "DISPOSITIVO E
// TESE": naming a thesis the court may not have stated would be false.
const SECTIONS = [
  { key: 'case', label: 'I. Caso em exame' },
  { key: 'question', label: 'II. Questão em discussão' },
  { key: 'reasoning', label: 'III. Razões de decidir' },
  { key: 'ruling', label: 'IV. Dispositivo' },
] as const;

type EmentaProps = { decision: Decision; headingId: string };

// The whole ementa, as the court wrote it, never the search snippet. The
// detail is read without a search term, so every field is plain text and React
// renders it as text: nothing from the API is ever parsed as HTML.
function Ementa({ decision, headingId }: EmentaProps) {
  const sections = decision.sections;
  const summary = decision.summary ?? '';
  // The contract answers `sections` only with all four found. Should one still
  // come back empty, the complete text is shown instead of an empty heading.
  const structured =
    sections !== null && SECTIONS.every(({ key }) => normalizeText(sections[key]) !== '');

  return (
    <section className="decision-detail__reading" aria-labelledby={headingId}>
      <h3 id={headingId} className="decision-detail__section-title">
        Ementa
      </h3>

      {structured ? (
        <>
          {normalizeText(sections.headnote) && (
            <p className="decision-detail__headnote">{sections.headnote}</p>
          )}

          {SECTIONS.map(({ key, label }) => (
            <section
              key={key}
              className="decision-detail__part"
              aria-labelledby={`${headingId}-${key}`}
            >
              <h4 id={`${headingId}-${key}`} className="decision-detail__part-title">
                {label}
              </h4>
              <p className="decision-detail__text">{sections[key]}</p>
            </section>
          ))}
        </>
      ) : normalizeText(summary) ? (
        <p className="decision-detail__text">{summary}</p>
      ) : (
        <p className="decision-detail__missing">
          A ementa desta decisão não está disponível. Consulte o documento na fonte oficial.
        </p>
      )}
    </section>
  );
}

type OfficialSourceProps = { decision: Decision };

// The same rule as the result card: only a real web address becomes a link,
// and one the load found broken is shown as unavailable rather than followed.
// Nothing here asks the court's site anything.
function OfficialSource({ decision }: OfficialSourceProps) {
  const officialUrl = normalizeOfficialUrl(decision.source_url);
  const available = officialUrl !== null && decision.source_url_reachable !== false;
  const court = normalizeText(decision.court);

  return (
    <section className="official-source" aria-label="Fonte oficial">
      <div className="official-source__text">
        <p className="official-source__title">Documento oficial como referência principal</p>
        <p className="official-source__detail">
          {available
            ? `A decisão no site do ${court || 'tribunal'} prevalece sobre qualquer conteúdo desta página.`
            : 'Link indisponível no momento.'}
        </p>
      </div>

      {available ? (
        <a
          className="official-source__action"
          href={officialUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <ArrowSquareOut size={16} aria-hidden="true" />
          Abrir fonte oficial
          <span className="sr-only"> (abre em nova aba)</span>
        </a>
      ) : (
        <span
          className="official-source__action official-source__action--disabled"
          role="link"
          aria-disabled="true"
          tabIndex={-1}
        >
          Abrir fonte oficial
          <span className="sr-only"> (indisponível)</span>
        </span>
      )}
    </section>
  );
}

export default DecisionDetail;
