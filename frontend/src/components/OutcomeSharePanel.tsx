import { Info } from '@phosphor-icons/react';

import { formatCount } from './coverageFormat';
import OutcomeShareChart from './OutcomeShareChart';
import { outcomeLabel, percent, rankOutcomes, type OutcomeState } from './outcomeFormat';

const plural = (count: number, one: string, many: string) =>
  `${formatCount(count)} ${count === 1 ? one : many}`;

// The four states the card has to keep apart. The last two look alike and are
// not: no decision matched, against decisions that matched and could not be read.
function message(state: OutcomeState): string | null {
  switch (state.status) {
    case 'idle':
      return 'Pesquise um tema para ver como esses recursos terminaram.';
    case 'failed':
      return state.message;
    case 'loaded': {
      const { total, classified } = state.outcome;
      if (total === 0) {
        return 'Nenhuma decisão encontrada para os filtros aplicados. Ajuste os termos ou amplie o período.';
      }
      if (!classified) {
        return 'Nenhuma decisão do recorte teve o resultado declarado no dispositivo.';
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
      {['68%', '22%', '10%'].map((width) => (
        <span key={width} className="volume-skeleton__bar" style={{ width }} />
      ))}
      <span className="sr-only">Carregando a proporção dos resultados</span>
    </div>
  );
}

type OutcomeSharePanelProps = {
  outcome: OutcomeState;
  onRetry: () => void;
  onSelectOutcome?: (outcome: string, count: number) => void;
  selectionDisabled?: boolean;
  compact?: boolean;
};

function OutcomeSharePanel({
  outcome,
  onRetry,
  onSelectOutcome,
  selectionDisabled,
  compact = false,
}: OutcomeSharePanelProps) {
  const loading = outcome.status === 'loading';
  const note = message(outcome);
  const share = outcome.status === 'loaded' ? outcome.outcome : null;
  const rows = share && !note ? rankOutcomes(share.outcomes) : null;
  const Explanation = compact ? 'details' : 'div';

  return (
    <section className="panorama" aria-labelledby="outcome-title">
      <header className="panorama__header" hidden={compact}>
        <div>
          <p className="panorama__eyebrow">Indicador explicável </p>
          <h2 id="outcome-title" className="panorama__title">
            Como esses recursos terminaram?
          </h2>
        </div>
        <p className="panorama__lead">
          A proporção usa os mesmos termos, tribunais e períodos da lista.
        </p>
      </header>

      <div className="panorama__grid">
        <article
          className="panorama-card"
          aria-labelledby={compact ? undefined : 'outcome-card-title'}
          aria-label={compact ? 'Resultado dos recursos' : undefined}
          aria-busy={loading}
        >
          <header className="panorama-card__header">
            <div>
              {compact && <p className="panorama__eyebrow">Resultado dos recursos</p>}
              <h3 id="outcome-card-title" className="panorama-card__title">
                {compact ? 'Provimento no recorte pesquisado' : 'Resultado dos recursos'}
              </h3>
            </div>
            {share?.total !== null && share?.total !== undefined && (
              <p className="panorama-card__meta">
                {plural(share.total, 'decisão no recorte', 'decisões no recorte')}
              </p>
            )}
          </header>

          <div className="panorama-card__body">
            {/* Above the percentages, never under them: a share of part of the
                cut reads as a share of the cut without it. */}
            {rows && share && (
              <p className="outcome-denominator">
                <strong>{formatCount(share.classified ?? 0)}</strong> com resultado declarado
                <span className="outcome-denominator__rest">
                  {' · '}
                  {formatCount(share.unclassified ?? 0)} sem declaração
                </span>
              </p>
            )}

            {loading && <Skeleton />}
            {note && outcome.status === 'failed' ? (
              <div className="search-state search-state--error panorama-card__error" role="alert">
                <p>{note}</p>
                <button type="button" className="search-state__retry" onClick={onRetry}>
                  Tentar novamente
                </button>
              </div>
            ) : (
              note && <p className="panorama-card__message">{note}</p>
            )}

            {rows && (
              <OutcomeShareChart
                outcomes={rows}
                horizontal={compact}
                onSelect={onSelectOutcome}
                disabled={loading || selectionDisabled}
              />
            )}

            {rows && !compact && (
              <ol className="outcome-list">
                {rows.map((row) => (
                  <li key={row.outcome} className="outcome-list__item">
                    <button
                      type="button"
                      className="indicator-target indicator-target--outcome"
                      disabled={
                        loading || selectionDisabled || row.decisions === null || !onSelectOutcome
                      }
                      onClick={() =>
                        row.decisions !== null && onSelectOutcome?.(row.outcome, row.decisions)
                      }
                      aria-label={`Consultar documentos com resultado ${outcomeLabel(row.outcome)}: ${formatCount(row.decisions)} decisões`}
                    >
                      <span className="outcome-list__label">
                        <span className="outcome-list__swatch" data-outcome={row.outcome} />
                        {outcomeLabel(row.outcome)}
                      </span>
                      <span className="outcome-list__share">
                        {row.share === null ? '—' : percent(row.share)}
                      </span>
                      <span className="outcome-list__count">
                        {formatCount(row.decisions ?? 0)}
                        <span className="sr-only">
                          {row.decisions === 1 ? ' decisão' : ' decisões'}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <footer className="volume-card__footer">
            <p className="volume-card__note">
              <Info size={13} aria-hidden="true" />
              Cada percentual é calculado sobre o número acima, não sobre o recorte inteiro.
            </p>
          </footer>
        </article>

        <article className="panorama-card panorama-card--composition">
          <Explanation className="composition__explain">
            {compact ? (
              <summary>
                <Info size={14} aria-hidden="true" /> Como este número é formado?
              </summary>
            ) : (
              <h4 className="composition__explain-title">Como este número é formado?</h4>
            )}
            <p className="composition__explain-text">
              O resultado é lido do dispositivo que o próprio tribunal publicou — a frase que
              declara se o recurso foi provido, provido em parte ou negado. Quando o dispositivo não
              declara, a decisão entra em &quot;sem declaração&quot; e fica fora do percentual, em
              vez de ser contada como negada.
            </p>
            <p className="composition__explain-text">
              Nem toda decisão julga o mérito de um recurso: conflito de competência, recurso
              prejudicado e extinção não têm resultado a declarar.
            </p>
          </Explanation>
        </article>
      </div>
    </section>
  );
}

export default OutcomeSharePanel;
