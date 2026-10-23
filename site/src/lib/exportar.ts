/**
 * O que vai para o arquivo do Excel, sem depender da biblioteca que escreve o arquivo (`excel.ts`): quais
 * editais entram em cada escolha ("só os marcados", "todos do filtro", "todos do painel") e como cada
 * edital vira uma linha. Texto, valores e datas saem iguais aos da tela.
 */
import { limpaObjeto, nomeDoOrgao, suavizaCaixa, valorConfiavel } from "./formatos";
import { ROTULO_COMBINA, ordenar, type Ordem } from "./painel";
import { comoRelogio, diaBR, diasAte } from "./tempo";
import type { Edital, Repetido } from "./types";

export type Escopo = "selecionados" | "filtrados" | "todos";

/**
 * O que a pessoa precisa saber sobre as colunas e os filtros: é uma demonstração e não um limite. Aparece na tela, no
 * rodapé e no arquivo do Excel. O que diz sobre o robô é verdade (ele já guarda esfera, poder, modo de disputa e
 * processo; só não os manda para o painel).
 */
export const AVISO_DEMONSTRACAO =
  "O painel mostra só uma parte do que existe. O robô já guarda outros dados que o PNCP informa (como a esfera do órgão, o modo de disputa e o número do processo) e pode passar a lê-los ou a mostrá-los. Se uma empresa precisar de mais colunas ou filtros, o dado entra e vira coluna e filtro aqui, sem mudar o resto. O que só está dentro do documento do edital (como as exigências de atestado) exige ler o documento, o que também dá para fazer.";

export interface LinhaExcel {
  /** Fim do prazo, como relógio de Brasília (veja `comoRelogio`). */
  prazo: Date;
  /** Dias de calendário até o prazo, na hora em que o arquivo foi gerado. */
  faltam: number;
  combina: string;
  objeto: string;
  orgao: string;
  uf: string;
  municipio: string;
  modalidade: string;
  numero: string;
  /** `null` quando o órgão não informou um valor que preste (abaixo de R$ 1 mil). */
  valor: number | null;
  registroDePrecos: "Sim" | "Não";
  palavras: string;
  tambemPublicadoComo: string;
  link: string;
}

const rotuloDoRepetido = (r: Repetido) => (r.numero ? `nº ${r.numero}` : "outro registro");

export function linhaDoEdital(e: Edital, agora: Date): LinhaExcel {
  return {
    prazo: comoRelogio(e.prazo),
    faltam: Math.max(0, diasAte(e.prazo, agora)),
    combina: ROTULO_COMBINA[e.combina],
    objeto: suavizaCaixa(limpaObjeto(e.objeto)),
    orgao: nomeDoOrgao(e.orgao, e.municipio),
    uf: e.uf ?? "",
    municipio: e.municipio ?? "",
    modalidade: e.modalidade,
    numero: e.numero ?? "",
    valor: valorConfiavel(e.valor),
    registroDePrecos: e.registro_de_precos ? "Sim" : "Não",
    palavras: e.termos.join(", "),
    tambemPublicadoComo: e.repetidos.map(rotuloDoRepetido).join(", "),
    link: e.link ?? "",
  };
}

interface Fontes {
  /** Ids marcados pela pessoa. */
  marcados: ReadonlySet<string>;
  /** O que a lista mostra com os filtros de agora, já na ordem escolhida. */
  filtrados: Edital[];
  /** Todos os editais abertos do painel, sem filtro. */
  todos: Edital[];
}

/** Os editais de cada escolha, na ordem da lista. */
export function editaisDoEscopo(escopo: Escopo, { marcados, filtrados, todos }: Fontes, ordem: Ordem): Edital[] {
  if (escopo === "filtrados") return filtrados;
  if (escopo === "todos") return ordenar(todos, ordem);
  return ordenar(
    todos.filter((e) => marcados.has(e.id)),
    ordem,
  );
}

const SUFIXO: Record<Escopo, string> = { selecionados: "selecionados", filtrados: "filtro", todos: "todos" };

/** `radar-pncp-2026-10-23-filtro.xlsx`: o dia vai no nome para a pessoa guardar um arquivo por dia. */
export function nomeDoArquivo(escopo: Escopo, agora: Date): string {
  return `radar-pncp-${diaBR(agora)}-${SUFIXO[escopo]}.xlsx`;
}

/** A escolha dita por extenso, para a aba "Sobre este arquivo". */
export function textoDoEscopo(escopo: Escopo, quantos: number): string {
  const n = quantos.toLocaleString("pt-BR");
  if (escopo === "selecionados") return `${n} ${quantos === 1 ? "edital marcado" : "editais marcados"} por quem exportou`;
  if (escopo === "filtrados") return `Todos os ${n} da lista, com os filtros que estavam ligados`;
  return `Todos os ${n} editais abertos do painel, sem nenhum filtro (inclui os que combinam só em parte)`;
}
