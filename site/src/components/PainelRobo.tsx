import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { NA_TELA, m, subir } from "../animacao";
import { EXECUCOES_NA_FAIXA, HORAS_ATE_AVISAR } from "../config";
import { formataInteiro, plural } from "../lib/formatos";
import { dataCurta, dataEHora, haQuantoTempo, horaCurta, horasDesde } from "../lib/tempo";
import type { ExecucaoResumo, Robo, UltimaExecucao } from "../lib/types";
import { Dica } from "./Dica";
import { Icone, type NomeIcone } from "./Icone";

type Situacao = "ok" | "aviso" | "erro";

function situacaoDe(status: string): Situacao {
  if (status === "success") return "ok";
  if (status === "partial") return "aviso";
  return "erro";
}

const TEXTO_SITUACAO: Record<Situacao, string> = {
  ok: "rodou com sucesso",
  aviso: "rodou, mas parte das buscas falhou",
  erro: "falhou",
};

const ICONE_SITUACAO = { ok: "check", aviso: "alerta", erro: "fechar" } as const;

const quandoRodou = (iso: string) => `${dataCurta(iso)} às ${horaCurta(iso)}`;
const capitaliza = (texto: string) => texto.charAt(0).toUpperCase() + texto.slice(1);

function detalhesDa(u: UltimaExecucao): string[] {
  const partes: string[] = [];
  if (u.lidos !== null) partes.push(`${formataInteiro(u.lidos)} ${plural(u.lidos, "registro lido", "registros lidos")}`);
  if (u.novos !== null) partes.push(`${formataInteiro(u.novos)} ${plural(u.novos, "novo", "novos")}`);
  if (u.prazos_corrigidos) {
    partes.push(
      `${formataInteiro(u.prazos_corrigidos)} ${plural(u.prazos_corrigidos, "prazo corrigido", "prazos corrigidos")}`,
    );
  }
  if (u.duracao_min !== null) partes.push(`${formataInteiro(Math.round(u.duracao_min))} min de duração`);
  return partes;
}

/**
 * As últimas rodadas lado a lado, como nas páginas de status de serviços: uma barra por rodada, a mais recente à
 * direita. Escolher uma barra (toque, clique ou setas) mostra o que aconteceu naquela rodada. A cor nunca está
 * sozinha: a altura da barra muda com a situação e a legenda e o texto abaixo dizem o mesmo por escrito.
 */
function FaixaExecucoes({ execucoes, ultima }: { execucoes: ExecucaoResumo[]; ultima: UltimaExecucao | null }) {
  const botoes = useRef<(HTMLButtonElement | null)[]>([]);
  const [escolhida, setEscolhida] = useState(execucoes.length - 1);
  const i = Math.min(Math.max(escolhida, 0), execucoes.length - 1);
  const atual = execucoes[i]!;
  const situacao = situacaoDe(atual.status);
  const vazias = Math.max(0, EXECUCOES_NA_FAIXA - execucoes.length);

  const aoTeclar = (ev: KeyboardEvent, de: number) => {
    const destino =
      ev.key === "ArrowRight" ? de + 1 : ev.key === "ArrowLeft" ? de - 1 : ev.key === "Home" ? 0 : ev.key === "End" ? execucoes.length - 1 : null;
    if (destino === null) return;
    ev.preventDefault();
    const novo = Math.min(Math.max(destino, 0), execucoes.length - 1);
    setEscolhida(novo);
    botoes.current[novo]?.focus();
  };

  return (
    <div className="robo-historico">
      <div className="historico-topo">
        <h3>{execucoes.length === 1 ? "Última rodada" : `Últimas ${execucoes.length} rodadas`}</h3>
        <ul className="legenda" aria-label="Legenda das barras">
          {(["ok", "aviso", "erro"] as const).map((s) => (
            <li key={s}>
              <span className={`legenda-marca legenda-${s}`} aria-hidden="true">
                <Icone nome={ICONE_SITUACAO[s]} tam={10} />
              </span>
              {s === "ok" ? "Sucesso" : s === "aviso" ? "Parcial" : "Falha"}
            </li>
          ))}
        </ul>
      </div>

      <div className="historico-corpo">
        <div className="historico-faixa">
          <ol className="faixa-execucoes" aria-label="Últimas execuções, da mais antiga para a mais recente">
            {Array.from({ length: vazias }, (_, k) => (
              <li key={`vazia-${k}`} className="exec-vazia" aria-hidden="true" />
            ))}
            {execucoes.map((e, k) => {
              const s = situacaoDe(e.status);
              return (
                <li key={`${e.em}-${k}`}>
                  <button
                    type="button"
                    ref={(el) => {
                      botoes.current[k] = el;
                    }}
                    className={`exec exec-${s} ${k === i ? "exec-escolhida" : ""}`}
                    aria-pressed={k === i}
                    aria-label={`${quandoRodou(e.em)}: ${TEXTO_SITUACAO[s]}`}
                    tabIndex={k === i ? 0 : -1}
                    onClick={() => setEscolhida(k)}
                    onKeyDown={(ev) => aoTeclar(ev, k)}
                  />
                </li>
              );
            })}
          </ol>

          <div className="historico-datas" aria-hidden="true">
            <span>{dataCurta(execucoes[0]!.em)}</span>
            <span>{execucoes.length > 1 ? dataCurta(execucoes[execucoes.length - 1]!.em) : ""}</span>
          </div>
        </div>

        <p className={`execucao-detalhe execucao-detalhe-${situacao}`} aria-live="polite">
          <Icone nome={ICONE_SITUACAO[situacao]} tam={14} />
          <span>
            Rodada de {quandoRodou(atual.em)}: {TEXTO_SITUACAO[situacao]}.
            {ultima && ultima.em === atual.em && detalhesDa(ultima).length > 0 && <> {detalhesDa(ultima).join(", ")}.</>}
          </span>
        </p>
      </div>
    </div>
  );
}

function Metrica({
  icone,
  rotulo,
  dica,
  valor,
  apoio,
}: {
  icone: NomeIcone;
  rotulo: string;
  dica?: { pergunta: string; texto: ReactNode };
  valor: string;
  apoio: string;
}) {
  return (
    <li className="metrica">
      <span className="metrica-icone">
        <Icone nome={icone} tam={16} />
      </span>
      <div>
        <p className="metrica-rotulo">
          {rotulo}
          {dica && <Dica rotulo={dica.pergunta}>{dica.texto}</Dica>}
        </p>
        <p className="metrica-valor">{valor}</p>
        <p className="metrica-apoio">{apoio}</p>
      </div>
    </li>
  );
}

/** O que o robô fez na última rodada, contado em quatro passos. */
function Passos({ u, geradoEm, agora }: { u: UltimaExecucao; geradoEm: string; agora: Date }) {
  const numero = (n: number | null, um: string, varios: string) =>
    n === null ? "sem número" : `${formataInteiro(n)} ${plural(n, um, varios)}`;
  const corrigidos = [
    u.prazos_corrigidos ? numero(u.prazos_corrigidos, "prazo", "prazos") : null,
    u.situacoes_corrigidas ? numero(u.situacoes_corrigidas, "situação", "situações") : null,
  ].filter(Boolean);

  const passos: { icone: NomeIcone; titulo: string; texto: string; dica?: ReactNode }[] = [
    { icone: "documento", titulo: "Leu o PNCP", texto: numero(u.lidos, "registro", "registros") },
    { icone: "lupa", titulo: "Achou novidades", texto: numero(u.novos, "edital novo", "editais novos") },
    {
      icone: "relogio",
      titulo: "Conferiu prazos",
      texto: corrigidos.length > 0 ? `${corrigidos.join(" e ")} atualizados` : "Nada para corrigir",
      dica: "Depois de publicar, o órgão pode mudar o prazo ou excluir o edital. O robô confere de novo os que estão perto de vencer, para o painel não mostrar informação velha.",
    },
    { icone: "check", titulo: "Atualizou o painel", texto: dataEHora(geradoEm, agora) },
  ];

  return (
    <div className="robo-passos">
      <h3>O que o robô fez na última rodada</h3>
      <ol>
        {passos.map((p, k) => (
          <li key={p.titulo} className="robo-passo">
            <span className="robo-passo-icone">
              <Icone nome={p.icone} tam={16} />
            </span>
            <div>
              <p className="robo-passo-titulo">
                {p.titulo}
                {p.dica && <Dica rotulo={`Por que o robô ${p.titulo.toLowerCase()}?`}>{p.dica}</Dica>}
              </p>
              <p className="robo-passo-texto">{p.texto}</p>
            </div>
            {k < passos.length - 1 && (
              <span className="robo-passo-seta" aria-hidden="true">
                <Icone nome="seta" tam={16} />
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function PainelRobo({ robo, geradoEm, agora }: { robo: Robo; geradoEm: string; agora: Date }) {
  const ultimoOk = robo.ultima_execucao_ok_em ?? null;
  const velho = ultimoOk === null || horasDesde(ultimoOk, agora) > HORAS_ATE_AVISAR;
  const u = robo.ultima;
  const situacaoUltima = u ? situacaoDe(u.status) : null;

  return (
    <m.section
      className={`robo ${velho ? "robo-alerta" : "robo-ok"}`}
      id="robo"
      aria-labelledby="robo-titulo"
      variants={subir}
      initial="oculto"
      whileInView="visivel"
      viewport={NA_TELA}
    >
      <header className="robo-cabeca">
        <div className="robo-titulo">
          <span className="robo-pulso" aria-hidden="true">
            <span className="robo-ponto" />
          </span>
          <div>
            <h2 id="robo-titulo">{velho ? "Atenção" : "Robô em dia"}</h2>
            <p>
              {ultimoOk === null ? (
                <>O robô ainda não terminou nenhuma execução.</>
              ) : velho ? (
                <>
                  A última atualização foi {haQuantoTempo(ultimoOk, agora)}. Os editais abaixo podem estar
                  desatualizados: confira o prazo no PNCP antes de agir.
                </>
              ) : (
                <>
                  Atualizou {haQuantoTempo(ultimoOk, agora)} ({dataEHora(ultimoOk, agora)}). Todo dia ele lê o PNCP e
                  refaz esta página.
                </>
              )}
            </p>
          </div>
        </div>
        <span className={`robo-selo ${velho ? "robo-selo-aviso" : "robo-selo-ok"}`}>
          <Icone nome={velho ? "alerta" : "check"} tam={14} />
          {velho ? "Desatualizado" : "Operacional"}
        </span>
      </header>

      <ul className="robo-metricas">
        <Metrica
          icone="relogio"
          rotulo="Última atualização"
          dica={{
            pergunta: "Quando o robô roda?",
            texto:
              "O robô roda uma vez por dia, de manhã (horário de Brasília). O serviço que agenda a tarefa às vezes atrasa algumas horas, por isso a hora varia.",
          }}
          valor={ultimoOk === null ? "—" : haQuantoTempo(ultimoOk, agora)}
          apoio={ultimoOk === null ? "nenhuma execução terminou" : dataEHora(ultimoOk, agora)}
        />
        <Metrica
          icone="check"
          rotulo="Sucesso em 30 dias"
          dica={{
            pergunta: "O que é a taxa de sucesso?",
            texto:
              "De cada 100 rodadas diárias dos últimos 30 dias, quantas leram o PNCP sem falhas. Rodada que falha em parte conta como não concluída.",
          }}
          valor={robo.taxa_sucesso_30d_pct === null ? "—" : `${formataInteiro(Math.round(robo.taxa_sucesso_30d_pct))}%`}
          apoio={`${formataInteiro(robo.execucoes_30d)} ${plural(robo.execucoes_30d, "rodada", "rodadas")} no período`}
        />
        <Metrica
          icone="grafico"
          rotulo="Duração da última rodada"
          valor={u && u.duracao_min !== null ? `${formataInteiro(Math.round(u.duracao_min))} min` : "—"}
          apoio={situacaoUltima ? capitaliza(TEXTO_SITUACAO[situacaoUltima]) : "sem rodada"}
        />
      </ul>

      {robo.ultimas.length > 0 && <FaixaExecucoes execucoes={robo.ultimas} ultima={u} />}
      {u && <Passos u={u} geradoEm={geradoEm} agora={agora} />}

      {robo.ultimas.length > 0 && (
        <details className="detalhes">
          <summary>Detalhes do robô</summary>
          <p>
            {robo.taxa_sucesso_30d_pct !== null && (
              <>
                {formataInteiro(Math.round(robo.taxa_sucesso_30d_pct))}% de sucesso em {robo.execucoes_30d}{" "}
                {plural(robo.execucoes_30d, "execução", "execuções")} nos últimos 30 dias.{" "}
              </>
            )}
            {u && u.lidos !== null && <>Última execução: {detalhesDa(u).join(", ")}. </>}
            Arquivo de dados gerado {dataEHora(geradoEm, agora)}.
          </p>
        </details>
      )}
    </m.section>
  );
}
