import { ArrowRight, Info } from '@phosphor-icons/react';

import type { ConcentrationDimension } from '../api/indicators';
import { CONCENTRATION_LABELS, type ConcentrationField } from '../search/indicatorSelection';
import { formatCount } from './coverageFormat';
import {
  CONCENTRATION_LIMIT,
  MIN_CONCENTRATION_CUT,
  type ConcentrationState,
} from './concentrationFormat';
import { percent } from './outcomeFormat';

const plural = (count: number, one: string, many: string) =>
  `${formatCount(count)} ${count === 1 ? one : many}`;

export type ConcentrationSelection = {
  field: ConcentrationField;
  // Null is the folded rest.
  name: string | null;
  ranked: string[];
  count: number;
};

// What stands in place of both lists while there is nothing honest to draw: no
// search yet, a failure, a cut that matched nothing, or one too small for a
// share to mean anything.
function message(state: ConcentrationState): string | null {
  switch (state.status) {
    case 'idle':
      return 'Pesquise um tema para ver em quais órgãos julgadores e com quais relatores ele se concentra.';
    case 'failed':
      return state.message;
    case 'loaded': {
      const { total } = state.concentration;
      if (total === null) {
        return 'A concentração do recorte não foi informada.';
      }
      if (total === 0) {
        return 'Nenhuma decisão encontrada para os filtros aplicados. Ajuste os termos ou amplie o período.';
      }
      if (total < MIN_CONCENTRATION_CUT) {
        return `O recorte tem ${plural(total, 'decisão', 'decisões')}, poucas para indicar concentração: com menos de ${MIN_CONCENTRATION_CUT}, uma única decisão muda muito cada percentual. Consulte as decisões na lista ou amplie a pesquisa.`;
      }
      return null;
    }
    default:
      return null;
  }
}

function Skeleton() {
  return (
    <div className="volume-skeleton">
      {['72%', '44%', '20%'].map((width) => (
        <span key={width} className="volume-skeleton__bar" style={{ width }} />
      ))}
      <span className="sr-only">Carregando a concentração por órgão julgador e relator</span>
    </div>
  );
}

const TITLES: Record<ConcentrationField, { title: string; noun: string; nouns: string }> = {
  orgao_julgador: {
    title: 'Por órgão julgador',
    noun: 'órgão julgador',
    nouns: 'órgãos julgadores',
  },
  relator: { title: 'Por relator', noun: 'relator', nouns: 'relatores' },
};

function Ranking({
  field,
  dimension,
  limit,
  disabled,
  onSelect,
}: {
  field: ConcentrationField;
  dimension: ConcentrationDimension;
  limit: number;
  disabled: boolean;
  onSelect?: (selection: ConcentrationSelection) => void;
}) {
  const { title, noun, nouns } = TITLES[field];
  const ranked = dimension.groups.map((group) => group.name);
  const other = dimension.other;
  const missing = dimension.missing ?? 0;
  const headingId = `concentration-${field}-title`;

  return (
    <section className="concentration__dimension" aria-labelledby={headingId}>
      <h4 id={headingId} className="concentration__title">
        {title}
      </h4>
      <ol className="concentration__list">
        {dimension.groups.map((group, index) => (
          <li key={group.name} className="concentration__item">
            <button
              type="button"
              className="indicator-target indicator-target--concentration"
              disabled={disabled || group.decisions === null || !onSelect}
              onClick={() =>
                group.decisions !== null &&
                onSelect?.({ field, name: group.name, ranked, count: group.decisions })
              }
              aria-label={`Consultar documentos do ${noun} ${group.name}: ${formatCount(group.decisions) ?? 'quantidade não informada'} decisões`}
            >
              <span className="composition__rank" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span className="concentration__name">{group.name}</span>
              <span className="concentration__share">
                {group.share === null ? '—' : percent(group.share)}
              </span>
              <span className="composition__count">{formatCount(group.decisions)}</span>
              <span className="concentration__track" aria-hidden="true">
                <span
                  className="concentration__bar"
                  style={{ width: `${Math.min(100, group.share ?? 0)}%` }}
                />
              </span>
              <ArrowRight className="indicator-target__arrow" size={16} aria-hidden="true" />
            </button>
          </li>
        ))}
        {other && (
          <li className="concentration__item concentration__item--other">
            <button
              type="button"
              className="indicator-target indicator-target--concentration"
              disabled={disabled || other.decisions === null || !onSelect}
              onClick={() =>
                other.decisions !== null &&
                onSelect?.({ field, name: null, ranked, count: other.decisions })
              }
              aria-label={`Consultar documentos dos ${CONCENTRATION_LABELS[field].rest.toLowerCase()}: ${formatCount(other.decisions) ?? 'quantidade não informada'} decisões`}
            >
              <span className="composition__rank" aria-hidden="true">
                +
              </span>
              <span className="concentration__name">
                {CONCENTRATION_LABELS[field].rest}
                <span className="concentration__rule">
                  {other.groups
                    ? `${plural(other.groups, noun, nouns)} fora das ${limit} primeiras posições`
                    : `Fora das ${limit} primeiras posições`}
                  {missing > 0 &&
                    `, com ${plural(missing, 'decisão', 'decisões')} sem ${noun} informado`}
                </span>
              </span>
              <span className="concentration__share">
                {other.share === null ? '—' : percent(other.share)}
              </span>
              <span className="composition__count">{formatCount(other.decisions)}</span>
              <span className="concentration__track" aria-hidden="true">
                <span
                  className="concentration__bar concentration__bar--other"
                  style={{ width: `${Math.min(100, other.share ?? 0)}%` }}
                />
              </span>
              <ArrowRight className="indicator-target__arrow" size={16} aria-hidden="true" />
            </button>
          </li>
        )}
      </ol>
    </section>
  );
}

type ConcentrationPanelProps = {
  concentration: ConcentrationState;
  onRetry: () => void;
  onSelect?: (selection: ConcentrationSelection) => void;
  selectionDisabled?: boolean;
};

function ConcentrationPanel({
  concentration,
  onRetry,
  onSelect,
  selectionDisabled,
}: ConcentrationPanelProps) {
  const loading = concentration.status === 'loading';
  const note = message(concentration);
  const answer = concentration.status === 'loaded' ? concentration.concentration : null;
  const shown = answer && !note ? answer : null;
  const limit = answer?.limit ?? CONCENTRATION_LIMIT;
  const disabled = loading || Boolean(selectionDisabled);

  return (
    <section
      className="panorama concentration"
      aria-label="Concentração por órgão julgador e relator"
    >
      <div className="panorama__grid">
        <article
          className="panorama-card"
          aria-labelledby="concentration-card-title"
          aria-busy={loading}
        >
          <header className="panorama-card__header">
            <h3 id="concentration-card-title" className="panorama-card__title">
              Onde e por quem o tema é decidido
            </h3>
            {answer?.total !== null && answer?.total !== undefined && (
              <p className="panorama-card__meta">
                {plural(answer.total, 'decisão no recorte', 'decisões no recorte')}
              </p>
            )}
          </header>

          <div className="panorama-card__body">
            {loading && <Skeleton />}
            {note && concentration.status === 'failed' ? (
              <div className="search-state search-state--error panorama-card__error" role="alert">
                <p>{note}</p>
                <button type="button" className="search-state__retry" onClick={onRetry}>
                  Tentar novamente
                </button>
              </div>
            ) : (
              note && <p className="panorama-card__message">{note}</p>
            )}

            {shown && (
              <div className="concentration__grid">
                <Ranking
                  field="orgao_julgador"
                  dimension={shown.judging_bodies}
                  limit={limit}
                  disabled={disabled}
                  onSelect={onSelect}
                />
                <Ranking
                  field="relator"
                  dimension={shown.reporting_judges}
                  limit={limit}
                  disabled={disabled}
                  onSelect={onSelect}
                />
              </div>
            )}
          </div>

          <footer className="volume-card__footer">
            <p className="volume-card__note">
              <Info size={13} aria-hidden="true" />
              Cada percentual é calculado sobre todas as decisões do recorte.
            </p>
          </footer>
        </article>

        <article className="panorama-card panorama-card--composition">
          <details className="composition__explain">
            <summary>
              <Info size={14} aria-hidden="true" /> Como este número é formado?
            </summary>
            <p className="composition__explain-text">
              Contagem das decisões que atendem à pesquisa e aos filtros aplicados, agrupadas pelo
              órgão julgador e pelo relator registrados em cada uma. Os nomes aparecem como a fonte
              os escreve: grafias diferentes do mesmo nome contam como grupos diferentes, como nos
              filtros da pesquisa.
            </p>
            <p className="composition__explain-text">
              Os {limit} maiores grupos aparecem por nome. Todos os demais, e as decisões sem órgão
              ou relator informado, formam um grupo único, com a sua contagem. Recortes com menos de{' '}
              {MIN_CONCENTRATION_CUT} decisões não são exibidos como concentração.
            </p>
          </details>
        </article>
      </div>
    </section>
  );
}

export default ConcentrationPanel;
