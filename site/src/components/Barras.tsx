import { NA_TELA, SUAVE, m, useReducedMotion } from "../animacao";
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

/** A barra cresce da esquerda quando aparece na tela. Com "menos movimento", já vem do tamanho certo. */
function Barra({ proporcao, destaque, ordem }: { proporcao: number; destaque: boolean; ordem: number }) {
  const reduzido = useReducedMotion();
  const largura = `${proporcao * 100}%`;
  const classe = `barras-barra ${destaque ? "barras-destaque" : ""}`;
  if (reduzido) return <span className={classe} style={{ width: largura }} />;
  return (
    <m.span
      className={classe}
      initial={{ width: "0%" }}
      whileInView={{ width: largura }}
      viewport={NA_TELA}
      transition={{ duration: 0.7, ease: SUAVE, delay: Math.min(ordem, 8) * 0.05 }}
    />
  );
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
      {linhas.map((l, i) => {
        const marcada = escolhida === l.id;
        const conteudo = (
          <>
            <span className="barras-rotulo">{l.rotulo}</span>
            <span className="barras-trilho" aria-hidden="true">
              <Barra proporcao={l.n / maior} destaque={destaque === l.id} ordem={i} />
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
