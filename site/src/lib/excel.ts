/**
 * Monta o arquivo .xlsx já formatado. A biblioteca (`write-excel-file`, 20 KB compactados) só é baixada quando a
 * pessoa pede o arquivo: quem só olha a lista não paga por ela.
 *
 * Aba "Editais": cabeçalho fixo, filtros nas colunas, colunas largas o bastante, prazo e valor como data e
 * número de verdade (dá para ordenar e somar), o link do PNCP clicável, cor nos prazos que acabam logo e três
 * colunas verdes em branco (Situação com lista de opções, Responsável e Observações) para a equipe preencher.
 * Aba "Sobre este arquivo": de onde vêm os dados, o que foi exportado e com quais filtros.
 */
import type { Cell, Feature } from "write-excel-file/universal";

import { AVISO_DEMONSTRACAO, linhaDoEdital, textoDoEscopo, type Escopo, type LinhaExcel } from "./exportar";
import { dataEHoraCompleta } from "./tempo";
import type { Edital } from "./types";

export interface ContextoDoArquivo {
  agora: Date;
  /** Quando o robô gerou os dados do painel (ISO). */
  geradoEm: string;
  perfil: string;
  escopo: Escopo;
  /** O texto de cada filtro ligado, como nas etiquetas da lista. Vazio = sem filtro. */
  filtros: string[];
  painelUrl: string;
  repoUrl: string;
  pncpUrl: string;
}

export const ABA_EDITAIS = "Editais";
export const ABA_SOBRE = "Sobre este arquivo";

/** As opções da lista suspensa da coluna "Situação". */
export const SITUACOES = ["Analisar", "Vou disputar", "Descartado", "Proposta enviada", "Ganhou", "Perdeu"] as const;

const AZUL = "#1f3a5f";
const VERDE = "#1e6b46";
const VERDE_CLARO = "#eef7f1";
const BORDA = "#d9dee7";

interface Coluna {
  titulo: string;
  largura: number;
  /** As três últimas ficam em branco para a equipe preencher. */
  paraPreencher?: boolean;
  celula: (l: LinhaExcel) => Cell;
}

const texto = (valor: string, extra: object = {}): Cell => ({ value: valor === "" ? null : valor, ...extra }) as Cell;

const COLUNAS: Coluna[] = [
  {
    titulo: "Prazo das propostas",
    largura: 19,
    celula: (l) => ({ value: l.prazo, type: Date, format: "dd/mm/yyyy hh:mm" }),
  },
  { titulo: "Faltam (dias)", largura: 10, celula: (l) => ({ value: l.faltam, type: Number }) },
  { titulo: "Combina", largura: 16, celula: (l) => texto(l.combina) },
  { titulo: "Objeto", largura: 62, celula: (l) => texto(l.objeto, { wrap: true }) },
  { titulo: "Órgão", largura: 34, celula: (l) => texto(l.orgao, { wrap: true }) },
  { titulo: "UF", largura: 6, celula: (l) => texto(l.uf) },
  { titulo: "Município", largura: 20, celula: (l) => texto(l.municipio, { wrap: true }) },
  { titulo: "Modalidade", largura: 24, celula: (l) => texto(l.modalidade, { wrap: true }) },
  { titulo: "Nº do edital", largura: 14, celula: (l) => texto(l.numero) },
  {
    titulo: "Valor estimado (R$)",
    largura: 19,
    celula: (l) => (l.valor === null ? null : { value: l.valor, type: Number, format: '"R$" #,##0.00' }) as Cell,
  },
  { titulo: "Registro de preços", largura: 12, celula: (l) => texto(l.registroDePrecos) },
  { titulo: "Palavras do perfil", largura: 24, celula: (l) => texto(l.palavras, { wrap: true }) },
  { titulo: "Também publicado como", largura: 22, celula: (l) => texto(l.tambemPublicadoComo, { wrap: true }) },
  {
    titulo: "Link no PNCP",
    largura: 15,
    celula: (l) =>
      (l.link === ""
        ? null
        : {
            // fórmula sem o "=" na frente: é como o arquivo guarda; o Excel mostra o texto e abre o endereço ao clicar
            value: `HYPERLINK("${l.link.replaceAll('"', "%22")}","Abrir no PNCP")`,
            type: "Formula",
            textColor: "#0563c1",
            textDecoration: { underline: true },
          }) as Cell,
  },
  { titulo: "Situação", largura: 18, paraPreencher: true, celula: () => null },
  { titulo: "Responsável", largura: 18, paraPreencher: true, celula: () => null },
  { titulo: "Observações", largura: 36, paraPreencher: true, celula: () => null },
];

/** Letra da coluna do Excel: 0 -> A, 16 -> Q. */
const letra = (i: number) => String.fromCharCode(65 + i);

const COLUNA_FALTAM = 2; // número da coluna (1 = A): "Faltam (dias)"
const COLUNA_SITUACAO = COLUNAS.findIndex((c) => c.titulo === "Situação");

function cabecalho(c: Coluna): Cell {
  return {
    value: c.titulo,
    fontWeight: "bold",
    textColor: "#ffffff",
    backgroundColor: c.paraPreencher ? VERDE : AZUL,
    wrap: true,
    alignVertical: "center",
    borderStyle: "thin",
    borderColor: BORDA,
  } as Cell;
}

/** O estilo comum a todo o corpo da planilha: alinhado ao topo e com linhas finas, para ler texto comprido. */
function comEstilo(celula: Cell | null, c: Coluna): Cell {
  const base = {
    alignVertical: "top",
    borderStyle: "thin",
    borderColor: BORDA,
    ...(c.paraPreencher ? { backgroundColor: VERDE_CLARO } : {}),
  };
  if (celula === null) return { value: "", type: String, ...base } as Cell;
  return { ...base, ...(celula as object) } as Cell;
}

// ---------------------------------------------------------------------------- extensões do arquivo

/**
 * A ordem em que o formato (ECMA-376, `CT_Worksheet`) exige os elementos de uma aba. Fora dela o Excel acusa
 * "arquivo corrompido", então tudo que este arquivo insere na mão passa por `insereNoLugar`.
 */
export const ORDEM_DA_ABA = [
  "sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols", "sheetData", "sheetCalcPr", "sheetProtection",
  "protectedRanges", "scenarios", "autoFilter", "sortState", "dataConsolidate", "customSheetViews", "mergeCells",
  "phoneticPr", "conditionalFormatting", "dataValidations", "hyperlinks", "printOptions", "pageMargins", "pageSetup",
  "headerFooter", "rowBreaks", "colBreaks", "customProperties", "cellWatches", "ignoredErrors", "smartTags", "drawing",
  "legacyDrawing", "legacyDrawingHF", "drawingHF", "picture", "oleObjects", "controls", "webPublishItems",
  "tableParts", "extLst",
] as const;

/**
 * Põe `markup` (o elemento `nome`) logo depois do último elemento que deve vir antes dele. Conta todos os
 * irmãos repetidos (a biblioteca escreve um `<conditionalFormatting>` por regra); a função de inserção dela
 * para no primeiro e deixaria a lista de opções no meio das regras de cor.
 */
export function insereNoLugar(xml: string, nome: (typeof ORDEM_DA_ABA)[number], markup: string): string {
  let fim = -1;
  for (const anterior of ORDEM_DA_ABA.slice(0, ORDEM_DA_ABA.indexOf(nome))) {
    const elemento = new RegExp(String.raw`<${anterior}\b[^>]*?(?:/>|>[\s\S]*?</${anterior}>)`, "g");
    for (const achado of xml.matchAll(elemento)) fim = Math.max(fim, achado.index + achado[0].length);
  }
  if (fim < 0) throw new Error(`não achei onde inserir <${nome}> na aba`);
  return xml.slice(0, fim) + markup + xml.slice(fim);
}

/**
 * A biblioteca não sabe desenhar filtros nas colunas nem lista suspensa; ela deixa o programa mexer no XML da
 * aba. Estas duas extensões rodam depois das regras de cor dela e só mexem na aba "Editais".
 */
function extensoes(linhas: number): Feature<Blob>[] {
  const ultima = linhas + 1; // a linha 1 é o cabeçalho
  const coluna = letra(COLUNA_SITUACAO);

  const filtroNasColunas: Feature<Blob> = {
    files: {
      transform: {
        "xl/worksheets/sheet{id}.xml": {
          transform: (xml, opcoes) =>
            opcoes.sheet === ABA_EDITAIS
              ? insereNoLugar(xml, "autoFilter", `<autoFilter ref="A1:${letra(COLUNAS.length - 1)}${ultima}"/>`)
              : xml,
        },
      },
    },
  };

  const listaDeSituacao: Feature<Blob> = {
    files: {
      transform: {
        "xl/worksheets/sheet{id}.xml": {
          transform: (xml, opcoes) =>
            opcoes.sheet === ABA_EDITAIS
              ? insereNoLugar(
                  xml,
                  "dataValidations",
                  `<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" ` +
                    `errorTitle="Situação" error="Escolha uma das opções da lista, ou deixe em branco." ` +
                    `sqref="${coluna}2:${coluna}${ultima}"><formula1>"${SITUACOES.join(",")}"</formula1>` +
                    `</dataValidation></dataValidations>`,
                )
              : xml,
        },
      },
    },
  };

  return [filtroNasColunas, listaDeSituacao];
}

// ---------------------------------------------------------------------------- aba "Sobre este arquivo"

function abaSobre(quantos: number, ctx: ContextoDoArquivo): Cell[][] {
  const rotulo = (v: string): Cell => ({ value: v, fontWeight: "bold", alignVertical: "top" }) as Cell;
  const corpo = (v: string): Cell => ({ value: v, wrap: true, alignVertical: "top" }) as Cell;
  const filtros = ctx.filtros.length > 0 ? ctx.filtros.join("; ") : "Nenhum";
  return [
    [{ value: "Radar de Licitações PNCP", fontWeight: "bold", fontSize: 16 } as Cell, null],
    [{ value: "Arquivo exportado do painel público", textColor: "#555555" } as Cell, null],
    [null, null],
    [rotulo("Gerado em"), corpo(`${dataEHoraCompleta(ctx.agora)} (horário de Brasília)`)],
    [rotulo("Dados do painel de"), corpo(dataEHoraCompleta(ctx.geradoEm))],
    [rotulo("O que foi exportado"), corpo(textoDoEscopo(ctx.escopo, quantos))],
    [rotulo("Filtros ligados"), corpo(filtros)],
    [rotulo("Perfil usado"), corpo(`Perfil de demonstração: ${ctx.perfil}`)],
    [rotulo("Colunas verdes"), corpo("Situação, Responsável e Observações ficam em branco para a sua equipe preencher. A coluna Situação tem uma lista de opções.")],
    [rotulo("Atenção"), corpo("Confira sempre o edital no PNCP: o prazo, a situação e o texto podem ter mudado depois que o robô leu.")],
    [rotulo("É uma demonstração, não um limite"), corpo(AVISO_DEMONSTRACAO)],
    [null, null],
    [rotulo("Painel"), corpo(ctx.painelUrl)],
    [rotulo("Fonte dos dados"), corpo(`PNCP, Portal Nacional de Contratações Públicas: ${ctx.pncpUrl}`)],
    [rotulo("Código"), corpo(ctx.repoUrl)],
  ];
}

// ---------------------------------------------------------------------------- o arquivo

export async function geraPlanilha(editais: Edital[], ctx: ContextoDoArquivo): Promise<Blob> {
  const linhas = editais.map((e) => linhaDoEdital(e, ctx.agora));
  const { default: escreveXlsx } = await import("write-excel-file/universal");

  const dados: Cell[][] = [
    COLUNAS.map(cabecalho),
    ...linhas.map((l) => COLUNAS.map((c) => comEstilo(c.celula(l), c))),
  ];
  const ultima = linhas.length + 1;
  const faltam = { from: { row: 2, column: COLUNA_FALTAM }, to: { row: Math.max(ultima, 2), column: COLUNA_FALTAM } };

  return escreveXlsx(
    [
      {
        data: dados,
        sheet: ABA_EDITAIS,
        columns: COLUNAS.map((c) => ({ width: c.largura })),
        stickyRowsCount: 1,
        // as mesmas cores da lista: vermelho até 2 dias, amarelo até 7 (a primeira regra que vale ganha)
        conditionalFormatting: [
          { cellRange: faltam, condition: { operator: "<=", value: 2 }, style: { backgroundColor: "#f8d7da", textColor: "#842029", fontWeight: "bold" } },
          { cellRange: faltam, condition: { operator: "<=", value: 7 }, style: { backgroundColor: "#fff3cd", textColor: "#664d03" } },
        ],
      },
      {
        data: abaSobre(linhas.length, ctx),
        sheet: ABA_SOBRE,
        columns: [{ width: 34 }, { width: 100 }],
      },
    ],
    { fontFamily: "Calibri", fontSize: 11, features: extensoes(linhas.length) },
  ).toBlob();
}
