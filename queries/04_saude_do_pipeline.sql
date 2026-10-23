-- Saúde do pipeline: taxa de sucesso, duração e bloqueios 429 por semana.
-- Só a rotina diária de verdade (a mesma conta do status.json e do painel): ficam de fora a carga
-- inicial, o backfill, a conferência semanal (modo 'reconcile') e a falha simulada de teste.
SELECT
    date_trunc('week', started_at)::DATE                         AS semana,
    count(*)                                                     AS execucoes,
    count(*) FILTER (WHERE status IN ('success', 'partial'))     AS ok,
    round(100.0 * count(*) FILTER (WHERE status IN ('success', 'partial')) / count(*), 1)
                                                                 AS taxa_sucesso_pct,
    round(avg(duration_s), 1)                                    AS duracao_media_s,
    sum(http_429)                                                AS bloqueios_429,
    sum(rows_new)                                                AS editais_novos,
    sum(prazos_alterados)                                        AS prazos_corrigidos
FROM read_parquet('data/warehouse/pipeline_runs/runs.parquet')
WHERE modo = 'daily'
  AND NOT coalesce(simulado, false)
  AND coalesce(error_message, '') NOT ILIKE '%simulada%'
GROUP BY 1
ORDER BY 1 DESC;
