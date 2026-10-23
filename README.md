# Branch `data`: dados do Radar PNCP

Esta branch **não tem código**. Ela guarda o que o robô produz e é atualizada sozinha pelo
workflow *Pipeline diário* da branch [`main`](https://github.com/victor-ozores/Radar-PNCP).
Não edite à mão.

```
warehouse/contratacoes/dt=AAAA-MM-DD/part.parquet   editais, uma partição por dia de publicação no PNCP
warehouse/pipeline_runs/runs.parquet                uma linha por execução (status, duração, chamadas, erros)
export/painel.json                                  o que a página pública lê (editais abertos que combinam + saúde do robô)
export/editais.csv                                  dados abertos: editais com nota e motivos
export/pipeline_runs.csv                            histórico das execuções
status.json                                         última execução e última rotina diária bem-sucedida (usado pelo vigia)
badge.json                                          dados do selo "última execução" do README
```

O painel que lê esses dados: <https://victor-ozores.github.io/Radar-PNCP/>

Consulte com SQL (DuckDB), a partir de um clone desta branch:

```sql
select status, trigger, modo, rows_new, api_calls, http_429, duration_s
from read_parquet('warehouse/pipeline_runs/runs.parquet')
order by started_at;
```

Endereços públicos dos arquivos:

* `https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/painel.json`
* `https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/editais.csv`

Um edital que o PNCP **excluiu** continua na tabela, com `situacao_id = 99` ("Excluída do PNCP"):
a linha não é apagada, só sai das listas.

A primeira carga veio de uma execução **local** (`trigger = local`) em 19/10/2026. As execuções
agendadas aparecem com `trigger = schedule`; a conferência semanal, com `modo = reconcile`.

A história desta branch é compactada a cada 6 meses (um commit só, com o estado atual). O passo a
passo está na seção 6 de `docs/setup-checklist.md`, na `main`.
