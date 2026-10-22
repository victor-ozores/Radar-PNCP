import { formataInteiro, formataValor, plural } from "../lib/formatos";
import { FILTRO_INICIAL, type Filtro, type Resumo } from "../lib/painel";
import { dataEHora } from "../lib/tempo";
import type { Painel } from "../lib/types";
import { Icone, type NomeIcone } from "./Icone";

interface Props {
  painel: Painel;
  resumo: Resumo;
  mediana: number | null;
  agora: Date;
  filtro: Filtro;
  /** `rolar`: leva a pessoa até a lista. */
  aoMudar: (filtro: Filtro, rolar: boolean) => void;
}

function listaEm(itens: string[]): string {
  if (itens.length <= 1) return itens.join("");
  return `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`;
}

function Numero({
  icone,
  rotulo,
  valor,
  dica,
  aoClicar,
}: {
  icone: NomeIcone;
  rotulo: string;
  valor: string;
  dica?: string;
  aoClicar?: () => void;
}) {
  const miolo = (
    <>
      <span className="numero-icone">
        <Icone nome={icone} tam={18} />
      </span>
      <span className="numero-texto">
        <span className="numero-rotulo">{rotulo}</span>
        <span className="numero-valor">{valor}</span>
        {dica && <span className="numero-dica">{dica}</span>}
      </span>
    </>
  );
  return aoClicar ? (
    <button type="button" className="numero numero-botao" onClick={aoClicar}>
      {miolo}
    </button>
  ) : (
    <div className="numero">{miolo}</div>
  );
}

export function Hero({ painel, resumo, mediana, agora, filtro, aoMudar }: Props) {
  const { perfil, totais, janela_dias: janela } = painel;
  const so = (parcial: Partial<Filtro>) => aoMudar({ ...FILTRO_INICIAL, ordem: filtro.ordem, ...parcial }, true);

  return (
    <section className="hero" id="resumo" aria-labelledby="hero-titulo">
      <div className="hero-texto">
        <p className="eyebrow">
          <span className="selo-demo">Perfil de demonstração</span>
          <span>{listaEm(perfil.ufs)}</span>
        </p>
        <h1 id="hero-titulo">
          <span className="hero-numero">{formataInteiro(resumo.combinam)}</span>
          <span className="hero-frase">
            {plural(resumo.combinam, "edital aberto combina", "editais abertos combinam")} com o perfil
          </span>
        </h1>
        <p className="hero-sub">
          Todo dia um robô lê o PNCP, o portal nacional de contratações públicas, e separa as obras e os
          serviços de engenharia que combinam com o perfil de uma empresa. Aqui estão os que ainda aceitam
          proposta.
        </p>
        <div className="hero-acoes">
          <a className="botao-primario" href="#editais">
            Ver os editais
          </a>
          <button type="button" className="botao" onClick={() => so({ prazoMax: 7 })}>
            Só os que vencem em até 7 dias
          </button>
        </div>
        <p className="escopo">
          Entre {formataInteiro(totais.abertos)} editais abertos com prazo nos próximos {janela} dias, nas{" "}
          {perfil.ufs.length} UFs e {perfil.modalidades.length} modalidades que o robô acompanha. Dados de{" "}
          {dataEHora(painel.gerado_em, agora)}.
        </p>
      </div>

      <div className="numeros">
        <Numero
          icone="relogio"
          rotulo="Prazo acaba em até 7 dias"
          valor={formataInteiro(resumo.vencemEm7Dias)}
          dica="Toque para ver"
          aoClicar={() => so({ prazoMax: 7 })}
        />
        <Numero
          icone="moeda"
          rotulo="Valor mediano estimado"
          valor={mediana === null ? "—" : formataValor(mediana)}
          dica="Metade vale mais, metade menos"
        />
        <Numero
          icone="documento"
          rotulo="Em registro de preços"
          valor={formataInteiro(resumo.registroDePrecos)}
          dica="Toque para ver"
          aoClicar={() => so({ registro: true })}
        />
        {resumo.emParte > 0 && (
          <Numero
            icone="grafico"
            rotulo="Combinam só em parte"
            valor={formataInteiro(resumo.emParte)}
            dica="Toque para incluir na lista"
            aoClicar={() => so({ incluirEmParte: true })}
          />
        )}
      </div>
    </section>
  );
}
