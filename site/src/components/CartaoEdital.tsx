import { Fragment, memo } from "react";

import { SUAVE, m } from "../animacao";
import { formataValor, limpaObjeto, localidade, nomeDoOrgao, suavizaCaixa, valorConfiavel } from "../lib/formatos";
import { dataEHora, diaDoMes, diasAte, emQuantosDias, horaCurta, mesCurto, dataCurta } from "../lib/tempo";
import { ROTULO_COMBINA } from "../lib/painel";
import type { Edital, Repetido } from "../lib/types";
import { Icone } from "./Icone";

/** "nº 34/2026", ou "outro registro" quando o órgão não preencheu um número que preste. */
const rotuloDoRepetido = (r: Repetido) => (r.numero ? `nº ${r.numero}` : "outro registro");

type Urgencia = "urgente" | "atencao" | "calmo";

function urgenciaDe(dias: number): Urgencia {
  if (dias <= 2) return "urgente";
  if (dias <= 7) return "atencao";
  return "calmo";
}

interface Props {
  edital: Edital;
  agora: Date;
  /** Lugar do cartão na página atual da lista; os primeiros entram em sequência, os outros juntos. */
  posicao: number;
  /** Marcado para levar ao Excel. */
  marcado: boolean;
  aoMarcar: (id: string) => void;
}

function CartaoEditalSemMemo({ edital: e, agora, posicao, marcado, aoMarcar }: Props) {
  const dias = diasAte(e.prazo, agora);
  const urgencia = urgenciaDe(dias);
  const abreDepois = e.abertura !== null && Date.parse(e.abertura) > agora.getTime();
  const semValor = valorConfiavel(e.valor) === null;
  const onde = localidade(e.municipio, e.uf);
  const objeto = suavizaCaixa(limpaObjeto(e.objeto));
  const resumoDoObjeto = objeto.length > 80 ? `${objeto.slice(0, 80)}…` : objeto;

  return (
    <m.li
      className={`edital ${marcado ? "edital-marcado" : ""}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: SUAVE, delay: Math.min(posicao, 8) * 0.035 }}
    >
      <div className="edital-lado">
        <label className="edital-marca">
          <input
            type="checkbox"
            checked={marcado}
            onChange={() => aoMarcar(e.id)}
            aria-label={`Marcar para exportar: ${resumoDoObjeto}`}
          />
        </label>
        <div className={`prazo-bloco prazo-${urgencia}`}>
          <span className="so-leitor">
            Propostas até {dataEHora(e.prazo, agora)} ({emQuantosDias(e.prazo, agora)}).
          </span>
          <span aria-hidden="true" className="prazo-dia">
            {diaDoMes(e.prazo)}
          </span>
          <span aria-hidden="true" className="prazo-mes">
            {mesCurto(e.prazo)}
          </span>
          <span aria-hidden="true" className="prazo-hora">
            {horaCurta(e.prazo)}
          </span>
          <span aria-hidden="true" className="prazo-falta">
            {emQuantosDias(e.prazo, agora)}
          </span>
        </div>
      </div>

      <div className="edital-corpo">
        <div className="edital-selos">
          <span className={`selo selo-${e.combina}`}>{ROTULO_COMBINA[e.combina]}</span>
          {e.registro_de_precos && <span className="etiqueta etiqueta-destaque">Registro de preços</span>}
          {abreDepois && e.abertura && (
            <span className="etiqueta etiqueta-destaque">Propostas abrem em {dataCurta(e.abertura)}</span>
          )}
        </div>

        <p className="edital-objeto">{objeto}</p>

        <p className="edital-meta">
          <span className="meta-item">
            <Icone nome="predio" tam={16} />
            {nomeDoOrgao(e.orgao, e.municipio)}
          </span>
          {onde && (
            <span className="meta-item">
              <Icone nome="pino" tam={16} />
              {onde}
            </span>
          )}
        </p>

        <p className="edital-meta">
          <span className={`meta-item ${semValor ? "sem-valor" : "valor-edital"}`}>
            <Icone nome="moeda" tam={16} />
            {formataValor(e.valor)}
          </span>
          <span className="meta-item">
            <Icone nome="documento" tam={16} />
            {e.modalidade}
            {e.numero && ` nº ${e.numero}`}
          </span>
        </p>

        {e.repetidos.length > 0 && (
          <p className="edital-repetido">
            <Icone nome="copia" tam={16} />
            <span>
              Também publicado como{" "}
              {e.repetidos.map((r, i) => (
                <Fragment key={r.id}>
                  {i > 0 && ", "}
                  {r.link ? (
                    <a href={r.link} target="_blank" rel="noopener noreferrer">
                      {rotuloDoRepetido(r)}
                      <span className="so-leitor"> (abre em outra aba)</span>
                    </a>
                  ) : (
                    rotuloDoRepetido(r)
                  )}
                </Fragment>
              ))}
            </span>
          </p>
        )}

        {e.termos.length > 0 && (
          <ul className="etiquetas" aria-label="Palavras do perfil encontradas">
            {e.termos.map((t) => (
              <li key={t} className="etiqueta">
                {t}
              </li>
            ))}
          </ul>
        )}
      </div>

      {e.link && (
        <a className="botao-link" href={e.link} target="_blank" rel="noopener noreferrer">
          Ver no PNCP
          <span className="so-leitor"> (abre em outra aba)</span>
          <Icone nome="externo" tam={16} />
        </a>
      )}
    </m.li>
  );
}

/** Marcar um cartão não refaz os outros 29 (nem a animação de entrada deles). */
export const CartaoEdital = memo(CartaoEditalSemMemo);
