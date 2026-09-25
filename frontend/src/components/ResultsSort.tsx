import type { SearchOrder } from '../api/search';

type ResultsSortProps = {
  value: SearchOrder;
  onChange: (order: SearchOrder) => void;
  disabled?: boolean;
};

const OPTIONS: { value: SearchOrder; label: string }[] = [
  { value: 'relevance', label: 'Relevância' },
  { value: 'date', label: 'Mais recentes' },
];

const HINT_ID = 'results-sort-hint';

// A native select: the chosen option is always the one showing, and the
// keyboard, the label and screen readers work as they do everywhere else.
function ResultsSort({ value, onChange, disabled = false }: ResultsSortProps) {
  return (
    <div className="results-sort">
      <label className="results-sort__label" htmlFor="results-sort">
        Ordenar por
      </label>
      <select
        id="results-sort"
        className="results-sort__select"
        value={value}
        onChange={(event) => onChange(event.target.value as SearchOrder)}
        disabled={disabled}
        aria-describedby={HINT_ID}
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {/* What "Mais recentes" sorts by, for whoever reads it aloud. */}
      <span id={HINT_ID} className="sr-only">
        Mais recentes ordena pela data do julgamento, ou da publicação quando o tribunal não
        registrou o julgamento.
      </span>
    </div>
  );
}

export default ResultsSort;
