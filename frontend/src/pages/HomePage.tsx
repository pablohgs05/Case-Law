import { useContext, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useMatch, useNavigate } from 'react-router-dom';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import {
  DEFAULT_ORDER,
  SearchRequestError,
  type SearchDecisionMatch,
  type SearchOrder,
} from '../api/search';
import DecisionDetail from '../components/DecisionDetail';
import DecisionResultCard from '../components/DecisionResultCard';
import ResultsPagination from '../components/ResultsPagination';
import ResultsSort from '../components/ResultsSort';
import CourtVolumePanel from '../components/CourtVolumePanel';
import OutcomeSharePanel from '../components/OutcomeSharePanel';
import TimelineVolumePanel, { type TimelineState } from '../components/TimelineVolumePanel';
import IndicatorDocumentsDrawer from '../components/IndicatorDocumentsDrawer';
import PanoramaLayout from '../components/PanoramaLayout';
import {
  selectIndicator,
  type IndicatorPoint,
  type IndicatorSelection,
} from '../search/indicatorSelection';
import ResultsTabs from '../components/ResultsTabs';
import { panelId, tabId, type ResultsView } from '../components/resultsView';
import SearchFilters from '../components/SearchFilters';
import type { OutcomeState } from '../components/outcomeFormat';
import type { LastUpdateState, VolumeState } from '../components/volumeFormat';
import {
  getLastUpdate,
  getOutcomeShare,
  getVolumeByCourt,
  getVolumeByPeriod,
  type VolumeParams,
} from '../api/indicators';
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
import type { PageInfo } from '../search/paging';
import { HeaderSearchSlot } from '../search/headerSearchSlot';
import { fetchPage, heldPage, prefetchAfter, resetBuffer } from '../search/resultsBuffer';
import { useCourts } from '../search/useCourts';
import { useFilterOptions } from '../search/useFilterOptions';
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

// What the results on screen were searched with: the expression, the filters,
// the order and the page, applied together. Changing the order or the page
// searches this again, never whatever is being edited in the box or the panel
// and not yet applied
type AppliedSearch = {
  q: string;
  filters: SearchFilterValues;
  order: SearchOrder;
  page: number;
};

// The one place a request is built from the applied search. Another page is
// another page of this same search — same expression, filters, order and page
// size — so a page can never be read in a different cut than the first.
const requestFor = (search: AppliedSearch) => ({
  ...toSearchParams(search.q, search.filters),
  page: search.page,
  order: search.order,
});

// The cut the panorama counts: the applied expression and filters, built by the
// same function as the search, without the page, its size or the order. Those
// only arrange the list, so changing them leaves the counts as they were.
const volumeFor = (search: AppliedSearch): VolumeParams => {
  const params = toSearchParams(search.q, search.filters);
  return {
    q: params.q,
    tribunal: params.tribunal,
    orgao_julgador: params.orgao_julgador,
    relator: params.relator,
    classe_cnj: params.classe_cnj,
    date_from: params.date_from,
    date_to: params.date_to,
    published_from: params.published_from,
    published_to: params.published_to,
  };
};

// Every parameter that defines the set, and only those. The courts are a set,
// so the order they were ticked in does not make a different cut.
const volumeKey = (params: VolumeParams) =>
  JSON.stringify({ ...params, tribunal: params.tribunal && [...params.tribunal].sort() });

// A counted cut, kept under the key of the cut it counts.
type PanoramaCache = {
  key: string;
  volume: VolumeState;
  outcome: OutcomeState;
  timeline: TimelineState;
} | null;

function volumeFailure(error: unknown): string {
  if (error instanceof SearchRequestError) {
    if (errorsFromApi(error.status, error.detail)) {
      return 'A busca recusou um dos períodos. Revise as datas destacadas nos filtros.';
    }
    if (error.status === 422) {
      return 'Um dos filtros tem um valor que a busca não aceita. Revise-o e tente novamente.';
    }
  }
  return 'Não foi possível carregar o volume por tribunal. Tente novamente.';
}

function HomePage() {
  // Everything the reader would lose by leaving and coming back lives in the
  // search session, above the routes: the list can unmount and still come back
  // as it was, with no new request. Only what belongs to this one render — the
  // form element — stays local.
  const [value, setValue] = useSessionState('value', 'prescrição intercorrente em execução fiscal');
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
  // Which view of the applied search is up. In the session, so it is still the
  // one chosen after a decision or the coverage page is left.
  const [view, setView] = useSessionState<ResultsView>('view', 'documents');
  const [isLoading, setIsLoading] = useSessionState('isLoading', false);
  const [errorMessage, setErrorMessage] = useSessionState<string | null>('errorMessage', null);
  const [results, setResults] = useSessionState<SearchDecisionMatch[]>('results', []);
  const [totalResults, setTotalResults] = useSessionState<number | null>('totalResults', null);
  // Where the page on screen sits in the total, as the API answered it. Null
  // while a page loads or after one failed: no range is shown that was not read.
  const [pageInfo, setPageInfo] = useSessionState<PageInfo | null>('pageInfo', null);
  const formRef = useRef<HTMLFormElement>(null);
  const [indicatorSelection, setIndicatorSelection] = useSessionState<IndicatorSelection | null>(
    'indicatorSelection',
    null,
  );
  const [indicatorTrigger, setIndicatorTrigger] = useState<HTMLElement | SVGElement | null>(null);
  const openIndicator = (point: IndicatorPoint) => {
    if (!applied || indicatorOpen || isLoading) return;
    resetBuffer();
    setIndicatorTrigger(
      document.activeElement instanceof HTMLElement || document.activeElement instanceof SVGElement
        ? document.activeElement
        : null,
    );
    setIndicatorSelection(
      selectIndicator(requestFor(applied), point, {
        total: totalResults ?? 0,
        filterCount: countFilters(applied.filters),
      }),
    );
    navigate(
      { pathname: location.pathname, search: location.search },
      { state: { ...location.state, indicatorDocuments: true } },
    );
  };
  // Only the most recent search may write to the screen. An answer that
  // arrives after a newer search, or a newer order, started is dropped.
  const { startSearch, isLatestSearch } = useSearchSession();
  const navigate = useNavigate();
  const location = useLocation();
  const indicatorOpen =
    (location.state as { indicatorDocuments?: boolean } | null)?.indicatorDocuments === true;
  const closeIndicator = () => navigate(-1);

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

  // Keyed by text, not by the decision object, which is a new one on every
  // render.
  const chosenKey = chosenDecision ? keyOf(chosenDecision) : null;

  // A decision's address is read in the documents: arriving at one — from a
  // link, or Back and Forward — shows them, whichever view was up before.
  useEffect(() => {
    if (chosenKey !== null) {
      setView('documents');
    }
  }, [chosenKey, setView]);

  // Back on the list's address, focus returns to the card that was read, so a
  // keyboard reader carries on from where they were.
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
  const appliedCount =
    (appliedFilters ? countFilters(appliedFilters) : 0) +
    (indicatorOpen && indicatorSelection?.contextActive ? 1 : 0);
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
    // A new search, order or page is a new list: back to the list's address, so
    // the decision from the old list never sits beside the new one. Reached
    // from the list, that address is the entry just before — returning to it,
    // rather than turning the decision's entry into a second copy of it, leaves
    // no Back that goes nowhere. Opened from a link, there is none: in place.
    if (chosenDecision) {
      if (cameFromResults) {
        navigate(-1);
      } else {
        navigate({ pathname: '/', search: location.search }, { replace: true });
      }
    }
    // A page whose block was already fetched is shown as it is: emptying the
    // list first would blink it away and back for an answer already in hand.
    const inHand = heldPage(requestFor(search));

    if (inHand) {
      setErrorMessage(null);
      setTotalResults(inHand.total);
      setResults(inHand.results);
      setPageInfo({
        page: inHand.page,
        pageSize: inHand.page_size,
        total: inHand.total,
        count: inHand.results.length,
        rangeFrom: inHand.range_from,
        rangeTo: inHand.range_to,
      });
      prefetchAfter(requestFor(search), inHand.total);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    // Nothing from the previous answer stays up while the new one loads, so
    // old results never pass for the new filters or the new order.
    setTotalResults(null);
    setResults([]);
    setPageInfo(null);

    try {
      const response = await fetchPage(requestFor(search));

      if (!isLatestSearch(searchId)) {
        return;
      }

      prefetchAfter(requestFor(search), response.total);

      // As in the reference, the first result shows beside the list as soon as
      // the list does — without taking the list's address from it.
      setTotalResults(response.total);
      setResults(response.results);
      setPageInfo({
        page: response.page,
        pageSize: response.page_size,
        total: response.total,
        count: response.results.length,
        rangeFrom: response.range_from,
        rangeTo: response.range_to,
      });

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
    resetBuffer();
    // A new expression or new filters keep the order already chosen, and start
    // on the first page.
    void runSearch({
      q: trimmedValue,
      filters: filterDraft,
      order: applied?.order ?? DEFAULT_ORDER,
      page: 1,
    });
  };

  const changeOrder = (order: SearchOrder) => {
    // Choosing the order already applied asks the API for nothing.
    if (!applied || order === applied.order) {
      return;
    }

    // Another order is another list: it starts on its first page.
    resetBuffer();
    void runSearch({ ...applied, order, page: 1 }, 'Não foi possível reordenar os resultados.');
  };

  // Once another page arrives, the reader is taken to its first result, not
  // left on a button at the foot of a list that changed.
  const toPageStart = useRef(false);

  // Only the page changes: the expression, filters and order are the applied
  // ones, never an edit left in the box or the panel. Ignored while a page is
  // loading, so repeated clicks ask for nothing more.
  const goToPage = (page: number) => {
    if (!applied || isLoading || page < 1 || page === applied.page) {
      return;
    }

    toPageStart.current = true;
    void runSearch({ ...applied, page }, `Não foi possível carregar a página ${page}.`);
  };

  // Keyed by text, as above: the result object is a new one on every answer.
  const firstOpener = firstResult ? openButtonId(firstResult) : null;
  useEffect(() => {
    if (!isLoading && toPageStart.current) {
      toPageStart.current = false;
      const opener = firstOpener ? document.getElementById(firstOpener) : null;
      opener?.scrollIntoView({ block: 'nearest' });
      opener?.focus();
    }
  }, [firstOpener, isLoading]);

  // The panorama counts the applied cut, in the session so switching views or
  // leaving the screen does not ask again. The base's freshness is kept beside
  // it: one date for every cut.
  const [panorama, setPanorama] = useSessionState<PanoramaCache>('panorama', null);
  const [lastUpdate, setLastUpdate] = useSessionState<LastUpdateState | null>('lastUpdate', null);
  const cutKey = applied ? volumeKey(volumeFor(applied)) : null;
  const panoramaKey = panorama?.timeline ? panorama.key : null;

  // Asked when the panorama is up and what it holds is not this cut: a new
  // expression or new filters, applied while it was up or before it opened.
  // An answer is written only if it is still for the cut on screen, so a late
  // one never replaces the counts of a newer search.
  useEffect(() => {
    if (view !== 'panorama' || !applied || cutKey === null || panoramaKey === cutKey) {
      return;
    }

    const key = cutKey;
    const settleVolume = (volume: VolumeState) =>
      setPanorama((current) => (current?.key === key ? { ...current, volume } : current));
    const settleOutcome = (outcome: OutcomeState) =>
      setPanorama((current) => (current?.key === key ? { ...current, outcome } : current));
    const settleTimeline = (timeline: TimelineState) =>
      setPanorama((current) => (current?.key === key ? { ...current, timeline } : current));

    setPanorama({
      key,
      volume: { status: 'loading' },
      outcome: { status: 'loading' },
      timeline: { status: 'loading' },
    });
    getVolumeByPeriod(volumeFor(applied)).then(
      (volume) => settleTimeline({ status: 'loaded', volume }),
      () => settleTimeline({ status: 'failed' }),
    );
    getVolumeByCourt(volumeFor(applied)).then(
      (volume) => settleVolume({ status: 'loaded', volume }),
      (error: unknown) => settleVolume({ status: 'failed', message: volumeFailure(error) }),
    );

    // The same cut, asked of the same builder, so the two indicators can never
    // describe different sets.
    getOutcomeShare(volumeFor(applied)).then(
      (outcome) => settleOutcome({ status: 'loaded', outcome }),
      (error: unknown) => settleOutcome({ status: 'failed', message: volumeFailure(error) }),
    );

    // Read again with each cut, so the date shown is the one the counts were
    // read against — never the time of the request.
    getLastUpdate().then(
      (update) => setLastUpdate({ status: 'loaded', lastUpdate: update }),
      () => setLastUpdate({ status: 'unavailable' }),
    );
  }, [view, applied, cutKey, panoramaKey, setPanorama, setLastUpdate]);

  // Before any search there is no cut, but the base still has a date.
  useEffect(() => {
    if (view === 'panorama' && lastUpdate === null) {
      setLastUpdate({ status: 'loading' });
      getLastUpdate().then(
        (update) => setLastUpdate({ status: 'loaded', lastUpdate: update }),
        () => setLastUpdate({ status: 'unavailable' }),
      );
    }
  }, [view, lastUpdate, setLastUpdate]);

  // Held counts of another cut are never shown for this one: until this cut's
  // answer arrives, the panorama is loading.
  const volumeState: VolumeState =
    cutKey === null
      ? { status: 'idle' }
      : panorama?.key === cutKey
        ? panorama.volume
        : { status: 'loading' };
  const outcomeState: OutcomeState =
    cutKey === null
      ? { status: 'idle' }
      : panorama?.key === cutKey
        ? panorama.outcome
        : { status: 'loading' };
  const lastUpdateState: LastUpdateState = lastUpdate ?? { status: 'loading' };
  const timelineState: TimelineState =
    cutKey === null
      ? { status: 'idle' }
      : panorama?.key === cutKey && panorama.timeline
        ? panorama.timeline
        : { status: 'loading' };

  const retryPanorama = () => {
    setPanorama(null);
    setLastUpdate((current) => (current?.status === 'unavailable' ? null : current));
  };

  // Where the page on screen starts in the whole result, for the numbers the
  // list shows beside each decision.
  const firstRank = pageInfo
    ? (pageInfo.rangeFrom ?? (pageInfo.page - 1) * pageInfo.pageSize + 1)
    : 1;

  // Retries what failed — the applied search — not an edit left in the box or
  // the panel.
  const retry = () => {
    if (applied) {
      void runSearch(applied);
    } else {
      handleSubmit();
    }
  };

  // The search sits in the top bar, which is above the routes; it is
  // rendered there from here, where its state lives. With no bar to hold it,
  // it stays in the screen.
  const searchSlot = useContext(HeaderSearchSlot);
  const courts = useCourts();
  const filterOptions = useFilterOptions();
  const activeOptions =
    filterOptions.state.status === 'loaded' ? filterOptions.state.options : null;
  const activeTags = applied
    ? [
        ...applied.filters.judgingBodies.map((value) => ({
          field: 'judgingBodies',
          value,
          label: `Órgão julgador: ${value}`,
        })),
        ...applied.filters.reportingJudges.map((value) => ({
          field: 'reportingJudges',
          value,
          label: `Relator: ${value}`,
        })),
        ...applied.filters.proceduralClasses.map((value) => ({
          field: 'proceduralClasses',
          value,
          label: `Classe processual: ${activeOptions?.procedural_classes.find((option) => option.value === value)?.label ?? value}`,
        })),
      ]
    : [];
  const removeActiveFilter = (field: string, value: string | number) => {
    if (!applied) return;
    const remove = (filters: SearchFilterValues): SearchFilterValues => ({
      ...filters,
      judgingBodies: filters.judgingBodies.filter(
        (item) => field !== 'judgingBodies' || item !== value,
      ),
      reportingJudges: filters.reportingJudges.filter(
        (item) => field !== 'reportingJudges' || item !== value,
      ),
      proceduralClasses: filters.proceduralClasses.filter(
        (item) => field !== 'proceduralClasses' || item !== value,
      ),
    });
    updateFilters(remove(filterDraft));
    resetBuffer();
    void runSearch({ ...applied, filters: remove(applied.filters), page: 1 });
  };
  const searchForm = (
    <form ref={formRef} className="search-form" onSubmit={handleSubmit} noValidate>
      <div className="legal-search">
        <div className="legal-search__field">
          <MagnifyingGlass size={18} aria-hidden="true" />

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
          <button
            type="button"
            className="filter-button"
            aria-expanded={filtersOpen}
            aria-controls={FILTERS_PANEL_ID}
            onClick={() => setFiltersOpen((open) => !open)}
            disabled={isLoading}
          >
            <SlidersHorizontal size={14} aria-hidden="true" />
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

      {/* Below the bar, over the screen, so opening them takes nothing
          from the list. */}
      <div className="search-form__drop">
        {/* Hidden rather than unmounted, so closing it keeps what was chosen. */}
        <SearchFilters
          id={FILTERS_PANEL_ID}
          values={filterDraft}
          onChange={updateFilters}
          errors={filterErrors}
          hidden={!filtersOpen}
          disabled={isLoading}
          courts={courts}
          filterOptions={filterOptions}
        />

        {/* The results below were searched with the applied filters, not with
            what the panel shows now. Said, so they are not read as the new cut. */}
        {hasPendingFilters && !isLoading && (
          <p className="filters-pending" role="status">
            Há alterações nos filtros que ainda não foram aplicadas. Clique em Pesquisar para
            aplicá-las.
          </p>
        )}
      </div>
    </form>
  );

  return (
    <main className="search-page">
      {searchSlot ? createPortal(searchForm, searchSlot) : searchForm}

      <ResultsTabs value={view} onChange={setView} />
      {activeTags.length > 0 && (
        <div className="filter-tags applied-filter-tags" aria-label="Filtros aplicados">
          {activeTags.map((tag) => (
            <button
              type="button"
              className="filter-tag"
              key={`${tag.field}-${tag.value}`}
              disabled={isLoading}
              aria-label={`Remover filtro ${tag.label}`}
              onClick={() => removeActiveFilter(tag.field, tag.value)}
            >
              {tag.label} ×
            </button>
          ))}
        </div>
      )}

      {/* The rest of the window. The page itself never scrolls: the list, the
          decision and the panorama each scroll inside their own box. */}
      <div className="search-content">
        {/* Always two columns, as in the reference: the list on the left, the
            decision on the right. Hidden rather than unmounted while the
            panorama is up, so the list, its page and the open decision are
            exactly as they were when the tab comes back. */}
        <div
          className="results-layout"
          role="tabpanel"
          id={panelId('documents')}
          aria-labelledby={tabId('documents')}
          hidden={view !== 'documents'}
        >
          <div className="results-column">
            {/* Beside the total and above the list. Kept up while a new order
                loads or fails, so it can be changed back or retried. Outside
                the live region below, so choosing an order is not read out as a
                new result. */}
            {applied && (
              <div className="results-toolbar">
                <h2 className="search-summary" aria-live="polite">
                  {!isLoading && totalResults !== null && (
                    <>
                      <span className="sr-only">Total de resultados:</span>
                      <strong>{totalResults}</strong> {totalResults === 1 ? 'decisão' : 'decisões'}
                    </>
                  )}
                </h2>
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
                  {results.map((result, index) => {
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
                          rank={firstRank + index}
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            {/* Under the list. Up while a later page loads, to say which, but
                never with a range before the API has answered one; gone when
                the page failed, so a failed page never reads as loaded. */}
            {applied && (pageInfo || (isLoading && applied.page > 1)) && (
              <ResultsPagination
                info={pageInfo}
                requestedPage={applied.page}
                loading={isLoading}
                onGo={goToPage}
              />
            )}
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
              // With a search, the list is beside the decision and is the way
              // back to it; the browser's Back still is too. Only a decision
              // opened from a link, with no list, offers the way to the search.
              back={
                chosenDecision && !hasSearch
                  ? { label: 'Ir para a busca', onClick: backToResults }
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

        {/* Focusable itself: the panorama holds no control until a count fails,
            and Tab from its tab must still reach what it says. */}
        <div
          className="results-panorama"
          role="tabpanel"
          id={panelId('panorama')}
          aria-labelledby={tabId('panorama')}
          hidden={view !== 'panorama'}
          tabIndex={0}
        >
          <PanoramaLayout
            courts={
              <CourtVolumePanel
                compact
                volume={volumeState}
                lastUpdate={lastUpdateState}
                onRetry={retryPanorama}
                selectionDisabled={isLoading || indicatorOpen}
                onSelectCourt={(court, count) => openIndicator({ kind: 'court', court, count })}
              />
            }
            temporal={
              <TimelineVolumePanel
                timeline={timelineState}
                onRetry={retryPanorama}
                selectionDisabled={isLoading || indicatorOpen}
                onSelectPeriod={(period, granularity, count) =>
                  openIndicator({ kind: 'period', period, granularity, count })
                }
              />
            }
            outcomes={
              <OutcomeSharePanel
                compact
                outcome={outcomeState}
                onRetry={retryPanorama}
                selectionDisabled={isLoading || indicatorOpen}
                onSelectOutcome={(outcome, count) =>
                  openIndicator({ kind: 'outcome', outcome, count })
                }
              />
            }
          />
        </div>
      </div>
      {indicatorOpen && indicatorSelection && (
        <IndicatorDocumentsDrawer
          selection={indicatorSelection}
          returnFocus={indicatorTrigger}
          onClose={closeIndicator}
          onRemoveSelection={() => {
            resetBuffer();
            setIndicatorSelection((current) =>
              current ? { ...current, contextActive: false } : null,
            );
          }}
        />
      )}
    </main>
  );
}

export default HomePage;
