import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, X } from '@phosphor-icons/react';
import { type SearchDecisionMatch, type SearchDecisionResponse } from '../api/search';
import { fetchPage, heldPage, prefetchAfter } from '../search/resultsBuffer';
import type { IndicatorSelection } from '../search/indicatorSelection';
import { formatCount } from './coverageFormat';
import DecisionResultCard from './DecisionResultCard';
import DecisionDetail from './DecisionDetail';
import ResultsPagination from './ResultsPagination';

type DocumentsState =
  | { status: 'loading' }
  | { status: 'failed' }
  | { status: 'loaded'; response: SearchDecisionResponse };

export default function IndicatorDocumentsDrawer({
  selection,
  onClose,
  returnFocus,
  onRemoveSelection,
}: {
  selection: IndicatorSelection;
  onClose: () => void;
  returnFocus: HTMLElement | SVGElement | null;
  onRemoveSelection: () => void;
}) {
  const params = selection.contextActive ? selection.params : selection.original;
  const expectedTotal = selection.contextActive ? selection.count : selection.originalTotal;
  const label = selection.contextActive ? selection.label : 'Pesquisa original';
  const dialog = useRef<HTMLDialogElement>(null);
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<DocumentsState>(() =>
    params
      ? { status: 'loading' }
      : { status: 'loaded', response: { total: 0, page: 1, page_size: 6, results: [] } },
  );
  const [chosen, setChosen] = useState<SearchDecisionMatch | null>(null);
  const content = useRef<HTMLDivElement>(null);
  const title = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusKey = returnFocus?.getAttribute('data-indicator-focus');
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      const restore = () => {
        // Recharts may replace a dot when its disabled state changes.
        const target = focusKey
          ? [...document.querySelectorAll<HTMLElement | SVGElement>('[data-indicator-focus]')].find(
              (item) => item.getAttribute('data-indicator-focus') === focusKey,
            )
          : returnFocus;
        target?.focus();
      };
      restore();
      if (focusKey) requestAnimationFrame(restore);
    };
  }, [returnFocus]);

  useEffect(() => {
    if (!params) return;
    let active = true;
    const request = { ...params, page };
    fetchPage(request).then(
      (response) => {
        if (active) {
          setState({ status: 'loaded', response });
          prefetchAfter(request, response.total);
        }
      },
      () => {
        if (active) setState({ status: 'failed' });
      },
    );
    return () => {
      active = false;
    };
  }, [params, page, attempt]);

  const retry = () => {
    setState({ status: 'loading' });
    setAttempt((value) => value + 1);
  };
  const go = (next: number) => {
    if (!params) return;
    const inHand = heldPage({ ...params, page: next });
    setState(inHand ? { status: 'loaded', response: inHand } : { status: 'loading' });
    setPage(next);
    content.current?.scrollTo?.({ top: 0 });
  };
  const response = state.status === 'loaded' ? state.response : null;
  const info = response
    ? {
        page: response.page,
        pageSize: response.page_size,
        total: response.total,
        count: response.results.length,
        rangeFrom: response.range_from,
        rangeTo: response.range_to,
      }
    : null;
  const total = formatCount(expectedTotal);
  const originalTags = [
    ...(selection.original.tribunal ?? []).map((value) => `Tribunal: ${value}`),
    ...(selection.original.orgao_julgador ?? []).map((value) => `Órgão julgador: ${value}`),
    ...(selection.original.relator ?? []).map((value) => `Relator: ${value}`),
    ...(selection.original.classe_cnj ?? []).map((value) => `Classe processual: ${value}`),
    ...(selection.original.resultado ?? []).map((value) => `Resultado: ${value}`),
    ...(selection.original.date_from || selection.original.date_to
      ? [
          `Período original: ${selection.original.date_from ?? 'início aberto'} a ${selection.original.date_to ?? 'fim aberto'}`,
        ]
      : []),
    ...(selection.original.published_from || selection.original.published_to
      ? [
          `Publicação: ${selection.original.published_from ?? 'início aberto'} a ${selection.original.published_to ?? 'fim aberto'}`,
        ]
      : []),
  ];
  const removeSelection = () => {
    setPage(1);
    setChosen(null);
    setState({ status: 'loading' });
    onRemoveSelection();
    title.current?.focus();
  };
  return createPortal(
    <dialog
      ref={dialog}
      className="indicator-drawer"
      aria-labelledby="indicator-documents-title"
      aria-modal="true"
      aria-describedby="indicator-documents-context"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="indicator-drawer__surface">
        <header className="indicator-drawer__header">
          <p className="panorama__eyebrow">Documentos do indicador</p>
          <button type="button" className="indicator-drawer__back" onClick={onClose}>
            <ArrowLeft size={16} aria-hidden="true" /> Voltar ao Panorama
          </button>
          <button
            type="button"
            className="indicator-drawer__close"
            aria-label="Fechar documentos e voltar ao Panorama"
            onClick={onClose}
            autoFocus
          >
            <X size={20} aria-hidden="true" />
          </button>
          <h2 id="indicator-documents-title" ref={title} tabIndex={-1}>
            {label}: {total} {expectedTotal === 1 ? 'decisão' : 'decisões'}
          </h2>
          <p id="indicator-documents-context">
            {selection.contextActive
              ? `Seleção “${selection.label}” na pesquisa “${selection.expression}”, mantendo os filtros aplicados.`
              : `Pesquisa “${selection.expression}” com os filtros originais, sem o recorte do indicador.`}
          </p>
          <div
            className="indicator-drawer__filters"
            role="group"
            aria-label="Filtros aplicados aos documentos"
          >
            <p>
              Filtros aplicados:{' '}
              <strong>{selection.filterCount + (selection.contextActive ? 1 : 0)}</strong>
            </p>
            <div className="filter-tags">
              {originalTags.map((tag, index) => (
                <span key={`${index}-${tag}`} className="filter-tag">
                  {tag}
                </span>
              ))}
              {selection.contextActive && (
                <button
                  type="button"
                  className="filter-tag"
                  aria-label={`Remover seleção do indicador ${selection.contextLabel}`}
                  onClick={removeSelection}
                >
                  {selection.contextLabel} <X size={12} aria-hidden="true" />
                </button>
              )}
            </div>
          </div>
        </header>
        <div className="indicator-drawer__content" ref={content}>
          {chosen ? (
            <DecisionDetail
              key={`${chosen.source}/${chosen.identifier}`}
              id="indicator-decision-detail"
              source={chosen.source}
              identifier={chosen.identifier}
              back={{
                label: 'Voltar aos documentos do indicador',
                onClick: () => {
                  setChosen(null);
                  title.current?.focus();
                },
              }}
            />
          ) : (
            <>
              <div className="indicator-drawer__total">
                <strong>{total}</strong>
                <span>
                  {selection.contextActive
                    ? expectedTotal === 1
                      ? 'decisão neste indicador'
                      : 'decisões neste indicador'
                    : expectedTotal === 1
                      ? 'decisão na pesquisa original'
                      : 'decisões na pesquisa original'}
                </span>
              </div>
              <div aria-busy={state.status === 'loading'}>
                {state.status === 'loading' && (
                  <p role="status">Carregando documentos do indicador...</p>
                )}
                {state.status === 'failed' && (
                  <div role="alert" className="search-state search-state--error">
                    <p>Não foi possível carregar os documentos deste indicador.</p>
                    <button type="button" className="search-state__retry" onClick={retry}>
                      Tentar novamente
                    </button>
                  </div>
                )}
                {response?.total === 0 && (
                  <p className="panorama-card__message">
                    Nenhum documento encontrado para esta seleção. Feche o painel e revise os
                    filtros da pesquisa.
                  </p>
                )}
                {response && selection.contextActive && response.total !== expectedTotal && (
                  <p role="status">
                    A consulta retornou {formatCount(response.total)} decisões; o indicador mostrava{' '}
                    {total}. A base pode ter sido atualizada. Feche o painel e atualize o Panorama
                    para conferir.
                  </p>
                )}
                {response && response.results.length > 0 && (
                  <ul className="indicator-drawer__documents">
                    {response.results.map((decision) => (
                      <li key={`${decision.source}/${decision.identifier}`}>
                        <DecisionResultCard
                          decision={decision}
                          onSelect={() => {
                            setChosen(decision);
                            title.current?.focus();
                            content.current?.scrollTo?.({ top: 0 });
                          }}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {((response && response.total > response.page_size) ||
                (state.status === 'loading' && page > 1)) && (
                <ResultsPagination
                  info={info}
                  requestedPage={page}
                  loading={state.status === 'loading'}
                  onGo={go}
                />
              )}
            </>
          )}
        </div>
      </div>
    </dialog>,
    document.body,
  );
}
