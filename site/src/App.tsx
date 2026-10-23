import { useCallback, useEffect, useMemo, useState } from "react";

import { Animacao } from "./animacao";
import { BarraTopo } from "./components/BarraTopo";
import { Esqueleto } from "./components/Esqueleto";
import { Hero } from "./components/Hero";
import { Lista } from "./components/Lista";
import { Panorama } from "./components/Panorama";
import { PainelRobo } from "./components/PainelRobo";
import { Rodape } from "./components/Rodape";
import { PAINEL_URL, PNCP_URL } from "./config";
import { carregaPainel } from "./lib/carrega";
import {
  FILTRO_INICIAL,
  PainelInvalido,
  combinam,
  resumir,
  resumoValores,
  vigentes,
  type Filtro,
} from "./lib/painel";
import type { Painel } from "./lib/types";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro"; mensagem: string; versaoNova: boolean }
  | { tipo: "pronto"; painel: Painel };

/** A hora de agora, renovada a cada minuto: o que venceu some e os "em X dias" acompanham. */
function useAgora(intervaloMs = 60_000): Date {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), intervaloMs);
    return () => clearInterval(id);
  }, [intervaloMs]);
  return agora;
}

function rolarAteLista() {
  const lista = document.getElementById("editais");
  if (!lista) return;
  const reduzido = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  lista.scrollIntoView?.({ behavior: reduzido ? "auto" : "smooth", block: "start" });
}

function Erro({ mensagem, versaoNova, aoTentar }: { mensagem: string; versaoNova: boolean; aoTentar: () => void }) {
  return (
    <div className="aviso-erro" role="alert">
      <h2>Não consegui carregar os editais</h2>
      {versaoNova ? (
        <p>O painel foi atualizado e esta página ficou para trás. Recarregue a página (Ctrl+F5) para ver a versão nova.</p>
      ) : (
        <p>
          Os dados ficam em um arquivo público que o robô atualiza uma vez por dia, e ele não respondeu agora.
          Tente de novo em alguns minutos. Enquanto isso, os editais continuam no{" "}
          <a href={PNCP_URL} target="_blank" rel="noopener noreferrer">
            PNCP
          </a>
          .
        </p>
      )}
      <p className="detalhe-erro">Detalhe técnico: {mensagem}</p>
      <button type="button" className="botao" onClick={aoTentar}>
        Tentar de novo
      </button>
    </div>
  );
}

export function App() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [filtro, setFiltro] = useState<Filtro>(FILTRO_INICIAL);
  const agora = useAgora();

  useEffect(() => {
    const controle = new AbortController();
    setEstado({ tipo: "carregando" });
    carregaPainel(PAINEL_URL, controle.signal)
      .then((painel) => setEstado({ tipo: "pronto", painel }))
      .catch((erro: unknown) => {
        if (controle.signal.aborted) return;
        setEstado({
          tipo: "erro",
          mensagem: erro instanceof Error ? erro.message : String(erro),
          versaoNova: erro instanceof PainelInvalido && erro.motivo === "versao",
        });
      });
    return () => controle.abort();
  }, [tentativa]);

  const tentarDeNovo = useCallback(() => setTentativa((n) => n + 1), []);
  const painel = estado.tipo === "pronto" ? estado.painel : null;

  const abertos = useMemo(() => (painel ? vigentes(painel.editais, agora) : []), [painel, agora]);
  const fortes = useMemo(() => combinam(abertos), [abertos]);
  const resumo = useMemo(() => resumir(abertos, agora), [abertos, agora]);
  const mediana = useMemo(() => resumoValores(fortes).mediana, [fortes]);

  /**
   * Muda o filtro; `rolar` leva a pessoa até a lista. Pode rolar já: o filtro só muda o que está
   * dentro da lista, então o ponto de chegada (o topo dela) não se mexe.
   */
  const mudaFiltro = useCallback((novo: Filtro, rolar = false) => {
    setFiltro(novo);
    if (rolar) rolarAteLista();
  }, []);

  return (
    <Animacao>
      <div className="pagina">
        <a className="pular" href="#editais">
          Pular para a lista de editais
        </a>
        <BarraTopo robo={painel?.robo ?? null} agora={agora} />
        <main>
          {estado.tipo === "carregando" && <Esqueleto />}
          {estado.tipo === "erro" && (
            <Erro mensagem={estado.mensagem} versaoNova={estado.versaoNova} aoTentar={tentarDeNovo} />
          )}
          {painel && (
            <>
              <Hero
                painel={painel}
                fortes={fortes}
                resumo={resumo}
                mediana={mediana}
                agora={agora}
                filtro={filtro}
                aoMudar={mudaFiltro}
              />
              <PainelRobo robo={painel.robo} geradoEm={painel.gerado_em} agora={agora} />
              <Panorama editais={fortes} agora={agora} filtro={filtro} aoMudar={mudaFiltro} />
              <Lista
                editais={abertos}
                agora={agora}
                filtro={filtro}
                aoMudar={mudaFiltro}
                origem={{ geradoEm: painel.gerado_em, perfil: painel.perfil.nome }}
              />
            </>
          )}
        </main>
        <Rodape perfil={painel?.perfil ?? null} />
      </div>
    </Animacao>
  );
}
