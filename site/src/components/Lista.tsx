import { useEffect, useMemo, useState } from "react";

import { TAMANHO_PAGINA } from "../config";
import { formataInteiro, plural } from "../lib/formatos";
import { filtrar, filtroLimpo, filtrosAtivos, type Filtro } from "../lib/painel";
import type { Edital } from "../lib/types";
import { CartaoEdital } from "./CartaoEdital";
import { Filtros } from "./Filtros";

interface Props {
  /** Os editais abertos (inclui os que combinam só em parte). */
  editais: Edital[];
  agora: Date;
  filtro: Filtro;
  aoMudar: (filtro: Filtro) => void;
}

export function Lista({ editais, agora, filtro, aoMudar }: Props) {
  const [visiveis, setVisiveis] = useState(TAMANHO_PAGINA);

  const ufs = useMemo(
    () => [...new Set(editais.map((e) => e.uf).filter((u): u is string => !!u))].sort(),
    [editais],
  );
  const emParte = useMemo(() => editais.filter((e) => e.combina === "parcial").length, [editais]);
  const registro = useMemo(
    () => editais.filter((e) => e.combina !== "parcial" && e.registro_de_precos).length,
    [editais],
  );
  const achados = useMemo(() => filtrar(editais, filtro, agora), [editais, filtro, agora]);

  // mudou o filtro: volta a mostrar só a primeira página
  useEffect(() => setVisiveis(TAMANHO_PAGINA), [filtro]);

  const filtrado = filtrosAtivos(filtro).length > 0;
  const mostrando = Math.min(visiveis, achados.length);

  return (
    <section className="lista" id="editais" aria-labelledby="lista-titulo">
      <div className="secao-topo">
        <h2 id="lista-titulo">Editais abertos</h2>
        <p className="contagem" role="status">
          {achados.length === 0
            ? "Nenhum edital com esses filtros."
            : `Mostrando ${formataInteiro(mostrando)} de ${formataInteiro(achados.length)} ${plural(achados.length, "edital", "editais")}`}
        </p>
      </div>

      <Filtros filtro={filtro} aoMudar={aoMudar} ufs={ufs} emParte={emParte} registro={registro} />

      {achados.length > 0 ? (
        <ul className="editais">
          {achados.slice(0, visiveis).map((e) => (
            <CartaoEdital key={e.id} edital={e} agora={agora} />
          ))}
        </ul>
      ) : (
        <div className="sem-resultado">
          <p>Nenhum edital combina com essa escolha.</p>
          {filtrado && (
            <button type="button" className="botao" onClick={() => aoMudar(filtroLimpo(filtro))}>
              Limpar filtros
            </button>
          )}
        </div>
      )}

      {achados.length > visiveis && (
        <p className="mais">
          <button type="button" className="botao" onClick={() => setVisiveis((v) => v + TAMANHO_PAGINA)}>
            Mostrar mais {formataInteiro(Math.min(TAMANHO_PAGINA, achados.length - visiveis))}
          </button>
        </p>
      )}
    </section>
  );
}
