import { useMemo, useState, type ReactNode } from "react";

import { NA_TELA, m, subir } from "../animacao";
import { formataInteiro, formataValor, plural } from "../lib/formatos";
import {
  FAIXAS_PRAZO,
  type Filtro,
  faixasPrazo,
  intervaloDaFaixa,
  porUf,
  resumoValores,
  termosMaisCitados,
  topMunicipios,
} from "../lib/painel";
import { diaBR } from "../lib/tempo";
import type { Edital } from "../lib/types";
import { Barras } from "./Barras";

interface Props {
  /** Os editais que combinam e ainda estão abertos. */
  editais: Edital[];
  agora: Date;
  filtro: Filtro;
  /** `rolar`: leva a pessoa até a lista depois de escolher uma barra. */
  aoMudar: (filtro: Filtro, rolar: boolean) => void;
}

interface CartaoProps {
  id: string;
  titulo: string;
  subtitulo: string;
  /** Posição no celular, onde os cartões ficam em uma coluna só. */
  ordem: number;
  extra?: ReactNode;
  children: ReactNode;
}

function Cartao({ id, titulo, subtitulo, ordem, extra, children }: CartaoProps) {
  return (
    <m.section
      className="cartao"
      aria-labelledby={id}
      style={{ order: ordem }}
      variants={subir}
      initial="oculto"
      whileInView="visivel"
      viewport={NA_TELA}
    >
      <header className="cartao-topo">
        <div>
          <h3 id={id}>{titulo}</h3>
          <p className="subtitulo">{subtitulo}</p>
        </div>
        {extra}
      </header>
      {children}
    </m.section>
  );
}

export function Panorama({ editais, agora, filtro, aoMudar }: Props) {
  const [aba, setAba] = useState<"estados" | "cidades">("estados");
  const hoje = diaBR(agora);
  const dados = useMemo(
    () => ({
      prazo: faixasPrazo(editais, agora),
      ufs: porUf(editais),
      cidades: topMunicipios(editais, 8),
      termos: termosMaisCitados(editais, 10),
      valores: resumoValores(editais),
    }),
    [editais, agora],
  );
  const { valores } = dados;

  /** Escolhe a barra; escolher de novo a mesma tira o filtro. */
  const alterna = (campo: "uf" | "cidade" | "termo" | "faixa") => (l: { id: string }) =>
    aoMudar({ ...filtro, [campo]: filtro[campo] === l.id ? "" : l.id }, filtro[campo] !== l.id);

  // a faixa do gráfico vira datas no filtro; está "escolhida" quando as datas são exatamente as dela
  const prazoEscolhido =
    FAIXAS_PRAZO.find((f) => {
      const { de, ate } = intervaloDaFaixa(f, hoje);
      return de === filtro.prazoDe && ate === filtro.prazoAte;
    })?.id ?? null;
  const escolhePrazo = (l: { id: string }) => {
    const faixa = FAIXAS_PRAZO.find((f) => f.id === l.id);
    if (!faixa) return;
    const ativa = prazoEscolhido === l.id;
    const { de, ate } = intervaloDaFaixa(faixa, hoje);
    aoMudar({ ...filtro, prazoDe: ativa ? "" : de, prazoAte: ativa ? "" : ate }, !ativa);
  };

  return (
    <section className="panorama" id="panorama" aria-labelledby="panorama-titulo">
      <div className="secao-topo">
        <h2 id="panorama-titulo">Panorama dos {formataInteiro(editais.length)} editais</h2>
        <p className="dica">Toque numa barra para filtrar a lista abaixo.</p>
      </div>

      {/* Duas colunas de alturas parecidas no computador; no celular os cartões seguem a ordem do número. */}
      <div className="grade">
        <div className="coluna">
          <Cartao id="graf-prazo" ordem={1} titulo="Quando acaba o prazo" subtitulo="Dias que faltam para entregar a proposta.">
            <Barras
              nome="Editais por prazo"
              linhas={dados.prazo}
              destaque="ate3"
              escolhida={prazoEscolhido}
              aoEscolher={escolhePrazo}
            />
          </Cartao>

          <Cartao
            id="graf-termos"
            ordem={4}
            titulo="Palavras mais encontradas"
            subtitulo="Em quantos editais o robô achou cada palavra do perfil."
          >
            <Barras
              nome="Editais por palavra"
              linhas={dados.termos}
              escolhida={filtro.termo || null}
              aoEscolher={alterna("termo")}
            />
          </Cartao>
        </div>

        <div className="coluna">
          <Cartao
            id="graf-valor"
            ordem={2}
            titulo="Quanto valem"
            subtitulo="Valor estimado pelo órgão, por faixa."
            extra={
              <p className="mini-numero">
                <span>Mediana</span>
                <strong>{valores.mediana === null ? "—" : formataValor(valores.mediana)}</strong>
              </p>
            }
          >
            <Barras
              nome="Editais por faixa de valor"
              linhas={valores.faixas}
              escolhida={filtro.faixa || null}
              aoEscolher={alterna("faixa")}
            />
            {valores.semValor > 0 && (
              <p className="nota-grafico">
                {formataInteiro(valores.semValor)} {plural(valores.semValor, "edital", "editais")} sem valor
                informado (fora das faixas).
              </p>
            )}
          </Cartao>

          <Cartao
            id="graf-uf"
            ordem={3}
            titulo="Onde estão"
            subtitulo="Estados e cidades com mais editais."
            extra={
              <div className="abas" role="tablist" aria-label="Ver por">
                {(["estados", "cidades"] as const).map((a) => (
                  <button
                    key={a}
                    type="button"
                    role="tab"
                    aria-selected={aba === a}
                    className={aba === a ? "ativa" : ""}
                    onClick={() => setAba(a)}
                  >
                    {a === "estados" ? "Estados" : "Cidades"}
                  </button>
                ))}
              </div>
            }
          >
            {aba === "estados" ? (
              <Barras nome="Editais por estado" linhas={dados.ufs} escolhida={filtro.uf || null} aoEscolher={alterna("uf")} />
            ) : (
              <Barras
                nome="Editais por cidade"
                linhas={dados.cidades}
                escolhida={filtro.cidade || null}
                aoEscolher={alterna("cidade")}
              />
            )}
          </Cartao>
        </div>
      </div>
    </section>
  );
}
