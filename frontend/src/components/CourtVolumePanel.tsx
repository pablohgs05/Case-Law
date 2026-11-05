import { ArrowRight, Info } from '@phosphor-icons/react';

import CourtVolumeChart from './CourtVolumeChart';
import { formatCount, formatDateTime, NOT_INFORMED, UNAVAILABLE } from './coverageFormat';
import { rankCourts, type LastUpdateState, type VolumeState } from './volumeFormat';

const plural = (count: number, one: string, many: string) =>
  `${formatCount(count)} ${count === 1 ? one : many}`;

const NO_DECISIONS =
  'Nenhuma decisão encontrada para os filtros aplicados. Ajuste os termos ou amplie o período.';

// What stands in place of the chart and of the list while there is nothing to
// draw. Each state says what it is: no search yet, a failure, or a cut that
// matched nothing — never an empty frame, and never a scale drawn over zeros.
function messages(state: VolumeState): { chart: string; list: string } | null {
  switch (state.status) {
    case 'idle':
      return {
        chart: 'Pesquise um tema para ver em quais tribunais ele aparece.',
        list: 'A composição aparece depois de uma pesquisa.',
      };
    case 'failed':
      return {
        chart: state.message,
        list: 'A composição do recorte está indisponível no momento.',
      };
    case 'loaded': {
      const { total, courts } = state.volume;
      const counted = courts.some((court) => (court.decisions ?? 0) > 0);
      // Zero is the answer only when the API says so. Courts it did not send,
      // or sent without a count, are not the same as none.
      if (total === 0) {
        return { chart: NO_DECISIONS, list: 'Nenhum tribunal no recorte.' };
      }
      if (!counted) {
        return {
          chart: 'O volume por tribunal não foi informado.',
          list: 'A composição do recorte não foi informada.',
        };
      }
      return null;
    }
    default:
      return null;
  }
}

// The collection's date, the same for every court. Without a finished load
// the reason is said rather than a missing value.
function lastUpdateText(state: LastUpdateState): { text: string; known: boolean } | null {
  if (state.status === 'loading') {
    return null;
  }
  if (state.status === 'unavailable') {
    return { text: UNAVAILABLE, known: false };
  }
  const updated = formatDateTime(state.lastUpdate.updated_at);
  if (updated) {
    return { text: updated, known: true };
  }
  const neverFinished =
    state.lastUpdate.state === 'all_loads_failed' || state.lastUpdate.state === 'never_loaded';
  return { text: neverFinished ? 'Nenhuma coleta concluída' : NOT_INFORMED, known: false };
}

function ChartSkeleton() {
  return (
    <div className="volume-skeleton">
      {['82%', '58%', '34%'].map((width) => (
        <span key={width} className="volume-skeleton__bar" style={{ width }} />
      ))}
      <span className="sr-only">Carregando o volume por tribunal</span>
    </div>
  );
}

type CourtVolumePanelProps = {
  volume: VolumeState;
  lastUpdate: LastUpdateState;
  onRetry: () => void;
  onSelectCourt?: (court: string, count: number) => void;
  selectionDisabled?: boolean;
  compact?: boolean;
};

function CourtVolumePanel({
  volume,
  lastUpdate,
  onRetry,
  onSelectCourt,
  selectionDisabled,
  compact = false,
}: CourtVolumePanelProps) {
  const loading = volume.status === 'loading';
  const message = messages(volume);
  // Ranked once, so the bars and the list can never disagree on the order.
  const courts = volume.status === 'loaded' && !message ? rankCourts(volume.volume.courts) : null;
  // The API's own total: never summed or adjusted here to match anything else.
  const total = volume.status === 'loaded' ? volume.volume.total : null;
  const updated = lastUpdateText(lastUpdate);
  const Explanation = compact ? 'details' : 'div';

  return (
    <section className="panorama" aria-labelledby="panorama-title">
      <header className="panorama__header" hidden={compact}>
        <div>
          <p className="panorama__eyebrow">Indicador explicável</p>
          <h2 id="panorama-title" className="panorama__title">
            Onde o tema aparece com mais frequência?
          </h2>
        </div>
        <p className="panorama__lead">
          O volume usa os mesmos termos, tribunais e períodos da lista.
        </p>
      </header>

      <div className="panorama__grid">
        <article className="panorama-card" aria-labelledby="volume-title" aria-busy={loading}>
          <header className="panorama-card__header">
            <h3 id="volume-title" className="panorama-card__title">
              Volume por tribunal
            </h3>
            {total !== null && (
              <p className="panorama-card__meta">
                {plural(total, 'decisão no recorte', 'decisões no recorte')}
              </p>
            )}
          </header>

          <div className="panorama-card__body">
            {loading && <ChartSkeleton />}
            {message && volume.status === 'failed' ? (
              <div className="search-state search-state--error panorama-card__error" role="alert">
                <p>{message.chart}</p>
                <button type="button" className="search-state__retry" onClick={onRetry}>
                  Tentar novamente
                </button>
              </div>
            ) : (
              message && <p className="panorama-card__message">{message.chart}</p>
            )}
            {courts && (
              <CourtVolumeChart
                courts={courts}
                onSelect={compact ? onSelectCourt : undefined}
                disabled={loading || selectionDisabled}
              />
            )}
          </div>

          <footer className="volume-card__footer">
            <p className="volume-card__note">
              <Info size={13} aria-hidden="true" />
              Frequência não representa relevância jurídica.
            </p>
            <p className="volume-card__updated">
              Última atualização:{' '}
              {updated === null ? (
                <span className="volume-card__updated-pending">
                  <span className="sr-only">Carregando</span>
                </span>
              ) : (
                <strong className={updated.known ? undefined : 'is-missing'}>{updated.text}</strong>
              )}
            </p>
          </footer>
        </article>

        {!compact && (
          <article
            className="panorama-card panorama-card--composition"
            aria-labelledby="composition-title"
            aria-busy={loading}
          >
            <header className="panorama-card__header">
              <h3 id="composition-title" className="panorama-card__title">
                Composição do recorte
              </h3>
              {total !== null && (
                <p className="panorama-card__meta">{plural(total, 'documento', 'documentos')}</p>
              )}
            </header>

            {loading && (
              <ul className="composition__list" aria-hidden="true">
                {[1, 2, 3].map((n) => (
                  <li key={n} className="composition__item composition__item--pending">
                    <span className="volume-skeleton__line" />
                  </li>
                ))}
              </ul>
            )}

            {message && <p className="panorama-card__message">{message.list}</p>}

            {/* The same courts, counts and order the chart is drawn from, as text. */}
            {courts && (
              <ol className="composition__list">
                {courts.map((court, index) => (
                  <li key={court.abbreviation} className="composition__item">
                    <button
                      type="button"
                      className="indicator-target indicator-target--court"
                      disabled={
                        loading || selectionDisabled || court.decisions === null || !onSelectCourt
                      }
                      onClick={() =>
                        court.decisions !== null &&
                        onSelectCourt?.(court.abbreviation, court.decisions)
                      }
                      aria-label={`Consultar documentos de ${court.abbreviation}: ${formatCount(court.decisions) ?? 'quantidade não informada'} decisões`}
                    >
                      <span className="composition__rank" aria-hidden="true">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span className="composition__court">
                        <strong className="composition__abbreviation">{court.abbreviation}</strong>
                        {court.name && <span className="composition__name">{court.name}</span>}
                      </span>
                      {court.decisions === null ? (
                        <span className="composition__count is-missing">{NOT_INFORMED}</span>
                      ) : (
                        <span className="composition__count">
                          {formatCount(court.decisions)}
                          <span className="sr-only">
                            {court.decisions === 1 ? ' decisão' : ' decisões'}
                          </span>
                        </span>
                      )}
                      {compact && (
                        <ArrowRight
                          className="indicator-target__arrow"
                          size={16}
                          aria-hidden="true"
                        />
                      )}
                    </button>
                  </li>
                ))}
              </ol>
            )}

            {/* The rule the endpoint applies, and only that: a count in the
              database of the decisions the search's own narrowing matches.
              Decisions under seal never enter the base. */}
            <Explanation className="composition__explain">
              {compact ? (
                <summary>
                  <Info size={14} aria-hidden="true" /> Como este número é formado?
                </summary>
              ) : (
                <h4 className="composition__explain-title">Como este número é formado?</h4>
              )}
              <p className="composition__explain-text">
                Contagem de decisões públicas únicas que atendem ao recorte, agrupadas por tribunal.
                Decisões em segredo de justiça não entram na base e não integram o cálculo.
              </p>
            </Explanation>
          </article>
        )}
      </div>
    </section>
  );
}

export default CourtVolumePanel;
