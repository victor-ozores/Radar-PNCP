import { SUAVE, m } from "../animacao";
import { HORAS_ATE_AVISAR, REPO_URL } from "../config";
import { haQuantoTempo, horasDesde } from "../lib/tempo";
import type { Tema } from "../lib/tema";
import type { Robo } from "../lib/types";
import { Icone } from "./Icone";

interface Props {
  robo: Robo | null;
  agora: Date;
  tema: Tema;
  aoAlternarTema: () => void;
}

const LINKS = [
  { href: "#resumo", texto: "Resumo" },
  { href: "#panorama", texto: "Panorama" },
  { href: "#editais", texto: "Editais" },
  { href: "#sobre", texto: "Sobre" },
];

export function BarraTopo({ robo, agora, tema, aoAlternarTema }: Props) {
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
            <span className={`status ${velho ? "status-aviso" : "status-ok"}`} title="Última atualização do robô">
              <span className="status-ponto" aria-hidden="true" />
              <span>
                {ultimoOk === null
                  ? "Sem execução"
                  : velho
                    ? `Parado ${haQuantoTempo(ultimoOk, agora)}`
                    : `Atualizado ${haQuantoTempo(ultimoOk, agora)}`}
              </span>
            </span>
          )}
          <m.button
            type="button"
            className="botao-icone"
            onClick={aoAlternarTema}
            aria-label={tema === "escuro" ? "Usar tema claro" : "Usar tema escuro"}
            title={tema === "escuro" ? "Tema claro" : "Tema escuro"}
            whileTap={{ scale: 0.9 }}
          >
            {/* a chave faz o ícone novo entrar girando quando o tema troca */}
            <m.span
              key={tema}
              className="botao-icone-miolo"
              initial={{ rotate: -80, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              transition={{ duration: 0.3, ease: SUAVE }}
            >
              <Icone nome={tema === "escuro" ? "sol" : "lua"} tam={18} />
            </m.span>
          </m.button>
          <a className="botao-icone" href={REPO_URL} target="_blank" rel="noopener noreferrer" aria-label="Código no GitHub (abre em outra aba)" title="Código no GitHub">
            <Icone nome="github" tam={18} />
          </a>
        </div>
      </div>
    </m.header>
  );
}
