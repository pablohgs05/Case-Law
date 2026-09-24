import { useState } from 'react';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import { searchDecisions, type SearchDecisionMatch } from '../api/search';
import DecisionResultCard from '../components/DecisionResultCard';

function HomePage() {
  const [value, setValue] = useState('prescrição intercorrente em execução fiscal');
  const [mode, setMode] = useState<'free' | 'exact'>('free');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [results, setResults] = useState<SearchDecisionMatch[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);

  const handleSubmit = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();

    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setErrorMessage('Digite uma expressão para pesquisar.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setTotalResults(null);
    setResults([]);

    try {
      const response = await searchDecisions({ q: trimmedValue, page: 1, page_size: 20 });
      setTotalResults(response.total);
      setResults(response.results);

      if (response.total === 0) {
        setErrorMessage(
          'Nenhuma decisão foi encontrada para esta expressão. Revise os termos ou tente uma sintaxe diferente.',
        );
      }
    } catch (requestError) {
      const message =
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'Não foi possível concluir a busca.';

      setErrorMessage(`${message} Tente novamente.`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="search-page">
      <div className="search-layout">
        <form className="legal-search" onSubmit={handleSubmit} noValidate>
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
              aria-label="Abrir filtros"
              disabled={isLoading}
            >
              <SlidersHorizontal size={17} aria-hidden="true" />
              <span>Filtros</span>
              <span className="filter-button__count">4</span>
            </button>

            <button type="submit" className="search-button" disabled={isLoading || !value.trim()}>
              {isLoading ? 'Pesquisando...' : 'Pesquisar'}
            </button>
          </div>
        </form>

        <section className="search-results" aria-live="polite">
          {isLoading && (
            <div className="search-state search-state--loading">Carregando resultados...</div>
          )}

          {!isLoading && totalResults !== null && (
            <div className="search-summary">
              <span>Total de resultados:</span>
              <strong>{totalResults}</strong>
            </div>
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
              <button type="button" className="search-state__retry" onClick={() => handleSubmit()}>
                Tentar novamente
              </button>
            </div>
          )}

          {!isLoading && results.length > 0 && (
            <ul className="result-list">
              {results.map((result) => (
                <li key={`${result.source}-${result.identifier}`} className="result-item">
                  <DecisionResultCard decision={result} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}

export default HomePage;
