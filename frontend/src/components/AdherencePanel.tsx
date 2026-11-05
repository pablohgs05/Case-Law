import { Info, Robot } from '@phosphor-icons/react';

import AdherenceChart from './AdherenceChart';
import { formatCount } from './coverageFormat';
import {
  adherenceLabel,
  percent,
  precedentName,
  rankAdherences,
  type AdherenceState,
  type MostCitedState,
} from './precedentFormat';

const plural = (count: number, one: string, many: string) =>
  `${formatCount(count)} ${count === 1 ? one : many}`;

/**
 * How the cut used the precedents it cites.
 *
 * Four states have to stay apart, and the last two look alike without being
 * alike: nothing matched the search, against decisions that matched and cite
 * no precedent, against citations whose wording settled nothing. Collapsing
 * any pair of them turns the indicator into a claim it cannot support.
 */
function message(state: AdherenceState): string | null {
  switch (state.status) {
    case 'idle':
      return 'Pesquise um tema para ver como esses acórdãos usaram os precedentes que citam.';
    case 'failed':
      return state.message;
    case 'loaded': {
      const { decisions, citing, determined } = state.adherence;
      if (decisions === 0) {
        return 'Nenhuma decisão encontrada para os filtros aplicados. Ajuste os termos ou amplie o período.';
      }
      if (!citing) {
        return 'Nenhuma decisão deste recorte cita súmula ou tema. A maior parte do acervo não cita.';
      }
      if (!determined) {
        return 'As decisões do recorte citam precedentes, mas a redação não permitiu determinar como os usaram em nenhuma delas.';
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
      {['62%', '20%', '12%', '6%'].map((width) => (
        <span key={width} className="volume-skeleton__bar" style={{ width }} />
      ))}
      <span className="sr-only">Carregando a aderência aos precedentes</span>
    </div>
  );
}

type AdherencePanelProps = {
  adherence: AdherenceState;
  mostCited: MostCitedState;
  onRetry: () => void;
};

function AdherencePanel({ adherence, mostCited, onRetry }: AdherencePanelProps) {
  const loading = adherence.status === 'loading';
  const note = message(adherence);
  const share = adherence.status === 'loaded' ? adherence.adherence : null;
  const rows = share && !note ? rankAdherences(share.adherences) : null;
  const ranked = mostCited.status === 'loaded' ? mostCited.precedents : [];

  return (
    <section className="panorama" aria-labelledby="adherence-title">
      <header className="panorama__header">
        <div>
          <p className="panorama__eyebrow">Indicador explicável</p>
          <h2 id="adherence-title" className="panorama__title">
            Esses acórdãos seguiram os precedentes que citam?
          </h2>
        </div>
        <p className="panorama__lead">
          A aderência usa os mesmos termos, tribunais e períodos da lista.
        </p>
      </header>

      <div className="panorama__grid">
        <article
          className="panorama-card"
          aria-labelledby="adherence-card-title"
          aria-busy={loading}
        >
          <header className="panorama-card__header">
            <h3 id="adherence-card-title" className="panorama-card__title">
              Uso dos precedentes citados
            </h3>
          </header>

          <div className="panorama-card__body">
            {/* The three denominators, above the percentages and without any
                interaction: most decisions cite nothing, so a share of the
                citations reads as a share of the cut unless all three are
                there to be seen at once. */}
            {share && adherence.status === 'loaded' && (
              <ol className="denominators">
                <li className="denominators__item">
                  <span className="denominators__value">{formatCount(share.decisions ?? 0)}</span>
                  <span className="denominators__label">
                    {share.decisions === 1 ? 'decisão no recorte' : 'decisões no recorte'}
                  </span>
                </li>
                <li className="denominators__item">
                  <span className="denominators__value">{formatCount(share.citing ?? 0)}</span>
                  <span className="denominators__label">citam algum precedente</span>
                </li>
                <li className="denominators__item denominators__item--base">
                  <span className="denominators__value">{formatCount(share.determined ?? 0)}</span>
                  <span className="denominators__label">
                    citações com uso determinado
                    <span className="denominators__rest">
                      {' · '}
                      {plural(share.undetermined ?? 0, 'indeterminada', 'indeterminadas')}
                    </span>
                  </span>
                </li>
              </ol>
            )}

            {loading && <Skeleton />}
            {note && adherence.status === 'failed' ? (
              <div className="search-state search-state--error panorama-card__error" role="alert">
                <p>{note}</p>
                <button type="button" className="search-state__retry" onClick={onRetry}>
                  Tentar novamente
                </button>
              </div>
            ) : (
              note && <p className="panorama-card__message">{note}</p>
            )}

            {rows && <AdherenceChart adherences={rows} />}

            {rows && (
              <ol className="outcome-list">
                {rows.map((row) => (
                  <li key={row.adherence} className="outcome-list__item">
                    <span className="outcome-list__label">
                      <span className="outcome-list__swatch" data-adherence={row.adherence} />
                      {adherenceLabel(row.adherence)}
                    </span>
                    <span className="outcome-list__share">
                      {row.share === null ? '—' : percent(row.share)}
                    </span>
                    <span className="outcome-list__count">
                      {formatCount(row.links ?? 0)}
                      <span className="sr-only">{row.links === 1 ? ' citação' : ' citações'}</span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <footer className="volume-card__footer">
            <p className="volume-card__note">
              <Robot size={13} aria-hidden="true" />O uso é lido automaticamente das palavras ao
              redor da citação. O acórdão é a fonte; este rótulo é leitura da ferramenta.
            </p>
          </footer>
        </article>

        <article className="panorama-card" aria-labelledby="most-cited-title">
          <header className="panorama-card__header">
            <h3 id="most-cited-title" className="panorama-card__title">
              Precedentes mais citados
            </h3>
          </header>

          <div className="panorama-card__body">
            {mostCited.status === 'loading' && <Skeleton />}
            {mostCited.status === 'failed' && (
              <p className="panorama-card__message">{mostCited.message}</p>
            )}
            {mostCited.status === 'loaded' && ranked.length === 0 && (
              <p className="panorama-card__message">
                Nenhum precedente citado nas decisões deste recorte.
              </p>
            )}

            {ranked.length > 0 && (
              <ol className="most-cited">
                {ranked.map((row) => (
                  <li key={`${row.court}-${row.kind}-${row.number}`} className="most-cited__item">
                    <p className="most-cited__name">{precedentName(row)}</p>
                    {row.text ? (
                      <p className="most-cited__text">{row.text}</p>
                    ) : (
                      <p className="most-cited__text most-cited__text--missing">
                        Enunciado fora do acervo.
                      </p>
                    )}
                    <p className="most-cited__count">
                      {plural(row.citations ?? 0, 'citação', 'citações')}
                      {row.decisions !== null && (
                        <span className="most-cited__decisions">
                          {' · '}
                          {plural(row.decisions, 'decisão', 'decisões')}
                        </span>
                      )}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <footer className="volume-card__footer">
            <p className="volume-card__note">
              <Info size={13} aria-hidden="true" />
              Uma decisão pode citar o mesmo precedente mais de uma vez, por isso as citações passam
              das decisões.
            </p>
          </footer>
        </article>
      </div>
    </section>
  );
}

export default AdherencePanel;
