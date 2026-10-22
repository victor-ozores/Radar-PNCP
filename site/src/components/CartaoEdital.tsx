import { formataValor, limpaObjeto, localidade, suavizaCaixa, valorConfiavel } from "../lib/formatos";
import { dataEHora, diaDoMes, diasAte, emQuantosDias, horaCurta, mesCurto, dataCurta } from "../lib/tempo";
import type { Combina, Edital } from "../lib/types";
import { Icone } from "./Icone";

const SELO: Record<Combina, string> = {
  muito: "Combina muito",
  combina: "Combina",
  parcial: "Combina em parte",
};

type Urgencia = "urgente" | "atencao" | "calmo";

function urgenciaDe(dias: number): Urgencia {
  if (dias <= 2) return "urgente";
  if (dias <= 7) return "atencao";
  return "calmo";
}

export function CartaoEdital({ edital: e, agora }: { edital: Edital; agora: Date }) {
  const dias = diasAte(e.prazo, agora);
  const urgencia = urgenciaDe(dias);
  const abreDepois = e.abertura !== null && Date.parse(e.abertura) > agora.getTime();
  const semValor = valorConfiavel(e.valor) === null;
  const onde = localidade(e.municipio, e.uf);

  return (
    <li className="edital">
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

      <div className="edital-corpo">
        <div className="edital-selos">
          <span className={`selo selo-${e.combina}`}>{SELO[e.combina]}</span>
          {e.registro_de_precos && <span className="etiqueta etiqueta-destaque">Registro de preços</span>}
          {abreDepois && e.abertura && (
            <span className="etiqueta etiqueta-destaque">Propostas abrem em {dataCurta(e.abertura)}</span>
          )}
        </div>

        <p className="edital-objeto">{suavizaCaixa(limpaObjeto(e.objeto))}</p>

        <p className="edital-meta">
          <span className="meta-item">
            <Icone nome="predio" tam={16} />
            {suavizaCaixa(e.orgao, true)}
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
          </span>
        </p>

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
    </li>
  );
}
