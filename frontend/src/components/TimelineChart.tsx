import { useId, useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { PeriodVolume } from '../api/indicators';
import { formatCount } from './coverageFormat';
import { axisTicks } from './volumeFormat';
import { formatPeriodLabel } from '../search/indicatorSelection';

export type TimelineChartProps = {
  periods: PeriodVolume[];
  granularity?: 'month' | 'quarter' | 'year' | null;
  onSelectPeriod?: (period: string) => void;
  selectedPeriod?: string | null;
  isAnimationActive?: boolean;
  showValues?: boolean;
  height?: number;
  selectionDisabled?: boolean;
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      period: string;
      label: string;
      count: number | null;
    };
  }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;
  const item = payload[0].payload;
  return (
    <div className="timeline-tooltip" role="tooltip">
      <div className="timeline-tooltip__period">{item.label}</div>
      <div className="timeline-tooltip__count">
        <strong>{formatCount(item.count) ?? 'Não informado'}</strong>{' '}
        {item.count === null ? '' : item.count === 1 ? 'decisão' : 'decisões'}
      </div>
    </div>
  );
}

export function TimelineChart({
  periods,
  granularity = 'month',
  onSelectPeriod,
  selectedPeriod,
  isAnimationActive = false,
  showValues = true,
  height = 260,
  selectionDisabled = false,
}: TimelineChartProps) {
  const effectiveGranularity = granularity ?? 'month';
  const gradientId = useId().replace(/:/g, '');
  const ValuesContainer = showValues ? 'details' : 'div';

  // Prepare chart data
  const chartData = useMemo(() => {
    return periods.map((p) => ({
      period: p.period,
      label: formatPeriodLabel(p.period, effectiveGranularity),
      count: p.decisions,
    }));
  }, [periods, effectiveGranularity]);

  const maxCount = useMemo(() => {
    if (periods.length === 0) return 0;
    return Math.max(...periods.map((p) => p.decisions ?? 0), 0);
  }, [periods]);

  const yTicks = useMemo(() => {
    const ticks = axisTicks(maxCount);
    return ticks.length > 0 ? ticks : [0];
  }, [maxCount]);

  const yDomainMax = Math.max(1, yTicks[yTicks.length - 1] ?? 1);
  const renderPoint = (raw: unknown) => {
    const { cx, cy, index } = raw as { cx?: number; cy?: number; index?: number };
    const point = index === undefined ? undefined : chartData[index];
    if (!point || cx === undefined || cy === undefined || point.count === null) return <g />;
    return (
      <g
        key={point.period}
        className="timeline-chart__point indicator-target--period"
        data-indicator-focus={`period:${point.period}`}
        role="button"
        tabIndex={selectionDisabled ? -1 : 0}
        aria-disabled={selectionDisabled}
        aria-label={`Consultar documentos de ${point.label}: ${formatCount(point.count)} ${point.count === 1 ? 'decisão' : 'decisões'}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!selectionDisabled) onSelectPeriod?.(point.period);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            event.stopPropagation();
            if (!selectionDisabled) onSelectPeriod?.(point.period);
          }
        }}
      >
        <circle
          className="timeline-chart__point-focus"
          cx={cx}
          cy={cy}
          r={10}
          fill="transparent"
          pointerEvents="none"
        />
        <circle
          className="recharts-area-dot"
          cx={cx}
          cy={cy}
          r={4}
          fill="var(--search-primary)"
          stroke="#fff"
          strokeWidth={1.5}
        />
      </g>
    );
  };

  if (periods.length === 0) {
    return (
      <div className="timeline-chart--empty" role="status">
        Nenhum dado temporal disponível.
      </div>
    );
  }

  return (
    <div className="timeline-chart-wrapper">
      <div
        className="timeline-chart__visual"
        aria-hidden={onSelectPeriod ? undefined : true}
        style={{ width: '100%', height }}
      >
        <ResponsiveContainer
          width="100%"
          height={height}
          minWidth={100}
          minHeight={100}
          initialDimension={{ width: 800, height }}
        >
          <AreaChart
            accessibilityLayer={false}
            data={chartData}
            margin={{ top: 20, right: 24, left: 0, bottom: 20 }}
            onClick={
              onSelectPeriod
                ? (state) => {
                    if (
                      selectionDisabled ||
                      state.activeTooltipIndex === null ||
                      state.activeTooltipIndex === undefined
                    )
                      return;
                    const point = chartData[Number(state.activeTooltipIndex)];
                    if (point && point.count !== null) onSelectPeriod(point.period);
                  }
                : undefined
            }
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4A151E" stopOpacity={0.16} />
                <stop offset="90%" stopColor="#4A151E" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid vertical={false} stroke="#EFE6E1" />

            <XAxis
              dataKey="label"
              interval="preserveStartEnd"
              minTickGap={26}
              tickLine={false}
              axisLine={{ stroke: '#E5D8D0' }}
              tick={{
                fill: 'var(--search-muted)',
                fontSize: 'var(--text-2xs)',
                fontFamily: "'Source Sans 3', sans-serif",
              }}
              dy={8}
            />

            <YAxis
              domain={[0, yDomainMax]}
              ticks={yTicks}
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              tick={{
                fill: 'var(--search-muted)',
                fontSize: 'var(--text-2xs)',
                fontFamily: "'Source Sans 3', sans-serif",
              }}
              tickFormatter={(value: number) => formatCount(value) ?? ''}
              width={70}
            />

            <Tooltip
              content={<CustomTooltip />}
              cursor={{ stroke: '#8A7B73', strokeWidth: 1, strokeDasharray: '3 3' }}
            />

            {selectedPeriod && (
              <ReferenceLine
                x={formatPeriodLabel(selectedPeriod, effectiveGranularity)}
                stroke="#7b1f2e"
                strokeDasharray="3 3"
              />
            )}
            <Area
              type="monotone"
              dataKey="count"
              stroke="var(--search-primary)"
              strokeWidth={2.5}
              fill={showValues ? `url(#${gradientId})` : '#f8ebe6'}
              isAnimationActive={isAnimationActive}
              dot={
                onSelectPeriod
                  ? renderPoint
                  : periods.length === 1
                    ? { r: 5, fill: 'var(--search-primary)' }
                    : false
              }
              activeDot={{
                r: 5,
                fill: '#4A151E',
                stroke: '#FFFFFF',
                strokeWidth: 2,
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <ValuesContainer
        className={showValues ? 'timeline-values' : 'sr-only'}
        {...(showValues ? { open: true } : {})}
      >
        {showValues && <summary>Consultar valores por período</summary>}
        <table>
          <caption>Evolução do volume de decisões no tempo</caption>
          <thead>
            <tr>
              <th scope="col">Período</th>
              <th scope="col">Quantidade de decisões</th>
            </tr>
          </thead>
          <tbody>
            {chartData.map((d) => (
              <tr key={d.period} aria-current={selectedPeriod === d.period ? 'true' : undefined}>
                <th scope="row">{d.label}</th>
                <td>{formatCount(d.count) ?? 'Não informado'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ValuesContainer>
    </div>
  );
}

export default TimelineChart;
