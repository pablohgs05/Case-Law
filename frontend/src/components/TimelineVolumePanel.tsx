import { lazy, Suspense } from 'react';
import type { VolumeByPeriod } from '../api/indicators';
import type { Granularity } from '../search/indicatorSelection';

const TimelineChart = lazy(() => import('./TimelineChart'));

export type TimelineState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed' }
  | { status: 'loaded'; volume: VolumeByPeriod };

export default function TimelineVolumePanel({
  timeline,
  onRetry,
  onSelectPeriod,
  selectionDisabled,
}: {
  timeline: TimelineState;
  onRetry: () => void;
  onSelectPeriod?: (period: string, granularity: Granularity, count: number) => void;
  selectionDisabled?: boolean;
}) {
  const volume = timeline.status === 'loaded' ? timeline.volume : null;
  const loading = timeline.status === 'loading';
  const empty = volume && (volume.total === 0 || volume.periods.length === 0);
  return (
    <section className="panorama temporal-volume" aria-labelledby="timeline-panel-title">
      <header className="panorama__header">
        <div>
          <p className="panorama__eyebrow">Movimento no período</p>
          <h2 id="timeline-panel-title" className="panorama__title">
            Evolução do volume de decisões
          </h2>
        </div>
        <p className="panorama__lead">
          Selecione um ponto do gráfico para consultar os documentos do período. Os tribunais têm
          janelas de cobertura diferentes; ausência de decisões no período não significa ausência de
          atividade do tribunal.
        </p>
      </header>
      <article
        className="panorama-card temporal-volume__card"
        aria-label="Volume ao longo do tempo"
        aria-busy={loading}
      >
        <div className="panorama-card__body">
          {timeline.status === 'idle' && (
            <p className="panorama-card__message">
              Pesquise um tema para ver a evolução do volume de decisões.
            </p>
          )}
          {loading && (
            <p className="panorama-card__message" role="status">
              Carregando o volume ao longo do tempo...
            </p>
          )}
          {timeline.status === 'failed' && (
            <div className="search-state search-state--error panorama-card__error" role="alert">
              <p>Não foi possível carregar o volume ao longo do tempo.</p>
              <button
                type="button"
                className="search-state__retry"
                aria-label="Tentar novamente o gráfico temporal"
                onClick={onRetry}
              >
                Tentar novamente
              </button>
            </div>
          )}
          {empty && (
            <p className="panorama-card__message">
              Nenhum dado temporal encontrado para os filtros aplicados. Revise os termos ou amplie
              o período.
            </p>
          )}
          {volume && !empty && (
            <>
              {volume.periods.length === 1 && (
                <p className="sr-only" role="status">
                  O recorte contém um único período.
                </p>
              )}
              <Suspense fallback={<p role="status">Carregando gráfico temporal...</p>}>
                <TimelineChart
                  periods={volume.periods}
                  granularity={volume.granularity}
                  showValues={false}
                  height={330}
                  selectionDisabled={selectionDisabled}
                  onSelectPeriod={
                    onSelectPeriod && volume.granularity
                      ? (period) => {
                          const point = volume.periods.find((item) => item.period === period);
                          if (
                            point?.decisions !== null &&
                            point?.decisions !== undefined &&
                            volume.granularity
                          )
                            onSelectPeriod(period, volume.granularity, point.decisions);
                        }
                      : undefined
                  }
                />
              </Suspense>
            </>
          )}
        </div>
      </article>
    </section>
  );
}
