import type { CourtVolume } from '../api/indicators';
import { formatCount } from './coverageFormat';
import { axisTicks } from './volumeFormat';

// Only known counts have a drawable length; the panel handles missing data.
const drawable = (court: CourtVolume): court is CourtVolume & { decisions: number } =>
  court.decisions !== null;

// Horizontal bars from one baseline, in the order given — the panel ranks the
// courts once for the chart and the list — each with its count at the tip.
// Lengths are proportional from zero. Interactive rows carry their court and
// count as a native button; without a callback the chart remains decorative.
function CourtVolumeChart({
  courts,
  onSelect,
  disabled = false,
}: {
  courts: CourtVolume[];
  onSelect?: (court: string, count: number) => void;
  disabled?: boolean;
}) {
  const bars = courts.filter(drawable);
  const ticks = axisTicks(Math.max(0, ...bars.map((court) => court.decisions)));
  const top = ticks[ticks.length - 1] || 1;
  const at = (value: number) => `${(value / top) * 100}%`;
  const Row = onSelect ? 'button' : 'div';

  return (
    <div className="volume-chart" aria-hidden={onSelect ? undefined : true}>
      <div className="volume-chart__plot">
        {/* The same span the bars are measured in: past the court labels,
            short of the room kept for the count at the longest bar's tip. */}
        <div className="volume-chart__scale" aria-hidden="true">
          {ticks.map((tick) => (
            <span key={tick} className="volume-chart__grid" style={{ left: at(tick) }} />
          ))}
        </div>

        {bars.map((court) => (
          <Row
            key={court.abbreviation}
            className={`volume-chart__row${onSelect ? ' indicator-target indicator-target--court' : ''}`}
            type={onSelect ? 'button' : undefined}
            disabled={onSelect ? disabled : undefined}
            aria-label={
              onSelect
                ? `Consultar documentos de ${court.abbreviation}: ${formatCount(court.decisions)} decisões`
                : undefined
            }
            onClick={() => onSelect?.(court.abbreviation, court.decisions)}
          >
            <span className="volume-chart__label">{court.abbreviation}</span>
            <span className="volume-chart__track">
              <span className="volume-chart__bar" style={{ width: at(court.decisions) }} />
              <span className="volume-chart__value">{formatCount(court.decisions)}</span>
            </span>
          </Row>
        ))}
      </div>

      <div className="volume-chart__axis" aria-hidden="true">
        <div className="volume-chart__scale">
          {ticks.map((tick) => (
            <span key={tick} className="volume-chart__tick" style={{ left: at(tick) }}>
              {formatCount(tick)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default CourtVolumeChart;
