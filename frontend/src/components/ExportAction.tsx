import { useEffect, useId, useRef, useState } from 'react';
import { CircleNotch, DownloadSimple } from '@phosphor-icons/react';
import { downloadPdf, exportPdf, ExportRequestError, type ExportParams } from '../api/exports';

type ExportState =
  { status: 'ready' | 'generating' | 'complete' } | { status: 'failed'; message: string };

export default function ExportAction({
  params,
  total,
  disabled,
}: {
  params: ExportParams;
  total: number | null;
  disabled: boolean;
}) {
  const hintId = useId();
  const [state, setState] = useState<ExportState>({ status: 'ready' });
  const inFlight = useRef<AbortController | null>(null);
  useEffect(() => {
    return () => {
      inFlight.current?.abort();
    };
  }, []);

  const generate = async () => {
    if (inFlight.current || disabled || !total) return;
    const controller = new AbortController();
    inFlight.current = controller;
    setState({ status: 'generating' });
    try {
      const result = await exportPdf(params, controller.signal);
      if (controller.signal.aborted) return;
      downloadPdf(result.blob, result.filename);
      setState({ status: 'complete' });
    } catch (error) {
      if (!controller.signal.aborted)
        setState({
          status: 'failed',
          message:
            error instanceof ExportRequestError
              ? error.message
              : 'Não foi possível exportar o recorte. Tente novamente.',
        });
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
    }
  };
  const blocked = disabled || total === null || total === 0;
  const count = total?.toLocaleString('pt-BR');
  const hint =
    total === 0
      ? 'Não há decisões neste recorte para exportar.'
      : 'O PDF inclui todas as decisões do recorte, na ordem da pesquisa.';
  return (
    <div className="export-action" aria-label="Exportação do recorte">
      <button
        type="button"
        className="export-action__button"
        onClick={generate}
        aria-describedby={hintId}
        disabled={blocked || state.status === 'generating'}
      >
        {state.status === 'generating' ? (
          <CircleNotch size={16} className="motion-spinner" aria-hidden="true" />
        ) : (
          <DownloadSimple size={16} aria-hidden="true" />
        )}
        {state.status === 'generating'
          ? 'Gerando PDF...'
          : state.status === 'failed'
            ? 'Tentar exportar novamente'
            : `Exportar recorte${total !== null ? ` · ${count} ${total === 1 ? 'decisão' : 'decisões'}` : ''}`}
      </button>
      <p id={hintId} className="export-action__hint">
        {hint}
      </p>
      {state.status === 'generating' && (
        <p role="status">Gerando o PDF do recorte. Aguarde a conclusão.</p>
      )}
      {state.status === 'complete' && <p role="status">PDF gerado e enviado para download.</p>}
      {state.status === 'failed' && <p role="alert">{state.message}</p>}
    </div>
  );
}
