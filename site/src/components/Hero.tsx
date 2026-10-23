import { emSequencia, m, subir, useContagem } from "../animacao";
import { formataInteiro, formataValor, plural } from "../lib/formatos";
import { FILTRO_INICIAL, atePrazoEmDias, type Filtro, type Resumo } from "../lib/painel";
import { dataEHora, diaBR } from "../lib/tempo";
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

const PASSOS = [
  "Veja o resumo e os gráficos",
  "Toque numa barra ou use os filtros",
  "Abra o edital no PNCP para ver os detalhes",
];

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
    <m.button type="button" className="numero numero-botao" variants={subir} onClick={aoClicar} whileTap={{ scale: 0.98 }}>
      {miolo}
    </m.button>
  ) : (
    <m.div className="numero" variants={subir}>
      {miolo}
    </m.div>
  );
}

export function Hero({ painel, resumo, mediana, agora, filtro, aoMudar }: Props) {
  const { perfil, totais, janela_dias: janela } = painel;
  const hoje = diaBR(agora);
  const so = (parcial: Partial<Filtro>) => aoMudar({ ...FILTRO_INICIAL, ordem: filtro.ordem, ...parcial }, true);
  const ate7 = () => {
    const { de, ate } = atePrazoEmDias(hoje, 7);
    so({ prazoDe: de, prazoAte: ate });
  };
  const contado = useContagem(resumo.combinam);

  return (
    <m.section className="hero" id="resumo" aria-labelledby="hero-titulo" variants={emSequencia} initial="oculto" animate="visivel">
      <div className="hero-texto">
        <m.p className="eyebrow" variants={subir}>
          <span className="selo-demo">Perfil de demonstração</span>
          <span>{listaEm(perfil.ufs)}</span>
        </m.p>
        <m.h1 id="hero-titulo" variants={subir}>
          <span className="hero-numero">
            <span aria-hidden="true">{formataInteiro(contado)}</span>
            <span className="so-leitor">{formataInteiro(resumo.combinam)}</span>
          </span>
          <span className="hero-frase">
            {plural(resumo.combinam, "edital aberto combina", "editais abertos combinam")} com o perfil
          </span>
        </m.h1>
        <m.p className="hero-sub" variants={subir}>
          Todo dia um robô lê o PNCP, o portal nacional de contratações públicas, e separa as obras e os serviços
          de engenharia que combinam com um perfil de empresa.
        </m.p>
        <m.div className="hero-acoes" variants={subir}>
          <a className="botao-primario" href="#editais">
            Ver os editais
          </a>
          <button type="button" className="botao" onClick={ate7}>
            Só os que vencem em até 7 dias
          </button>
        </m.div>
        <m.ol className="passos" variants={subir} aria-label="Como usar">
          {PASSOS.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </m.ol>
        <m.p className="escopo" variants={subir}>
          Entre {formataInteiro(totais.abertos)} editais abertos que o robô acompanha ({listaEm(perfil.ufs)};{" "}
          {perfil.modalidades.length} modalidades; prazo em até {janela} dias). Dados de{" "}
          {dataEHora(painel.gerado_em, agora)}.
        </m.p>
      </div>

      <m.div className="numeros" variants={emSequencia}>
        <Numero
          icone="relogio"
          rotulo="Prazo acaba em até 7 dias"
          valor={formataInteiro(resumo.vencemEm7Dias)}
          dica="Toque para ver"
          aoClicar={ate7}
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
      </m.div>
    </m.section>
  );
}
