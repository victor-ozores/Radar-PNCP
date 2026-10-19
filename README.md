# Branch `data`: dados do Radar PNCP

Esta branch **não tem código**. Ela guarda o que o pipeline produz e é atualizada sozinha pelo
workflow *Pipeline diário* da branch [`main`](https://github.com/victor-ozores/Radar-PNCP).
Não edite à mão.

```
warehouse/contratacoes/dt=AAAA-MM-DD/part.parquet   editais, uma partição por dia de publicação no PNCP
warehouse/pipeline_runs/runs.parquet                uma linha por execução (status, duração, chamadas, erros)
export/editais.csv                                  editais com nota e motivos (fonte do Power BI)
export/pipeline_runs.csv                            histórico das execuções
status.json                                         última execução e último sucesso (usado pelo vigia)
badge.json                                          dados do selo "última execução" do README
```

Consulte com SQL (DuckDB), a partir de um clone desta branch:

```sql
select status, trigger, rows_new, api_calls, http_429, duration_s
from read_parquet('warehouse/pipeline_runs/runs.parquet')
order by started_at;
```

Fonte pública para o Power BI:
`https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/editais.csv`

A primeira carga veio de uma execução **local** (`trigger = local`) em 19/10/2026. As execuções
agendadas aparecem com `trigger = schedule`.
