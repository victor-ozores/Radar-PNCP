-- Saúde do pipeline: taxa de sucesso, duração e bloqueios 429 por semana.
SELECT
    date_trunc('week', started_at)::DATE                         AS semana,
    count(*)                                                     AS execucoes,
    count(*) FILTER (WHERE status IN ('success', 'partial'))     AS ok,
    round(100.0 * count(*) FILTER (WHERE status IN ('success', 'partial')) / count(*), 1)
                                                                 AS taxa_sucesso_pct,
    round(avg(duration_s), 1)                                    AS duracao_media_s,
    sum(http_429)                                                AS bloqueios_429,
    sum(rows_new)                                                AS editais_novos
FROM read_parquet('data/warehouse/pipeline_runs/runs.parquet')
GROUP BY 1
ORDER BY 1 DESC;
