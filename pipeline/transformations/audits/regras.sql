AUDIT (
  name sem_segredo_de_justica,
  dialect postgres
);
/* Nenhuma decisão em segredo de justiça pode chegar ao núcleo.
   O filtro está na transformação; esta auditoria é a rede de segurança. */
SELECT d.*
FROM @this_model AS d
JOIN raw.acordao_tjdft AS r
  ON r.identificador = d.identificador_fonte
WHERE COALESCE(r."segredoJustica", FALSE);

AUDIT (
  name data_referencia_preenchida,
  dialect postgres
);
/* Documento sem nenhuma data não é filtrável nem ordenável — não serve ao produto. */
SELECT * FROM @this_model WHERE data_referencia IS NULL;
