import { SUAVE, m } from "../animacao";
import { HORAS_ATE_AVISAR, REPO_URL } from "../config";
import { haQuantoTempo, horasDesde } from "../lib/tempo";
import type { Robo } from "../lib/types";
import { Icone } from "./Icone";

interface Props {
  robo: Robo | null;
  agora: Date;
}

const LINKS = [
  { href: "#resumo", texto: "Resumo" },
  { href: "#robo", texto: "Robô" },
  { href: "#panorama", texto: "Panorama" },
  { href: "#editais", texto: "Editais" },
  { href: "#sobre", texto: "Sobre" },
];

export function BarraTopo({ robo, agora }: Props) {
  const ultimoOk = robo?.ultima_execucao_ok_em ?? null;
  const velho = robo !== null && (ultimoOk === null || horasDesde(ultimoOk, agora) > HORAS_ATE_AVISAR);

  return (
    <m.header
      className="barra-topo"
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: SUAVE }}
    >
      <div className="barra-interna">
        <a className="marca" href="#resumo" aria-label="Radar de Licitações PNCP, ir para o início">
          <span className="marca-icone">
            <Icone nome="radar" tam={20} />
          </span>
          <span className="marca-nome">
            Radar de Licitações <span className="marca-pncp">PNCP</span>
          </span>
        </a>

        <nav className="navegacao" aria-label="Seções da página">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href}>
              {l.texto}
            </a>
          ))}
        </nav>

        <div className="barra-acoes">
          {robo && (
            <a className={`status ${velho ? "status-aviso" : "status-ok"}`} href="#robo" title="Última atualização do robô. Toque para ver o painel do robô.">
              <span className="status-ponto" aria-hidden="true" />
              <span>
                {ultimoOk === null
                  ? "Sem execução"
                  : velho
                    ? `Parado ${haQuantoTempo(ultimoOk, agora)}`
                    : `Atualizado ${haQuantoTempo(ultimoOk, agora)}`}
              </span>
            </a>
          )}
          <a className="botao-icone" href={REPO_URL} target="_blank" rel="noopener noreferrer" aria-label="Código no GitHub (abre em outra aba)" title="Código no GitHub">
            <Icone nome="github" tam={18} />
          </a>
        </div>
      </div>
    </m.header>
  );
}
