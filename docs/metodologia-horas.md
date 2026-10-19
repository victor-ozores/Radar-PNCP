# Metodologia: horas economizadas (estimativa)

> **Isto é uma estimativa, não uma medição.** As premissas abaixo ainda **não foram validadas**
> com uma pessoa de orçamentos. Até isso acontecer, qualquer número derivado deve aparecer com o
> rótulo "estimativa".

## Fórmula

```
horas_por_mes = dias_uteis_no_mes × (minutos_busca_manual − minutos_lendo_o_resumo) / 60
```

## Premissas (a validar)

| Variável | Cenário conservador | Cenário central | Fonte |
|---|---|---|---|
| `dias_uteis_no_mes` | 21 | 21 | calendário |
| `minutos_busca_manual` (por dia, em vários portais) | 20 | 45 | **hipótese do autor, não medida** |
| `minutos_lendo_o_resumo` (Telegram) | 5 | 5 | **hipótese do autor, não medida** |

Resultado com essas hipóteses: conservador 21 × 15 / 60 = **5,25 h/mês**; central 21 × 40 / 60 =
**14 h/mês**.

## Como validar

1. Perguntar a uma pessoa de orçamentos (por exemplo, um ex-colega da AFEZ) quantos minutos por
   dia ela gasta procurando editais e em quantos portais.
2. Substituir as hipóteses acima pelos valores informados e registrar quem respondeu e quando
   (sem expor dados pessoais).

## Métricas medidas (não dependem de estimativa)

Estas saem das tabelas do próprio pipeline e podem ser citadas sem ressalva:

* taxa de sucesso das execuções agendadas (`pipeline_runs`);
* editais lidos e novos por dia;
* editais relevantes por mês;
* tempo de execução e bloqueios 429;
* frescor: horário do alerta menos `data_publicacao` do edital;
* precisão do filtro, quando houver uma amostra revisada à mão (a fazer).
