import { useCallback, useEffect, useMemo, useState } from "react";

import { Destaque } from "./components/Destaque";
import { FaixaRobo } from "./components/FaixaRobo";
import { Lista } from "./components/Lista";
import { Panorama } from "./components/Panorama";
import { Rodape } from "./components/Rodape";
import { Topo } from "./components/Topo";
import { PAINEL_URL, PNCP_URL } from "./config";
import { carregaPainel } from "./lib/carrega";
import { PainelInvalido, combinam, resumir, resumoValores, vigentes } from "./lib/painel";
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

  return (
    <div className="pagina">
      <Topo perfil={painel?.perfil ?? null} />
      <main>
        {estado.tipo === "carregando" && (
          <p className="carregando" role="status">
            Carregando os editais…
          </p>
        )}
        {estado.tipo === "erro" && (
          <Erro mensagem={estado.mensagem} versaoNova={estado.versaoNova} aoTentar={tentarDeNovo} />
        )}
        {painel && (
          <>
            <FaixaRobo robo={painel.robo} geradoEm={painel.gerado_em} agora={agora} />
            <Destaque painel={painel} resumo={resumo} mediana={mediana} agora={agora} />
            <Panorama editais={fortes} agora={agora} />
            <Lista editais={abertos} agora={agora} />
          </>
        )}
      </main>
      <Rodape perfil={painel?.perfil ?? null} />
    </div>
  );
}
