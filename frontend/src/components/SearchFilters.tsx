import { useEffect, useState } from 'react';
import { Check } from '@phosphor-icons/react';

import { listCourts, type Court } from '../api/courts';
import type { FilterErrors, SearchFilterValues } from '../search/filters';

// Chrome does not submit a form on Enter from a date input, and the search
// button sits above the panel. Without this, applying from the keyboard means
// tabbing back through every field.
function submitOnEnter(event: React.KeyboardEvent<HTMLInputElement>) {
  if (event.key === 'Enter') {
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }
}

type DateRangeGroupProps = {
  id: string;
  legend: string;
  note: string;
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
  error?: string;
  disabled: boolean;
};

function DateRangeGroup({
  id,
  legend,
  note,
  from,
  to,
  onChange,
  error,
  disabled,
}: DateRangeGroupProps) {
  const noteId = `${id}-note`;
  const errorId = `${id}-error`;
  const describedBy = error ? `${errorId} ${noteId}` : noteId;

  return (
    <fieldset
      className={error ? 'date-group date-group--invalid' : 'date-group'}
      disabled={disabled}
    >
      <legend className="date-group__legend">{legend}</legend>

      <div className="date-range">
        <div className="date-field">
          <label htmlFor={`${id}-from`}>De</label>
          <input
            id={`${id}-from`}
            type="date"
            value={from}
            onChange={(event) => onChange(event.target.value, to)}
            onKeyDown={submitOnEnter}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
          />
        </div>

        <div className="date-field">
          <label htmlFor={`${id}-to`}>Até</label>
          <input
            id={`${id}-to`}
            type="date"
            value={to}
            onChange={(event) => onChange(from, event.target.value)}
            onKeyDown={submitOnEnter}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
          />
        </div>
      </div>

      {error && (
        <p className="date-group__error" id={errorId} role="alert">
          {error}
        </p>
      )}

      <p className="date-group__note" id={noteId}>
        {note}
      </p>
    </fieldset>
  );
}

type CourtsState =
  { status: 'loading' } | { status: 'loaded'; courts: Court[] } | { status: 'failed' };

type SearchFiltersProps = {
  id: string;
  values: SearchFilterValues;
  onChange: (values: SearchFilterValues) => void;
  errors?: FilterErrors;
  hidden: boolean;
  disabled?: boolean;
};

function SearchFilters({
  id,
  values,
  onChange,
  errors = {},
  hidden,
  disabled = false,
}: SearchFiltersProps) {
  const [courtsState, setCourtsState] = useState<CourtsState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;

    listCourts().then(
      (courts) => {
        if (active) {
          setCourtsState({ status: 'loaded', courts });
        }
      },
      () => {
        if (active) {
          setCourtsState({ status: 'failed' });
        }
      },
    );

    return () => {
      active = false;
    };
  }, [attempt]);

  const retry = () => {
    setCourtsState({ status: 'loading' });
    setAttempt((current) => current + 1);
  };

  const toggleCourt = (abbreviation: string) => {
    const courts = values.courts.includes(abbreviation)
      ? values.courts.filter((selected) => selected !== abbreviation)
      : [...values.courts, abbreviation];

    onChange({ ...values, courts });
  };

  const courtsHint = `${id}-courts-hint`;

  return (
    <section id={id} className="search-filters" aria-label="Filtros da pesquisa" hidden={hidden}>
      <fieldset className="search-filters__group" disabled={disabled}>
        <legend className="search-filters__legend">Tribunais</legend>
        <p className="sr-only" id={courtsHint}>
          Nenhum marcado: a pesquisa inclui todos os tribunais.
        </p>

        {courtsState.status === 'loading' && (
          <p className="filter-state" role="status">
            Carregando tribunais...
          </p>
        )}

        {courtsState.status === 'failed' && (
          <div className="filter-state filter-state--error" role="alert">
            <p>Não foi possível carregar a lista de tribunais.</p>
            {values.courts.length > 0 && (
              <p>Sua seleção foi mantida: {values.courts.join(', ')}.</p>
            )}
            <button type="button" className="search-state__retry" onClick={retry}>
              Tentar novamente
            </button>
          </div>
        )}

        {courtsState.status === 'loaded' && courtsState.courts.length === 0 && (
          <p className="filter-state">Nenhum tribunal com decisões disponível no momento.</p>
        )}

        {courtsState.status === 'loaded' && courtsState.courts.length > 0 && (
          <div className="court-options" aria-describedby={courtsHint}>
            {courtsState.courts.map((court) => (
              <label key={court.abbreviation} className="court-option" title={court.name}>
                <input
                  type="checkbox"
                  className="court-option__input"
                  checked={values.courts.includes(court.abbreviation)}
                  onChange={() => toggleCourt(court.abbreviation)}
                />
                <span className="court-option__body">
                  <Check
                    className="court-option__check"
                    size={13}
                    weight="bold"
                    aria-hidden="true"
                  />
                  <span>{court.abbreviation}</span>
                  <span className="sr-only"> — {court.name}</span>
                </span>
              </label>
            ))}
          </div>
        )}
      </fieldset>

      <div className="date-groups">
        <DateRangeGroup
          id={`${id}-judged`}
          legend="Data de julgamento"
          note="Sem data de julgamento registrada, vale a de publicação."
          from={values.dateFrom}
          to={values.dateTo}
          onChange={(dateFrom, dateTo) => onChange({ ...values, dateFrom, dateTo })}
          error={errors.judged}
          disabled={disabled}
        />

        <DateRangeGroup
          id={`${id}-published`}
          legend="Data de publicação (opcional)"
          note="Decisões sem data de publicação registrada ficam de fora."
          from={values.publishedFrom}
          to={values.publishedTo}
          onChange={(publishedFrom, publishedTo) =>
            onChange({ ...values, publishedFrom, publishedTo })
          }
          error={errors.published}
          disabled={disabled}
        />
      </div>
    </section>
  );
}

export default SearchFilters;
