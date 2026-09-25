import { useEffect, useRef } from 'react';
import { useLocation, useMatch, useNavigate } from 'react-router-dom';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import {
  DEFAULT_ORDER,
  searchDecisions,
  SearchRequestError,
  type SearchDecisionMatch,
  type SearchOrder,
} from '../api/search';
import DecisionDetail from '../components/DecisionDetail';
import DecisionResultCard from '../components/DecisionResultCard';
import ResultsSort from '../components/ResultsSort';
import SearchFilters from '../components/SearchFilters';
import {
  countFilters,
  errorsFromApi,
  hasErrors,
  INCOMPLETE_DATE_MESSAGE,
  NO_FILTERS,
  rangeErrors,
  sameFilters,
  toSearchParams,
  type DateGroup,
  type FilterErrors,
  type SearchFilterValues,
} from '../search/filters';
import { useSearchSession, useSessionState } from '../search/session';

const FILTERS_PANEL_ID = 'search-filters';

const DATE_INPUTS: Record<DateGroup, string[]> = {
  judged: [`${FILTERS_PANEL_ID}-judged-from`, `${FILTERS_PANEL_ID}-judged-to`],
  published: [`${FILTERS_PANEL_ID}-published-from`, `${FILTERS_PANEL_ID}-published-to`],
};

// A half-typed date leaves the input's value empty, which would read as "no
// filter" and quietly widen the search. The browser still knows it is there.
function incompleteDates(form: HTMLFormElement | null): FilterErrors {
  const errors: FilterErrors = {};

  for (const [group, ids] of Object.entries(DATE_INPUTS) as [DateGroup, string[]][]) {
    const incomplete = ids.some((id) => {
      const input = form?.querySelector<HTMLInputElement>(`#${id}`);
      return input?.validity.badInput ?? false;
    });
    if (incomplete) {
      errors[group] = INCOMPLETE_DATE_MESSAGE;
    }
  }

  return errors;
}

const DETAIL_PANEL_ID = 'decision-detail';

// What the detail endpoint identifies a decision by. The case number is not
// enough: one case can have several decisions.
type OpenDecision = { source: string; identifier: string };

const keyOf = (decision: OpenDecision) => `${decision.source}/${decision.identifier}`;

// The address of a decision: the same two identifiers the detail endpoint
// takes, so a copied link reopens exactly this decision.
export const DETAIL_ROUTE = '/decisoes/:source/:identifier';

const detailPath = (decision: OpenDecision) =>
  `/decisoes/${encodeURIComponent(decision.source)}/${encodeURIComponent(decision.identifier)}`;

const openButtonId = (decision: OpenDecision) =>
  `open-${keyOf(decision).replace(/[^A-Za-z0-9_-]/g, '-')}`;

// Below this width the two columns stack, the detail under the list.
const STACKED = '(max-width: 1100px)';

const isStacked = () =>
  typeof window.matchMedia === 'function' && window.matchMedia(STACKED).matches;

// What the results on screen were searched with: the expression, the filters
// and the order, applied together. Changing the order searches this again,
// never whatever is being edited in the box or the panel and not yet applied.
type AppliedSearch = { q: string; filters: SearchFilterValues; order: SearchOrder };

// The one place a request is built from the applied search. Paging, when it
// comes, asks for another page of this same search — same expression, filters
// and order — so a page can never be read in a different order than the first.
const requestFor = (search: AppliedSearch, page = 1) => ({
  ...toSearchParams(search.q, search.filters),
  page,
  order: search.order,
});

function HomePage() {
  // Everything the reader would lose by leaving and coming back lives in the
  // search session, above the routes: the list can unmount and still come back
  // as it was, with no new request. Only what belongs to this one render — the
  // form element — stays local.
  const [value, setValue] = useSessionState('value', 'prescrição intercorrente em execução fiscal');
  const [mode, setMode] = useSessionState<'free' | 'exact'>('mode', 'free');
  // What the panel shows while it is being edited. A change here never starts a
  // search: only Pesquisar applies it.
  const [filterDraft, setFilterDraft] = useSessionState<SearchFilterValues>(
    'filterDraft',
    NO_FILTERS,
  );
  const [applied, setApplied] = useSessionState<AppliedSearch | null>('applied', null);
  // Errors found on submit — a half-typed date, or a range the API refused.
  // Backwards ranges are also found live, from the draft itself.
  const [submitErrors, setSubmitErrors] = useSessionState<FilterErrors>('submitErrors', {});
  const [filtersOpen, setFiltersOpen] = useSessionState('filtersOpen', false);
  const [isLoading, setIsLoading] = useSessionState('isLoading', false);
  const [errorMessage, setErrorMessage] = useSessionState<string | null>('errorMessage', null);
  const [results, setResults] = useSessionState<SearchDecisionMatch[]>('results', []);
  const [totalResults, setTotalResults] = useSessionState<number | null>('totalResults', null);
  const formRef = useRef<HTMLFormElement>(null);
  // Only the most recent search may write to the screen. An answer that
  // arrives after a newer search, or a newer order, started is dropped.
  const { startSearch, isLatestSearch } = useSearchSession();
  const navigate = useNavigate();
  const location = useLocation();

  // A decision the reader chose has its own address, so it can be copied,
  // opened in another tab or reloaded. Without one, the list's address shows
  // the first result, as the reference does, and stays the list's address:
  // coming back to it is coming back to the results.
  const match = useMatch(DETAIL_ROUTE);
  const chosenDecision: OpenDecision | null =
    match?.params.source && match.params.identifier
      ? { source: match.params.source, identifier: match.params.identifier }
      : null;
  const [firstResult] = results;
  const openDecision: OpenDecision | null =
    chosenDecision ??
    (firstResult ? { source: firstResult.source, identifier: firstResult.identifier } : null);

  // Reached from the list, the entry before this one is the list: going back
  // is going back in the history, and the browser's Back does the same. Opened
  // from a link, there is no list behind it — and the entry before may be
  // another site — so the way back is to the search, forward.
  const cameFromResults =
    (location.state as { fromResults?: boolean } | null)?.fromResults === true;
  const hasSearch = applied !== null;
  // Which card to return focus to once the list's address is back.
  const returnTo = useRef<OpenDecision | null>(null);

  const backToResults = () => {
    returnTo.current = chosenDecision;
    if (cameFromResults) {
      navigate(-1);
    } else {
      navigate({ pathname: '/', search: location.search });
    }
  };

  // Back on the list's address, focus returns to the card that was read, so a
  // keyboard reader carries on from where they were. Keyed by text, not by the
  // decision object, which is a new one on every render.
  const chosenKey = chosenDecision ? keyOf(chosenDecision) : null;
  useEffect(() => {
    if (chosenKey === null && returnTo.current) {
      const opener = document.getElementById(openButtonId(returnTo.current));
      opener?.scrollIntoView({ block: 'center' });
      opener?.focus();
      returnTo.current = null;
    }
  }, [chosenKey]);

  // What the results on screen were filtered with. Null before the first search.
  const appliedFilters = applied?.filters ?? null;

  // An error from submit wins over the live one, but only where there is one:
  // a period whose submit error was cleared still shows a backwards range.
  const liveErrors = rangeErrors(filterDraft);
  const filterErrors: FilterErrors = {
    judged: submitErrors.judged ?? liveErrors.judged,
    published: submitErrors.published ?? liveErrors.published,
  };
  const appliedCount = appliedFilters ? countFilters(appliedFilters) : 0;
  const hasPendingFilters = appliedFilters !== null && !sameFilters(filterDraft, appliedFilters);

  const updateFilters = (next: SearchFilterValues) => {
    // An error found on submit belongs to the dates as they were then; editing
    // that period clears it.
    setSubmitErrors((current) => ({
      judged:
        next.dateFrom === filterDraft.dateFrom && next.dateTo === filterDraft.dateTo
          ? current.judged
          : undefined,
      published:
        next.publishedFrom === filterDraft.publishedFrom &&
        next.publishedTo === filterDraft.publishedTo
          ? current.published
          : undefined,
    }));
    setFilterDraft(next);
  };

  // The result's link navigates; this only brings the panel into view when the
  // columns are stacked and it sits below the list, out of sight.
  const openDetail = () => {
    if (isStacked()) {
      requestAnimationFrame(() =>
        document.getElementById(DETAIL_PANEL_ID)?.scrollIntoView({ block: 'start' }),
      );
    }
  };

  // `failure`, when given, replaces the usual message: a failed reorder says so,
  // rather than reading like the search itself went wrong.
  const runSearch = async (search: AppliedSearch, failure?: string) => {
    const searchId = startSearch();

    setApplied(search);
    // A new search is a new list: back to the list's address, in place, so the
    // decision from the old list never sits beside the new one.
    if (chosenDecision) {
      navigate({ pathname: '/', search: location.search }, { replace: true });
    }
    setIsLoading(true);
    setErrorMessage(null);
    // Nothing from the previous answer stays up while the new one loads, so
    // old results never pass for the new filters or the new order.
    setTotalResults(null);
    setResults([]);

    try {
      // Every new search, filter or order starts on the first page.
      const response = await searchDecisions(requestFor(search));

      if (!isLatestSearch(searchId)) {
        return;
      }

      // As in the reference, the first result shows beside the list as soon as
      // the list does — without taking the list's address from it.
      setTotalResults(response.total);
      setResults(response.results);

      if (response.total === 0) {
        setErrorMessage(
          'Nenhuma decisão foi encontrada para esta expressão. Revise os termos ou tente uma sintaxe diferente.',
        );
      }
    } catch (requestError) {
      if (!isLatestSearch(searchId)) {
        return;
      }

      if (requestError instanceof SearchRequestError) {
        const refused = errorsFromApi(requestError.status, requestError.detail);

        if (refused) {
          setSubmitErrors(refused);
          setFiltersOpen(true);
          setErrorMessage(
            'A busca recusou um dos períodos. Revise as datas destacadas nos filtros.',
          );
          return;
        }

        if (requestError.status === 422) {
          setFiltersOpen(true);
          setErrorMessage(
            'Um dos filtros tem um valor que a busca não aceita. Revise as datas e tente novamente.',
          );
          return;
        }
      }

      const message =
        failure ??
        (requestError instanceof Error && requestError.message
          ? requestError.message
          : 'Não foi possível concluir a busca.');

      setErrorMessage(`${message} Tente novamente.`);
    } finally {
      if (isLatestSearch(searchId)) {
        setIsLoading(false);
      }
    }
  };

  const handleSubmit = (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();

    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setErrorMessage('Digite uma expressão para pesquisar.');
      return;
    }

    const blocking = { ...rangeErrors(filterDraft), ...incompleteDates(formRef.current) };

    if (hasErrors(blocking)) {
      setSubmitErrors(blocking);
      setFiltersOpen(true);
      return;
    }

    setSubmitErrors({});
    // A new expression or new filters keep the order already chosen.
    void runSearch({
      q: trimmedValue,
      filters: filterDraft,
      order: applied?.order ?? DEFAULT_ORDER,
    });
  };

  const changeOrder = (order: SearchOrder) => {
    // Choosing the order already applied asks the API for nothing.
    if (!applied || order === applied.order) {
      return;
    }

    void runSearch({ ...applied, order }, 'Não foi possível reordenar os resultados.');
  };

  // Retries what failed — the applied search — not an edit left in the box or
  // the panel.
  const retry = () => {
    if (applied) {
      void runSearch(applied);
    } else {
      handleSubmit();
    }
  };

  return (
    <main className="search-page">
      <div className="search-layout">
        <form ref={formRef} className="search-form" onSubmit={handleSubmit} noValidate>
          <div className="legal-search">
            <div className="legal-search__field">
              <MagnifyingGlass size={20} aria-hidden="true" />

              <label className="sr-only" htmlFor="legal-search-input">
                Pesquisar decisões
              </label>

              <input
                id="legal-search-input"
                type="search"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="Pesquise um assunto, fundamento ou frase exata"
                autoComplete="off"
                disabled={isLoading}
              />
            </div>

            <div className="legal-search__actions">
              <div className="search-mode" role="group" aria-label="Modalidade da pesquisa">
                <span
                  className="search-mode__indicator"
                  style={{
                    transform: mode === 'free' ? 'translateX(0%)' : 'translateX(100%)',
                  }}
                />

                <button
                  type="button"
                  className={mode === 'free' ? 'is-active' : ''}
                  aria-pressed={mode === 'free'}
                  onClick={() => setMode('free')}
                  disabled={isLoading}
                >
                  Termo livre
                </button>

                <button
                  type="button"
                  className={mode === 'exact' ? 'is-active' : ''}
                  aria-pressed={mode === 'exact'}
                  onClick={() => setMode('exact')}
                  disabled={isLoading}
                >
                  Frase exata
                </button>
              </div>

              <button
                type="button"
                className="filter-button"
                aria-expanded={filtersOpen}
                aria-controls={FILTERS_PANEL_ID}
                onClick={() => setFiltersOpen((open) => !open)}
                disabled={isLoading}
              >
                <SlidersHorizontal size={17} aria-hidden="true" />
                <span>Filtros</span>
                {appliedCount > 0 && (
                  <span className="filter-button__count">
                    {appliedCount}
                    <span className="sr-only"> aplicados</span>
                  </span>
                )}
              </button>

              <button type="submit" className="search-button" disabled={isLoading || !value.trim()}>
                {isLoading ? 'Pesquisando...' : 'Pesquisar'}
              </button>
            </div>
          </div>

          {/* Hidden rather than unmounted, so closing it keeps what was chosen. */}
          <SearchFilters
            id={FILTERS_PANEL_ID}
            values={filterDraft}
            onChange={updateFilters}
            errors={filterErrors}
            hidden={!filtersOpen}
            disabled={isLoading}
          />

          {/* The results below were searched with the applied filters, not with
              what the panel shows now. Said, so they are not read as the new cut. */}
          {hasPendingFilters && !isLoading && (
            <p className="filters-pending" role="status">
              Há alterações nos filtros que ainda não foram aplicadas. Clique em Pesquisar para
              aplicá-las.
            </p>
          )}
        </form>

        {/* Always two columns, as in the reference: the list on the left, the
            decision on the right. */}
        <div className="results-layout">
          <div className="results-column">
            {/* Beside the total and above the list. Kept up while a new order
                loads or fails, so it can be changed back or retried. Outside
                the live region below, so choosing an order is not read out as a
                new result. */}
            {applied && (
              <div className="results-toolbar">
                <div className="search-summary" aria-live="polite">
                  {!isLoading && totalResults !== null && (
                    <>
                      <span>Total de resultados:</span>
                      <strong>{totalResults}</strong>
                    </>
                  )}
                </div>
                <ResultsSort value={applied.order} onChange={changeOrder} disabled={isLoading} />
              </div>
            )}

            <section className="search-results" aria-live="polite">
              {isLoading && (
                <div className="search-state search-state--loading">Carregando resultados...</div>
              )}

              {!isLoading && !errorMessage && totalResults === 0 && (
                <div className="search-state search-state--empty">
                  Nenhuma decisão foi encontrada para esta expressão. Revise os termos ou tente uma
                  sintaxe diferente.
                </div>
              )}

              {!isLoading && errorMessage && (
                <div className="search-state search-state--error" role="alert">
                  <p>{errorMessage}</p>
                  <button type="button" className="search-state__retry" onClick={retry}>
                    Tentar novamente
                  </button>
                </div>
              )}

              {!isLoading && results.length > 0 && (
                <ul className="result-list">
                  {results.map((result) => {
                    const decision = { source: result.source, identifier: result.identifier };
                    const selected =
                      openDecision !== null && keyOf(openDecision) === keyOf(decision);

                    return (
                      <li key={`${result.source}-${result.identifier}`} className="result-item">
                        <DecisionResultCard
                          decision={result}
                          to={{ pathname: detailPath(decision), search: location.search }}
                          // From one chosen decision to another, the entry is
                          // replaced: going back always lands on the list.
                          replace={chosenDecision !== null}
                          state={{ fromResults: true }}
                          onOpen={openDetail}
                          openButtonId={openButtonId(decision)}
                          selected={selected}
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>

          {/* Outside the results' live region, so a screen reader is not read the
            whole ementa each time a decision opens. Keyed by the decision, so
            nothing from the previous one shows while the next loads. */}
          {openDecision ? (
            <DecisionDetail
              key={keyOf(openDecision)}
              id={DETAIL_PANEL_ID}
              source={openDecision.source}
              identifier={openDecision.identifier}
              // Only a decision with its own address has somewhere to go back
              // from; the first result shown beside the list is already there.
              back={
                chosenDecision
                  ? {
                      label: hasSearch ? 'Voltar aos resultados' : 'Ir para a busca',
                      onClick: backToResults,
                    }
                  : undefined
              }
            />
          ) : (
            <aside id={DETAIL_PANEL_ID} className="decision-detail decision-detail--empty">
              <p className="decision-detail__placeholder">
                {isLoading
                  ? 'Carregando resultados...'
                  : 'Pesquise e escolha uma decisão da lista para lê-la aqui.'}
              </p>
            </aside>
          )}
        </div>
      </div>
    </main>
  );
}

export default HomePage;
