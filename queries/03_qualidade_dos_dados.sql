-- Lacunas de qualidade do PNCP por modalidade (base dos posts sobre qualidade de dados).
SELECT
    modalidade_nome                                              AS modalidade,
    count(*)                                                     AS editais,
    round(100 * avg((valor_estimado IS NULL)::INT), 1)           AS pct_sem_valor,
    round(100 * avg((link_origem IS NULL)::INT), 1)              AS pct_sem_link_origem,
    round(100 * avg((situacao_id IN (2, 3, 4))::INT), 1)         AS pct_revogada_anulada_suspensa,
    round(100 * avg((data_encerramento_proposta < data_abertura_proposta)::INT), 2)
                                                                 AS pct_prazo_antes_da_abertura
FROM read_parquet('data/warehouse/contratacoes/dt=*/part.parquet', union_by_name = true)
GROUP BY ALL
ORDER BY editais DESC;
