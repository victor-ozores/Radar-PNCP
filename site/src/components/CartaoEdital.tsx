import { formataValor, limpaObjeto, localidade, valorConfiavel } from "../lib/formatos";
import { dataCurta, dataEHora, diasAte, emQuantosDias } from "../lib/tempo";
import type { Combina, Edital } from "../lib/types";

const SELO: Record<Combina, string> = {
  muito: "Combina muito",
  combina: "Combina",
  parcial: "Combina em parte",
};

export function CartaoEdital({ edital: e, agora }: { edital: Edital; agora: Date }) {
  const urgente = diasAte(e.prazo, agora) <= 2;
  const abreDepois = e.abertura !== null && Date.parse(e.abertura) > agora.getTime();
  const sinalValor = valorConfiavel(e.valor) === null;

  return (
    <li className="edital">
      <div className="edital-topo">
        <span className={`selo selo-${e.combina}`}>{SELO[e.combina]}</span>
        <p className={`edital-prazo ${urgente ? "urgente" : ""}`}>
          <span aria-hidden="true">⏰ </span>
          Propostas até <strong>{dataEHora(e.prazo, agora)}</strong>
          {diasAte(e.prazo, agora) > 1 && <> ({emQuantosDias(e.prazo, agora)})</>}
        </p>
      </div>
      <p className="edital-objeto">{limpaObjeto(e.objeto)}</p>
      <p className="edital-quem">
        {e.orgao}
        {localidade(e.municipio, e.uf) && <> · {localidade(e.municipio, e.uf)}</>}
      </p>
      <p className="edital-linha">
        <span className={sinalValor ? "sem-valor" : "valor-edital"}>{formataValor(e.valor)}</span>
        <span className="separador" aria-hidden="true">
          ·
        </span>
        <span>{e.modalidade}</span>
      </p>
      {(e.registro_de_precos || abreDepois || e.termos.length > 0) && (
        <ul className="etiquetas" aria-label="Detalhes do edital">
          {e.registro_de_precos && <li className="etiqueta etiqueta-destaque">Registro de preços</li>}
          {abreDepois && e.abertura && (
            <li className="etiqueta etiqueta-destaque">Propostas abrem em {dataCurta(e.abertura)}</li>
          )}
          {e.termos.map((t) => (
            <li key={t} className="etiqueta">
              {t}
            </li>
          ))}
        </ul>
      )}
      {e.link && (
        <p className="edital-acao">
          <a href={e.link} target="_blank" rel="noopener noreferrer">
            Ver o edital no PNCP<span className="so-leitor"> (abre em outra aba)</span>
            <span aria-hidden="true"> ↗</span>
          </a>
        </p>
      )}
    </li>
  );
}
