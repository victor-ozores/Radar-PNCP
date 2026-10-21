import { HORAS_ATE_AVISAR } from "../config";
import { formataInteiro, plural } from "../lib/formatos";
import { dataCurta, dataEHora, haQuantoTempo, horaCurta, horasDesde } from "../lib/tempo";
import type { ExecucaoResumo, Robo, UltimaExecucao } from "../lib/types";

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

/** Ícone + cor: a situação nunca depende só da cor. */
function Icone({ situacao }: { situacao: Situacao }) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
      {situacao === "ok" && <path d="M3.5 8.5 6.6 11.5 12.5 4.8" />}
      {situacao === "aviso" && <path d="M8 3.5v5.5M8 11.6v.9" />}
      {situacao === "erro" && <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" />}
    </svg>
  );
}

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

function Execucao({ e }: { e: ExecucaoResumo }) {
  const s = situacaoDe(e.status);
  const quando = `${dataCurta(e.em)} às ${horaCurta(e.em)}`;
  return (
    <li className={`execucao execucao-${s}`} title={`${quando}: ${TEXTO_SITUACAO[s]}`}>
      <Icone situacao={s} />
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
    <section className={`robo ${velho ? "robo-alerta" : ""}`} aria-labelledby="robo-titulo">
      <h2 id="robo-titulo" className="so-leitor">
        Situação do robô
      </h2>
      <p className="robo-resumo">
        <span className={`robo-selo ${velho ? "selo-aviso" : "selo-ok"}`}>
          <Icone situacao={velho ? "aviso" : "ok"} />
          {velho ? "Atenção" : "Robô em dia"}
        </span>{" "}
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

      {robo.ultimas.length > 0 && (
        <div className="execucoes-bloco">
          <ol className="execucoes" aria-label="Últimas execuções, da mais antiga para a mais recente">
            {robo.ultimas.map((e, i) => (
              <Execucao key={`${e.em}-${i}`} e={e} />
            ))}
          </ol>
          <p className="robo-detalhe">
            {robo.taxa_sucesso_30d_pct !== null && (
              <>
                {formataInteiro(Math.round(robo.taxa_sucesso_30d_pct))}% de sucesso em{" "}
                {robo.execucoes_30d} {plural(robo.execucoes_30d, "execução", "execuções")} nos últimos 30
                dias.{" "}
              </>
            )}
            {u && u.lidos !== null && <>Última execução: {detalhesDa(u).join(", ")}. </>}
            <span className="so-leitor">Arquivo gerado {dataEHora(geradoEm, agora)}.</span>
          </p>
        </div>
      )}
    </section>
  );
}
