import type { OutcomeCount } from '../api/indicators';
import { outcomeLabel, percent } from './outcomeFormat';
import { axisTicks } from './volumeFormat';
import { formatCount } from './coverageFormat';

const drawable = (row: OutcomeCount): row is OutcomeCount & { decisions: number } =>
  row.decisions !== null && row.decisions > 0;

// One bar, split in the order the panel ranked once for the list beside it, so
// the two can never disagree. Lengths are proportional to the counts, over the
// decisions that carry a reading — the same denominator the list states. The
// list carries every number as text, so the drawing is hidden from screen
// readers rather than read twice.
function OutcomeShareChart({
  outcomes,
  horizontal = false,
  onSelect,
  disabled = false,
}: {
  outcomes: OutcomeCount[];
  horizontal?: boolean;
  onSelect?: (outcome: string, count: number) => void;
  disabled?: boolean;
}) {
  const parts = outcomes.filter(drawable);
  const counted = parts.reduce((sum, row) => sum + row.decisions, 0);

  if (!counted) {
    return null;
  }

  if (horizontal) {
    const ticks = axisTicks(Math.max(...parts.map((row) => row.decisions)));
    const top = ticks[ticks.length - 1] || 1;
    return (
      <div className="outcome-horizontal">
        {outcomes.map((row) => (
          <button
            type="button"
            className="indicator-target indicator-target--outcome outcome-horizontal__row"
            key={row.outcome}
            disabled={disabled || row.decisions === null || !onSelect}
            aria-label={`Consultar documentos com resultado ${outcomeLabel(row.outcome)}: ${formatCount(row.decisions)} decisões`}
            onClick={() => row.decisions !== null && onSelect?.(row.outcome, row.decisions)}
          >
            <span className="outcome-horizontal__label">{outcomeLabel(row.outcome)}</span>
            <span className="outcome-horizontal__track" aria-hidden="true">
              <span className="outcome-horizontal__grid">
                {ticks.map((tick) => (
                  <span key={tick} style={{ left: `${(tick / top) * 100}%` }} />
                ))}
              </span>
              <span
                className="outcome-horizontal__bar"
                data-outcome={row.outcome}
                style={{ width: `${((row.decisions ?? 0) / top) * 100}%` }}
              />
              <span className="outcome-horizontal__value">
                {row.share === null ? '—' : percent(row.share)}
              </span>
            </span>
            <span className="outcome-list__count">
              {formatCount(row.decisions)}
              <span className="sr-only"> decisões</span>
            </span>
          </button>
        ))}
        <div className="outcome-horizontal__axis" aria-hidden="true">
          {ticks.map((tick) => (
            <span key={tick} style={{ left: `${(tick / top) * 100}%` }}>
              {formatCount(tick)}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="outcome-chart" aria-hidden="true">
      {parts.map((row) => (
        <span
          key={row.outcome}
          className="outcome-chart__part"
          data-outcome={row.outcome}
          style={{ width: `${(row.decisions / counted) * 100}%` }}
        />
      ))}
    </div>
  );
}

export default OutcomeShareChart;
