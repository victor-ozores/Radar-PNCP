# O que a API do PNCP mostrou (achados de qualidade e comportamento)

Medido com chamadas reais à API de consulta entre **19 e 22/10/2026**. Não é documentação oficial:
o comportamento pode mudar. As contagens vêm de uma amostra pequena e servem para dimensionar o
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
| Valor simbólico (por exemplo R$ 0,04) em vez de zero | Apareceu nos dados reais de 22/10/2026 | Abaixo de R$ 1 mil o painel e o alerta mostram "valor não informado" (o guardado não muda) |
| Edital **excluído** responde **HTTP 410** na consulta individual (`/orgaos/{cnpj}/compras/{ano}/{seq}`) e some das listagens, sem aviso | 2 dos 8 editais "sumidos" de 22/10/2026 (ver abaixo) | `conferencia.py` marca como "Excluída do PNCP" (`situacao_id` 99) e tira das listas; a linha fica no Parquet |
| A consulta individual traz **o mesmo conteúdo** da listagem | 10 de 10 editais com `row_hash` igual | Comparar o hash basta para saber se algo mudou |

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
  Por isso entra no descarte da allowlist (veja README, seção "Custa R$ 0 e respeita a LGPD").
* **Nome do órgão sem acento e em CAIXA ALTA** ("MUNICIPIO DE IBIRITE"), enquanto a cidade do mesmo
  edital vem certa ("Ibirité"): em 22/10/2026, 356 dos 1.394 editais do painel tinham a cidade sem
  acento no nome do órgão. A tela e o Telegram copiam a grafia da cidade (`nome_do_orgao` em
  `normalize.py`, igual em `site/src/lib/formatos.ts`); o texto guardado não muda.
* **O mesmo edital publicado duas vezes** (mesmo órgão, valor, prazo e texto): em 22/10/2026, 41 dos
  1.338 editais que combinam tinham um gêmeo (cerca de 3%; entre todos os abertos, cerca de 5%).
  Dos pares conferidos no PNCP, 2 de 3 estavam com os dois ativos (o órgão republica com outro
  número, por exemplo "34" e "34/2026REPUBLICADO", ou publica duas vezes em minutos) e em 1 o
  original tinha sido excluído (410). O painel e o Telegram mostram o edital uma vez, com o número e
  o link do outro (`repetidos.py`); no alerta, cada registro é conferido no PNCP antes, para o link
  nunca apontar para um excluído. O texto conta como o mesmo se for igual ou estiver inteiro dentro
  do outro (a republicação costuma só acrescentar "Processo nº ..."). Na dúvida não junta: há pares
  com o mesmo valor e prazo e textos bem diferentes ("brinquedos parquinho" e uma descrição longa de
  playground) que provavelmente são o mesmo edital, mas também há par com valor e prazo iguais e
  objetos sem relação alguma, então o texto precisa bater.
* **Consultoria, fiscalização, gerenciamento e projeto** não são obra, mas citam "obra" e
  "engenharia": eram 2,6% dos relevantes (38 de 1.448 em 22/10/2026). Têm regra própria em
  `scoring.py` (`servicos_intelectuais` no `config.yaml`).

## Conferência com o PNCP ao vivo (21/10/2026)

Medido comparando o que o robô guardou com a API e com a página pública de cada edital.

| Verificação | Resultado |
|---|---|
| Link público `pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}` | Abre o edital certo (conferido no navegador: objeto, valor e prazo iguais aos guardados) |
| 60 editais relevantes sorteados, conferidos um a um (situação, prazo, valor) | 0 desatualizados |
| Editais com prazo em até 7 dias (13 buscas): lista de propostas abertas da API contra o guardado | 829 em comum; 8 guardados que a API já não listava (7 deles com **prazo prorrogado**, por exemplo de 22/10 para 10/12); 2 que a API tinha e o robô não |
| Consulta por **data de atualização** (últimos 3 dias) | Trouxe 7 dos 8 prazos prorrogados; o oitavo não apareceu nela |

Consequências para o desenho:

* **Prorrogação é comum.** Quanto mais perto do vencimento, mais provável. A consulta por
  publicação, sozinha, nunca revê um edital já guardado, então a rotina diária passou a ler
  também a consulta por atualização. A execução registra `prazos_alterados` e `situacoes_alteradas`.
* **A carga inicial só cobre prazos de até 30 dias** (a consulta `/proposta` usa `dataFinal`).
  Editais com prazo mais longo só entram quando publicados ou alterados depois.
* **Custo da consulta por atualização** (rodada de teste de 21/10/2026, 16 buscas de alterados em
  2 dias): 3.847 linhas lidas, das quais 2.216 (58%) eram de editais já encerrados (homologações) e
  foram descartadas; 92 prazos e 74 situações mudaram. Execução inteira: 143 chamadas. Depois dela,
  os guardados desatualizados (prazo ≤ 7 dias) caíram de 8 em 813 (1,0%) para 1 em 791 (0,1%).
* **O nome da secretaria dentro do texto atrapalha o filtro** ("Secretaria Municipal de Obras e
  Engenharia"): um serviço de alinhamento de veículos casou `obra` e `engenharia` por isso.
* **O que o filtro deixa de fora** (medido): obras de recapeamento, calçamento e muro de contenção
  não estavam no perfil (50 editais); entraram. "Drenagem" e "esgotamento sanitário" foram testados
  e rejeitados (trouxeram cânula de drenagem venosa e um software).

## Editais excluídos e prazos velhos (22/10/2026)

Mesmo lendo as alterações, sobraram editais guardados como abertos que a lista de propostas abertas
da API já não trazia: **8 de 837 (1,0%)** entre os de prazo em até 7 dias. A consulta individual de
cada um explicou todos: 2 **excluídos** do PNCP (HTTP 410, que nenhuma listagem avisa) e 6 com
**prazo prorrogado** antes de o robô passar a ler as alterações.

Primeira conferência semanal de verdade (cópia local dos dados, janela de 14 dias): 16 buscas,
7.667 linhas lidas, 209 chamadas, 46 minutos, nenhum bloqueio 429. Dos 47 editais guardados como
abertos que a listagem não trouxe, **20 estavam excluídos** e **27 tinham mudado** (prazo, valor ou
situação); nenhuma resposta incerta. No painel isso tirou 2 excluídos e 7 suspensos ou anulados e
corrigiu 3 prazos e 3 valores. Comparando de novo com a API, os guardados como abertos que a API não
lista caíram de 8 em 837 (1,0%) para 3 em 819 (0,4%). Consulta individual dos 3: 1 **excluído** (410)
e 2 com **prazo prorrogado** no PNCP em 22/10 (às 12:23 e às 15:45) que a lista de propostas abertas
ainda mostrava com o prazo antigo durante a conferência das 19:20. Ou seja, **a lista do PNCP pode
demorar horas para refletir uma mudança**, e só a consulta individual é a fonte. As prorrogações
entram na leitura de alterações do dia seguinte; a exclusão não tem aviso nenhum.

Por isso a consulta individual passou a ser feita em três momentos: **todo dia**, nos editais que
combinam e vencem em até 3 dias (do que vence primeiro ao que vence depois, no máximo 100
consultas, de 12 a 23 minutos a mais na rotina); **antes de cada alerta**, nos de "Prazos chegando"
(os já conferidos no dia não são consultados de novo); e **todo domingo**, em tudo o que a lista
deixa de trazer até 14 dias. Quantos editais vencem em até 3 dias muda muito com o dia da semana
(estimado para os próximos dias: 95 na sexta, 308 na segunda), por isso o teto. Se o PNCP parar de
responder (duas respostas incertas seguidas), a conferência do dia e a do alerta desistem sem marcar
nada. Mesmo assim a página continua pedindo para conferir o edital no PNCP.
