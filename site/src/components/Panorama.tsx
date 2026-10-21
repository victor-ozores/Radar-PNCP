import { useMemo } from "react";

import { formataInteiro, formataValor, plural } from "../lib/formatos";
import {
  faixasPrazo,
  porUf,
  resumoValores,
  termosMaisCitados,
  topMunicipios,
} from "../lib/painel";
import type { Edital } from "../lib/types";
import { Barras, TabelaBarras } from "./Barras";

/** `editais`: os que combinam e ainda estão abertos. */
export function Panorama({ editais, agora }: { editais: Edital[]; agora: Date }) {
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

  return (
    <section className="panorama" aria-labelledby="panorama-titulo">
      <h2 id="panorama-titulo">Panorama dos {formataInteiro(editais.length)} editais que combinam</h2>
      <div className="grade">
        <Barras
          id="graf-prazo"
          titulo="Quando acaba o prazo"
          subtitulo="Dias que faltam para entregar a proposta."
          linhas={dados.prazo}
        />
        <Barras
          id="graf-valor"
          titulo="Quanto valem"
          subtitulo="Valor estimado pelo órgão, por faixa."
          linhas={valores.faixas}
        >
          <p className="nota-grafico">
            Valor mediano: <strong>{valores.mediana === null ? "—" : formataValor(valores.mediana)}</strong>.{" "}
            {valores.semValor > 0 && (
              <>
                {formataInteiro(valores.semValor)} {plural(valores.semValor, "edital", "editais")} sem valor
                informado não entram nas faixas.
              </>
            )}
          </p>
        </Barras>
        <Barras
          id="graf-uf"
          titulo="Onde estão"
          subtitulo="Por estado e pelas cidades com mais editais."
          linhas={dados.ufs}
        >
          {dados.cidades.length > 0 && (
            <>
              <h4 className="subgrafico">Cidades com mais editais</h4>
              <TabelaBarras titulo="Cidade" linhas={dados.cidades} />
            </>
          )}
        </Barras>
        <Barras
          id="graf-termos"
          titulo="Palavras mais encontradas"
          subtitulo="Em quantos editais o robô achou cada palavra do perfil."
          linhas={dados.termos}
        />
      </div>
    </section>
  );
}
