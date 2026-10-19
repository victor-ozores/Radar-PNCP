-- Editais relevantes com prazo aberto, do que vence primeiro ao que vence depois.
-- Rode a partir da raiz do clone da branch `data` (ou de ./data_local nas execuções locais):
--   duckdb -c ".read queries/01_editais_relevantes_abertos.sql"
SELECT
    score,
    uf,
    municipio,
    left(objeto, 90)                         AS objeto,
    valor_estimado,
    data_encerramento_proposta               AS prazo,
    dias_para_encerrar,
    link_pncp
FROM read_csv('data/export/editais.csv', header = true)
WHERE relevante
  AND dias_para_encerrar >= 0
ORDER BY data_encerramento_proposta, score DESC
LIMIT 30;
