-- Quantos editais o robô guardou por UF e modalidade, e quanto vale o que foi publicado.
SELECT
    uf,
    modalidade_nome                          AS modalidade,
    count(*)                                 AS editais,
    count(valor_estimado)                    AS com_valor,
    round(sum(valor_estimado) / 1e6, 1)      AS valor_total_mi
FROM read_parquet('data/warehouse/contratacoes/dt=*/part.parquet', union_by_name = true)
GROUP BY ALL
ORDER BY editais DESC;
