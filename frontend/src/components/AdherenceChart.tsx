import type { AdherenceCount } from '../api/precedents';

const drawable = (row: AdherenceCount): row is AdherenceCount & { links: number } =>
  row.links !== null && row.links > 0;

// One bar, split in the order the panel ranked once for the list beside it, so
// the two can never disagree. Lengths are proportional to the citations the
// wording settled — the same denominator the list states. The list carries
// every number as text, so the drawing is hidden from screen readers rather
// than read twice.
function AdherenceChart({ adherences }: { adherences: AdherenceCount[] }) {
  const parts = adherences.filter(drawable);
  const counted = parts.reduce((sum, row) => sum + row.links, 0);

  if (!counted) {
    return null;
  }

  return (
    <div className="outcome-chart" aria-hidden="true">
      {parts.map((row) => (
        <span
          key={row.adherence}
          className="outcome-chart__part"
          data-adherence={row.adherence}
          style={{ width: `${(row.links / counted) * 100}%` }}
        />
      ))}
    </div>
  );
}

export default AdherenceChart;
