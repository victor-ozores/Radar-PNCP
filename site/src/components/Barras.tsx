import type { CSSProperties, ReactNode } from "react";

import { formataInteiro } from "../lib/formatos";
import type { Linha } from "../lib/painel";

/**
 * Barras horizontais feitas com uma tabela de verdade: quem usa leitor de tela, ou só quer os
 * números, tem a tabela; a barra é só o desenho ao lado de cada valor.
 */
export function TabelaBarras({ titulo, linhas }: { titulo: string; linhas: Linha[] }) {
  const maior = Math.max(1, ...linhas.map((l) => l.n));
  return (
    <table className="barras">
      <thead className="so-leitor">
        <tr>
          <th scope="col">{titulo}</th>
          <th scope="col">Editais</th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((l) => (
          <tr key={l.id}>
            <th scope="row">{l.rotulo}</th>
            <td>
              <div className="celula">
                <span
                  className="barra"
                  style={{ "--proporcao": l.n / maior } as CSSProperties}
                  aria-hidden="true"
                />
                <span className="valor">{formataInteiro(l.n)}</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface Props {
  id: string;
  titulo: string;
  subtitulo?: string;
  linhas: Linha[];
  children?: ReactNode;
}

export function Barras({ id, titulo, subtitulo, linhas, children }: Props) {
  return (
    <section className="cartao" aria-labelledby={id}>
      <h3 id={id}>{titulo}</h3>
      {subtitulo && <p className="subtitulo">{subtitulo}</p>}
      {linhas.length === 0 ? (
        <p className="vazio">Nenhum edital.</p>
      ) : (
        <TabelaBarras titulo={titulo} linhas={linhas} />
      )}
      {children}
    </section>
  );
}
