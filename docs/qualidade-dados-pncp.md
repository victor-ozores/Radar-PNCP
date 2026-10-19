# O que a API do PNCP mostrou (achados de qualidade e comportamento)

Medido com chamadas reais à API de consulta em **19/10/2026**. Não é documentação oficial: o
comportamento pode mudar. As contagens vêm de uma amostra pequena e servem para dimensionar o
pipeline, não como estatística do PNCP. Os números do pipeline em produção ficam na tabela
`pipeline_runs` e em `queries/03_qualidade_dos_dados.sql`.

## Comportamento da API

| Achado | Como foi observado | O que o código faz |
|---|---|---|
| Não exige autenticação, embora o Swagger declare `bearerAuth` | Chamadas sem token responderam 200 | Nenhuma credencial da API |
| `codigoModalidadeContratacao` é obrigatório em `/contratacoes/publicacao` | Sem ele: HTTP 400 | Uma série de buscas por modalidade e UF |
| Datas em `yyyyMMdd`; ISO (`2026-10-31`) devolve **422** | Teste direto em `/proposta` | `fmt_date` em `pncp_client.py` |
| `tamanhoPagina` aceita 10 a 50 | 51 e 9 devolveram 400 | Usa 50; o `config.yaml` valida o limite |
| Sem registros devolve **204 sem corpo** | Modalidades 2 e 3 em 16/10/2026 | Tratado como lista vazia |
| Excesso de chamadas devolve **429 com corpo HTML** e sem `Retry-After` | Bloqueio após ~8 a 10 chamadas a 1,2 s de intervalo; 4 s de intervalo passou limpo; liberou em menos de 75 s | Intervalo mínimo de 4 s e espera de 30, 60 e 120 s no 429 |
| O filtro `uf` funciona no servidor | 10 de 10 itens retornaram a UF pedida | Mesmo assim confere cada linha (`uf_mismatch`), pois há relato público de filtros ignorados em silêncio em outros parâmetros |
| A UF fica em `unidadeOrgao.ufSigla` | Não existe `unidadeFederativa` no item | `normalize.py` |
| `/proposta` com `dataFinal` devolve propostas abertas que encerram **até** essa data | 1ª página: encerramentos entre 20/10 e 26/10 para `dataFinal` = 26/10; publicações de nov/2024 a set/2026 | Usado na carga inicial (`bootstrap`) |
| Sem valor estimado chega como **0**, não como nulo | Amostra de 50 pregões eletrônicos em SP: 13 com valor nulo ou zero | `valor_zero` e `valor_ausente` viram métrica; o valor é gravado como nulo e não penaliza o score |

## Volume (publicados em 16/10/2026, Brasil inteiro)

| Modalidade | Registros |
|---|---|
| 6 Pregão eletrônico | 1.601 |
| 4 Concorrência eletrônica | 254 |
| 7 Pregão presencial | 31 |
| 5 Concorrência presencial | 13 |
| 1 Leilão eletrônico | 12 |
| 2 e 3 | 0 (HTTP 204) |

As modalidades 8 a 13 não foram medidas (a API bloqueou a consulta). Medir a 8 (dispensa) antes de
incluí-la no perfil.

## Qualidade do conteúdo

* **Texto livre ruidoso para busca por palavra-chave.** "Mão de obra" aparece em quase todo
  contrato de serviço (limpeza, vigilância). Sem tratamento, o termo `obra` marcava limpeza e
  vigilância como obra de engenharia. A correção está em `scoring.py` e tem teste.
* **Status que mudam depois da publicação** (`Revogada`, `Suspensa`). Por isso o armazenamento
  é um upsert por `numeroControlePNCP`, e o score zera editais inativos.
* **Link do sistema de origem ausente** em parte dos editais (19 de 50 na amostra). O alerta
  sempre inclui o link público do PNCP, montado a partir de CNPJ, ano e sequencial.
* **`usuarioNome` traz nomes de fornecedores de software** nos itens vistos (por exemplo
  "BLL Compras", "Fiorilli Software"), mas o campo pode conter pessoa física em outros casos.
  Por isso entra no descarte da allowlist (veja README, seção "Dados e LGPD").
