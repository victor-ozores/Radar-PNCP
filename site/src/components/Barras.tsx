import type { CSSProperties } from "react";

import { formataInteiro, plural } from "../lib/formatos";
import type { Linha } from "../lib/painel";

interface Props {
  /** Nome da lista para leitor de tela ("Editais por estado"). */
  nome: string;
  linhas: Linha[];
  /** id da linha que está escolhida no filtro da lista. */
  escolhida?: string | null;
  /** Se informado, cada linha é um botão que filtra a lista pelo que ela representa. */
  aoEscolher?: (linha: Linha) => void;
  /** id da linha que ganha a cor de destaque (aqui: os prazos mais curtos). */
  destaque?: string;
}

/**
 * Barras horizontais: rótulo, barra e valor. É uma lista de verdade (leitor de tela lê "SP, 453
 * editais"); a barra é só o desenho, e o número fica sempre escrito ao lado.
 */
export function Barras({ nome, linhas, escolhida = null, aoEscolher, destaque }: Props) {
  if (linhas.length === 0) return <p className="vazio">Nenhum edital.</p>;
  const maior = Math.max(1, ...linhas.map((l) => l.n));

  return (
    <ul className="barras" aria-label={nome}>
      {linhas.map((l) => {
        const marcada = escolhida === l.id;
        const conteudo = (
          <>
            <span className="barras-rotulo">{l.rotulo}</span>
            <span className="barras-trilho" aria-hidden="true">
              <span
                className={`barras-barra ${destaque === l.id ? "barras-destaque" : ""}`}
                style={{ "--proporcao": l.n / maior } as CSSProperties}
              />
            </span>
            <span className="barras-valor">{formataInteiro(l.n)}</span>
          </>
        );
        const descricao = `${l.rotulo}: ${formataInteiro(l.n)} ${plural(l.n, "edital", "editais")}`;
        return (
          <li key={l.id}>
            {aoEscolher ? (
              <button
                type="button"
                className={`barras-linha barras-botao ${marcada ? "marcada" : ""}`}
                aria-pressed={marcada}
                aria-label={descricao}
                onClick={() => aoEscolher(l)}
              >
                {conteudo}
              </button>
            ) : (
              <div className="barras-linha" role="group" aria-label={descricao}>
                {conteudo}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
