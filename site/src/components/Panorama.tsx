import { useMemo, type ReactNode } from "react";

import { NA_TELA, m, subir } from "../animacao";
import { formataInteiro, formataValor, plural } from "../lib/formatos";
import { dicaCidade, dicaPrazo, dicaTermo, dicaUf, dicaValor } from "../lib/historia";
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
import { Dica } from "./Dica";

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
  /** O que o gráfico mostra, numa frase calculada dos dados. */
  historia?: string | null;
  /** Explicação do termo, no balão do "?" ao lado do título. */
  dica?: { pergunta: string; texto: ReactNode };
  /** Posição no celular, onde os cartões ficam em uma coluna só. */
  ordem: number;
  extra?: ReactNode;
  children: ReactNode;
}

function Cartao({ id, titulo, subtitulo, historia, dica, ordem, extra, children }: CartaoProps) {
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
          <div className="cartao-titulo">
            <h3 id={id}>{titulo}</h3>
            {dica && <Dica rotulo={dica.pergunta}>{dica.texto}</Dica>}
          </div>
          <p className="subtitulo">{subtitulo}</p>
        </div>
        {extra}
      </header>
      {historia && <p className="historia-grafico">{historia}</p>}
      {children}
    </m.section>
  );
}

export function Panorama({ editais, agora, filtro, aoMudar }: Props) {
  const hoje = diaBR(agora);
  const dados = useMemo(
    () => ({
      prazo: faixasPrazo(editais, agora),
      ufs: porUf(editais),
      cidades: topMunicipios(editais, 6),
      termos: termosMaisCitados(editais, 8),
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
        <p className="dica-secao">
          De onde vêm, quanto valem e quando vencem. Toque numa barra para filtrar a lista abaixo.
        </p>
      </div>

      {/* Duas colunas de alturas parecidas no computador; no celular os cartões seguem a ordem do número. */}
      <div className="grade">
        <div className="coluna">
          <Cartao
            id="graf-prazo"
            ordem={1}
            titulo="Quando acaba o prazo"
            subtitulo="Dias que faltam para entregar a proposta."
            historia={dicaPrazo(dados.prazo)}
            dica={{
              pergunta: "O que mostra o gráfico de prazos?",
              texto:
                "Agrupa os editais pelos dias que faltam até o fim do prazo de proposta. A barra laranja é a dos mais urgentes. Tocar numa barra filtra a lista pelas datas dela.",
            }}
          >
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
            historia={dicaTermo(dados.termos, editais.length)}
            dica={{
              pergunta: "O que são as palavras do perfil?",
              texto:
                "O perfil tem uma lista de palavras que indicam o tipo de obra ou serviço (reforma, pavimentação, drenagem…). O robô procura essas palavras no objeto de cada edital. Um edital pode ter várias.",
            }}
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
            historia={dicaValor(valores)}
            dica={{
              pergunta: "O que é o valor estimado?",
              texto:
                "É quanto o órgão calcula que a contratação vai custar. Não é o preço final, que só aparece depois da disputa. Valores simbólicos (abaixo de R$ 1 mil) são tratados como não informados.",
            }}
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
            historia={[dicaUf(dados.ufs, editais.length), dicaCidade(dados.cidades)].filter(Boolean).join(" ")}
          >
            <p className="subgrupo">Por estado</p>
            <Barras nome="Editais por estado" linhas={dados.ufs} escolhida={filtro.uf || null} aoEscolher={alterna("uf")} />
            <p className="subgrupo">Por cidade</p>
            <Barras
              nome="Editais por cidade"
              linhas={dados.cidades}
              escolhida={filtro.cidade || null}
              aoEscolher={alterna("cidade")}
            />
          </Cartao>
        </div>
      </div>
    </section>
  );
}
