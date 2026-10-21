import { formataInteiro, formataValor, plural } from "../lib/formatos";
import type { Resumo } from "../lib/painel";
import { dataEHora } from "../lib/tempo";
import type { Painel } from "../lib/types";

interface Props {
  painel: Painel;
  resumo: Resumo;
  mediana: number | null;
  agora: Date;
}

function listaEm(itens: string[]): string {
  if (itens.length <= 1) return itens.join("");
  return `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`;
}

export function Destaque({ painel, resumo, mediana, agora }: Props) {
  const { perfil, totais, janela_dias: janela } = painel;
  return (
    <section className="destaque" aria-labelledby="destaque-titulo">
      <h2 id="destaque-titulo" className="so-leitor">
        Resumo
      </h2>
      <div className="hero">
        <p className="hero-numero">{formataInteiro(resumo.combinam)}</p>
        <p className="hero-texto">
          {plural(resumo.combinam, "edital aberto combina", "editais abertos combinam")} com o perfil
        </p>
      </div>
      <p className="subtitulo">
        Entre {formataInteiro(totais.abertos)} editais abertos, com prazo nos próximos {janela} dias, nas{" "}
        {perfil.ufs.length} UFs ({listaEm(perfil.ufs)}) e {perfil.modalidades.length} modalidades que o robô
        acompanha. Dados de {dataEHora(painel.gerado_em, agora)}.
      </p>
      <dl className="numeros">
        <div>
          <dt>Prazo acaba em até 7 dias</dt>
          <dd>{formataInteiro(resumo.vencemEm7Dias)}</dd>
        </div>
        <div>
          <dt>Valor mediano estimado</dt>
          <dd>{mediana === null ? "—" : formataValor(mediana)}</dd>
        </div>
        <div>
          <dt>Em registro de preços</dt>
          <dd>{formataInteiro(resumo.registroDePrecos)}</dd>
        </div>
      </dl>
      {resumo.emParte > 0 && (
        <p className="subtitulo">
          Há ainda {formataInteiro(resumo.emParte)}{" "}
          {plural(resumo.emParte, "edital que combina", "editais que combinam")} só em parte: aparecem na
          lista se você marcar essa opção.
        </p>
      )}
    </section>
  );
}
