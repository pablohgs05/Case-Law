import { type ReactNode } from 'react';
import { useSessionState } from '../search/session';
import { CaretDown, Info } from '@phosphor-icons/react';
type Dimension = 'courts' | 'timeline' | 'outcomes';
export default function PanoramaLayout({
  courts,
  temporal,
  outcomes,
}: {
  courts: ReactNode;
  temporal: ReactNode;
  outcomes: ReactNode;
}) {
  const [expanded, setExpanded] = useSessionState<Dimension | null>('panoramaDimension', 'courts');
  const dimensions: {
    key: Dimension;
    title: string;
    category: string;
    content: ReactNode;
  }[] = [
    {
      key: 'courts',
      title: 'Onde o tema se concentra',
      category: 'Tribunais',
      content: courts,
    },
    {
      key: 'timeline',
      title: 'Como o volume mudou',
      category: 'Evolução',
      content: temporal,
    },
    {
      key: 'outcomes',
      title: 'Como os recursos foram julgados',
      category: 'Resultados',
      content: outcomes,
    },
  ];
  return (
    <div className="panorama-overview">
      <header className="panorama-overview__header">
        <h1>Panorama</h1>
        <p>Escolha uma dimensão para compreender o recorte.</p>
      </header>
      <div className="panorama-dimensions">
        {dimensions.map((dimension, index) => {
          const open = expanded === dimension.key;
          return (
            <section
              className={`panorama-dimension panorama-dimension--${dimension.key}`}
              key={dimension.key}
            >
              <h2 className="panorama-dimension__heading">
                <button
                  type="button"
                  className="panorama-dimension__toggle"
                  aria-label={dimension.title}
                  aria-expanded={open}
                  aria-controls={`dimension-${dimension.key}`}
                  id={`dimension-${dimension.key}-title`}
                  onClick={() => setExpanded(open ? null : dimension.key)}
                >
                  <span className="panorama-dimension__number" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className="panorama-dimension__title">{dimension.title}</span>
                  <span className="panorama-dimension__category">{dimension.category}</span>
                  <span className="panorama-dimension__explore">Explorar</span>
                  <CaretDown className="panorama-dimension__caret" size={16} aria-hidden="true" />
                </button>
              </h2>
              <div
                id={`dimension-${dimension.key}`}
                className="panorama-dimension__content"
                role="region"
                aria-labelledby={`dimension-${dimension.key}-title`}
                hidden={!open}
              >
                {dimension.content}
              </div>
            </section>
          );
        })}
      </div>
      <footer className="panorama-overview__footer">
        <Info size={15} aria-hidden="true" />
        Frequência não representa relevância jurídica.
      </footer>
    </div>
  );
}
