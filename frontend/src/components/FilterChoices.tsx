import { useState } from 'react';
import type { FilterOption } from '../api/filters';

type Props<T extends string | number> = {
  legend: string;
  options: FilterOption<T>[];
  selected: T[];
  onChange: (selected: T[]) => void;
  disabled: boolean;
  searchable?: boolean;
};

export default function FilterChoices<T extends string | number>({
  legend,
  options,
  selected,
  onChange,
  disabled,
  searchable = false,
}: Props<T>) {
  const [query, setQuery] = useState('');
  const normalize = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('pt-BR');
  const visible = options.filter((option) => normalize(option.label).includes(normalize(query)));
  return (
    <fieldset className="search-filters__group" disabled={disabled}>
      <legend className="search-filters__legend">{legend}</legend>
      {searchable && (
        <label className="filter-local-search">
          Buscar relator
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Digite parte do nome"
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.preventDefault();
            }}
          />
        </label>
      )}
      {selected.length > 0 && (
        <div className="filter-tags" aria-label={`${legend} selecionados`}>
          {selected.map((value) => {
            const label = options.find((option) => option.value === value)?.label ?? String(value);
            return (
              <button
                type="button"
                key={value}
                className="filter-tag"
                aria-label={`Remover ${legend}: ${label}`}
                onClick={() => onChange(selected.filter((item) => item !== value))}
              >
                {label} ×
              </button>
            );
          })}
        </div>
      )}
      {options.length === 0 ? (
        <p className="filter-state">Nenhuma opção disponível.</p>
      ) : (
        <div className="filter-choice-list">
          {visible.map((option) => (
            <label key={option.value} className="filter-choice">
              <input
                type="checkbox"
                checked={selected.includes(option.value)}
                onChange={() =>
                  onChange(
                    selected.includes(option.value)
                      ? selected.filter((value) => value !== option.value)
                      : [...selected, option.value],
                  )
                }
              />
              <span>{option.label}</span>
            </label>
          ))}
          {visible.length === 0 && (
            <p className="filter-state">Nenhum relator encontrado para esse nome.</p>
          )}
        </div>
      )}
    </fieldset>
  );
}
