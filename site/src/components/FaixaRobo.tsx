import { NA_TELA, m, subir } from "../animacao";
import { HORAS_ATE_AVISAR } from "../config";
import { formataInteiro, plural } from "../lib/formatos";
import { dataCurta, dataEHora, haQuantoTempo, horaCurta, horasDesde } from "../lib/tempo";
import type { ExecucaoResumo, Robo, UltimaExecucao } from "../lib/types";
import { Icone } from "./Icone";

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

/** Ícone + cor: a situação nunca depende só da cor. */
function Execucao({ e }: { e: ExecucaoResumo }) {
  const s = situacaoDe(e.status);
  const quando = `${dataCurta(e.em)} às ${horaCurta(e.em)}`;
  return (
    <li className={`execucao execucao-${s}`} title={`${quando}: ${TEXTO_SITUACAO[s]}`}>
      <Icone nome={ICONE_SITUACAO[s]} tam={14} />
      <span className="so-leitor">
        {quando}: {TEXTO_SITUACAO[s]}
      </span>
    </li>
  );
}

export function FaixaRobo({ robo, geradoEm, agora }: { robo: Robo; geradoEm: string; agora: Date }) {
  const ultimoOk = robo.ultima_execucao_ok_em ?? null;
  const velho = ultimoOk === null || horasDesde(ultimoOk, agora) > HORAS_ATE_AVISAR;
  const u = robo.ultima;

  return (
    <m.section
      className={`robo ${velho ? "robo-alerta" : ""}`}
      aria-labelledby="robo-titulo"
      variants={subir}
      initial="oculto"
      whileInView="visivel"
      viewport={NA_TELA}
    >
      <div className="robo-principal">
        <span className={`robo-icone ${velho ? "robo-icone-aviso" : "robo-icone-ok"}`}>
          <Icone nome={velho ? "alerta" : "check"} tam={18} />
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
                Atualizou {haQuantoTempo(ultimoOk, agora)} ({dataEHora(ultimoOk, agora)}).
              </>
            )}
          </p>
        </div>
      </div>

      {robo.ultimas.length > 0 && (
        <>
          <ol className="execucoes" aria-label="Últimas execuções, da mais antiga para a mais recente">
            {robo.ultimas.map((e, i) => (
              <Execucao key={`${e.em}-${i}`} e={e} />
            ))}
          </ol>
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
        </>
      )}
    </m.section>
  );
}
