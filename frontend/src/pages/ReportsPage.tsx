import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft } from '@phosphor-icons/react';

import { CONTESTED_LABELS, listReports, ReportError, type ListedReport } from '../api/reports';
import { useCurrentPerson } from '../session/sessionContext';

/**
 * Every classification a reader said was wrong, for a manager.
 *
 * A list to read, not a review screen: nothing here changes a classification.
 * Each report carries what was published when it arrived, because the next
 * publication may have changed it, and a link to the decision as it is now.
 */

export const REPORTS_PATH = '/reportes';

const STATUS_LABELS: Record<ListedReport['status'], string> = {
  pendente: 'aguardando revisão',
  aceito: 'aceito',
  recusado: 'recusado',
};

function formatMoment(value: string): string {
  const moment = new Date(value);

  return Number.isNaN(moment.getTime())
    ? value
    : moment.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export default function ReportsPage() {
  const navigate = useNavigate();
  const person = useCurrentPerson();
  const [reports, setReports] = useState<ListedReport[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const manager = person?.role === 'gerente';

  useEffect(() => {
    if (!manager) {
      return;
    }

    const controller = new AbortController();

    listReports({ signal: controller.signal }).then(setReports, (error: unknown) => {
      if (!controller.signal.aborted) {
        setFailure(
          error instanceof ReportError ? error.message : 'Não foi possível carregar os reportes.',
        );
      }
    });

    return () => controller.abort();
  }, [manager]);

  return (
    <main className="team reports">
      <header className="team__header">
        <button type="button" className="coverage-back" onClick={() => navigate('/')}>
          <ArrowLeft size={13} aria-hidden="true" />
          Voltar à pesquisa
        </button>

        <h1 className="team__title">Reportes de classificação</h1>
        <p className="team__lead">
          O que os analistas apontaram como classificação incorreta, do mais recente ao mais antigo.
          Um reporte não altera a classificação publicada: ela continua a mesma até ser revista.
        </p>
      </header>

      <section className="team__list-area" aria-labelledby="reportes-recebidos">
        <h2 id="reportes-recebidos" className="team__section-title">
          Reportes recebidos
        </h2>

        {!manager && (
          <p className="team__feedback team__feedback--failed" role="alert">
            Só um gerente vê os reportes.
          </p>
        )}

        {failure && (
          <p className="team__feedback team__feedback--failed" role="alert">
            {failure}
          </p>
        )}

        {manager && reports === null && !failure && (
          <p className="team__state" role="status">
            Carregando os reportes…
          </p>
        )}

        {reports !== null && reports.length === 0 && (
          <p className="team__state">Nenhum reporte recebido até agora.</p>
        )}

        {reports !== null && reports.length > 0 && (
          <ul className="team__list">
            {reports.map((report) => (
              <li key={report.id} className="team__person reports__item">
                <div className="team__who">
                  <p className="team__name">
                    {CONTESTED_LABELS[report.information]}
                    <span className="team__badge">{STATUS_LABELS[report.status]}</span>
                  </p>
                  <p className="reports__description">{report.description}</p>
                  <p className="team__contact">
                    Publicado no momento do reporte:{' '}
                    {report.publishedValue ?? 'nenhuma classificação'}
                  </p>
                  <p className="team__contact">
                    {report.reportedBy.name}
                    {report.reportedBy.email ? ` · ${report.reportedBy.email}` : ''} ·{' '}
                    {formatMoment(report.receivedAt)}
                  </p>
                </div>

                <Link
                  className="team__change"
                  to={`/decisoes/${encodeURIComponent(report.source)}/${encodeURIComponent(report.identifier)}`}
                >
                  Abrir decisão
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
