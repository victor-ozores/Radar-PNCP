import type { ReactNode } from "react";

import { emSequencia, m, subir, useContagem } from "../animacao";
import { formataInteiro, formataValor, plural } from "../lib/formatos";
import { fraseOnde, frasePrazo, fraseValor, listaEm, porcento } from "../lib/historia";
import { FILTRO_INICIAL, atePrazoEmDias, type Filtro, type Resumo } from "../lib/painel";
import { dataEHora, diaBR } from "../lib/tempo";
import type { Edital, Painel } from "../lib/types";
import { Dica } from "./Dica";
import { Icone, type NomeIcone } from "./Icone";

interface Props {
  painel: Painel;
  /** Os editais abertos que combinam: é deles que saem os números e as frases. */
  fortes: Edital[];
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

function Numero({
  icone,
  rotulo,
  dica,
  valor,
  apoio,
  acao,
}: {
  icone: NomeIcone;
  rotulo: string;
  dica: { pergunta: string; texto: ReactNode };
  valor: string;
  apoio: string;
  acao?: { rotulo: string; descricao: string; aoClicar: () => void };
}) {
  return (
    <m.div className="numero" variants={subir}>
      <span className="numero-icone">
        <Icone nome={icone} tam={18} />
      </span>
      <div className="numero-texto">
        <p className="numero-rotulo">
          {rotulo}
          <Dica rotulo={dica.pergunta}>{dica.texto}</Dica>
        </p>
        <p className="numero-valor">{valor}</p>
        <p className="numero-apoio">{apoio}</p>
        {acao && (
          <button type="button" className="link-botao" aria-label={acao.descricao} onClick={acao.aoClicar}>
            {acao.rotulo}
            <Icone nome="seta" tam={14} />
          </button>
        )}
      </div>
    </m.div>
  );
}

export function Hero({ painel, fortes, resumo, mediana, agora, filtro, aoMudar }: Props) {
  const { perfil, totais, janela_dias: janela } = painel;
  const hoje = diaBR(agora);
  const so = (parcial: Partial<Filtro>) => aoMudar({ ...FILTRO_INICIAL, ordem: filtro.ordem, ...parcial }, true);
  const ate7 = () => {
    const { de, ate } = atePrazoEmDias(hoje, 7);
    so({ prazoDe: de, prazoAte: ate });
  };
  const contado = useContagem(resumo.combinam);
  const onde = fraseOnde(fortes);

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
          <Dica rotulo="O que significa combinar com o perfil?">
            “Combina” é uma estimativa feita com palavras-chave do objeto (obra, reforma, pavimentação…), o estado,
            a modalidade e o valor do perfil de demonstração. Não é uma recomendação: confira sempre o edital.
          </Dica>
        </m.p>
        <m.div className="hero-acoes" variants={subir}>
          <a className="botao-primario" href="#editais">
            Ver os editais
          </a>
          <button type="button" className="botao" onClick={ate7}>
            Só os que vencem em até 7 dias
          </button>
        </m.div>
      </div>

      <div className="hero-lateral">
        <m.aside className="historia" variants={subir} aria-labelledby="historia-titulo">
          <h2 id="historia-titulo">O resumo de hoje</h2>
          <ul>
            <li>
              <span className="historia-icone">
                <Icone nome="relogio" tam={16} />
              </span>
              <p>{frasePrazo(fortes, agora)}</p>
            </li>
            {onde && (
              <li>
                <span className="historia-icone">
                  <Icone nome="pino" tam={16} />
                </span>
                <p>{onde}</p>
              </li>
            )}
            <li>
              <span className="historia-icone">
                <Icone nome="moeda" tam={16} />
              </span>
              <p>{fraseValor(fortes)}</p>
            </li>
          </ul>
        </m.aside>

        <m.div className="como-usar" variants={subir}>
          <h2>Como usar</h2>
          <ol className="passos">
            {PASSOS.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ol>
        </m.div>
      </div>

      <m.div className="numeros" variants={emSequencia}>
        <Numero
          icone="relogio"
          rotulo="Prazo acaba em até 7 dias"
          dica={{
            pergunta: "O que mostra o prazo em até 7 dias?",
            texto:
              "Quantos editais que combinam deixam de aceitar proposta nos próximos 7 dias. É por onde vale começar: quem demora perde a data.",
          }}
          valor={formataInteiro(resumo.vencemEm7Dias)}
          apoio={`${porcento(resumo.vencemEm7Dias, resumo.combinam)}% dos que combinam`}
          acao={{ rotulo: "Ver na lista", descricao: "Ver na lista os que vencem em até 7 dias", aoClicar: ate7 }}
        />
        <Numero
          icone="moeda"
          rotulo="Valor mediano estimado"
          dica={{
            pergunta: "O que é o valor mediano?",
            texto:
              "Se os valores forem postos em ordem, é o do meio: metade dos editais vale mais e metade vale menos. Serve melhor que a média, que os valores muito altos distorcem.",
          }}
          valor={mediana === null ? "—" : formataValor(mediana)}
          apoio="Metade vale mais, metade menos"
        />
        <Numero
          icone="documento"
          rotulo="Em registro de preços"
          dica={{
            pergunta: "O que é registro de preços?",
            texto:
              "O órgão fixa os preços com o vencedor e vai comprando aos poucos, geralmente durante até 1 ano, sem obrigação de comprar tudo. Para a empresa, vira uma ata de preços e não um contrato único.",
          }}
          valor={formataInteiro(resumo.registroDePrecos)}
          apoio={`${porcento(resumo.registroDePrecos, resumo.combinam)}% dos que combinam`}
          acao={{ rotulo: "Ver na lista", descricao: "Ver na lista os de registro de preços", aoClicar: () => so({ registro: true }) }}
        />
      </m.div>

      <m.p className="escopo" variants={subir}>
        Entre {formataInteiro(totais.abertos)} editais abertos que o robô acompanha ({listaEm(perfil.ufs)};{" "}
        {perfil.modalidades.length} modalidades; prazo em até {janela} dias). Dados de{" "}
        {dataEHora(painel.gerado_em, agora)}.
      </m.p>
    </m.section>
  );
}
