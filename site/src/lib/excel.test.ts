// @vitest-environment jsdom
import { strFromU8, unzipSync } from "fflate";
import { describe, expect, it } from "vitest";

import {
  ABA_EDITAIS,
  ABA_SOBRE,
  ORDEM_DA_ABA,
  SITUACOES,
  TEXTO_DA_NOTA,
  geraPlanilha,
  insereNoLugar,
  textoDosFiltros,
  type ContextoDoArquivo,
} from "./excel";
import { AGORA, edital, emDias } from "../testes/modelos";

const contexto: ContextoDoArquivo = {
  agora: AGORA,
  geradoEm: "2026-10-21T12:40:00-03:00",
  perfil: "Construtora de médio porte",
  escopo: "filtrados",
  filtros: ["Estado: SP", "Prazo até 30/10"],
  painelUrl: "https://exemplo.github.io/Radar-PNCP/",
  repoUrl: "https://github.com/exemplo/Radar-PNCP",
  pncpUrl: "https://pncp.gov.br/app/editais",
};

const editais = [
  edital({
    objeto: "REFORMA DA ESCOLA MUNICIPAL",
    prazo: "2026-10-26T07:59:00-03:00",
    valor: 1_234_567.5,
    link: "https://pncp.gov.br/app/editais/11111111000111/2026/7",
    numero: "12/2026",
    nota: 85,
  }),
  edital({ objeto: "Pavimentação de ruas", prazo: emDias(20), valor: 0.04, link: null }),
  edital({ objeto: 'Obra "com aspas" & símbolos <1>', prazo: emDias(3) }),
];

async function abre(escolhidos = editais, ctx = contexto) {
  const blob = await geraPlanilha(escolhidos, ctx);
  const arquivos = unzipSync(new Uint8Array(await blob.arrayBuffer()));
  const texto = (nome: string) => strFromU8(arquivos[nome]!);
  const comuns = [...texto("xl/sharedStrings.xml").matchAll(/<si>(?:<t[^>]*>)?([\s\S]*?)(?:<\/t>)?<\/si>/g)].map((m) =>
    m[1]!.replaceAll("&amp;", "&").replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&quot;", '"'),
  );
  return { blob, arquivos, texto, comuns, aba1: texto("xl/worksheets/sheet1.xml"), aba2: texto("xl/worksheets/sheet2.xml") };
}

describe("textoDosFiltros", () => {
  it("diz que os filtros valem para o arquivo só quando a escolha foi 'todos da lista'", () => {
    expect(textoDosFiltros("filtrados", ["Estado: SP", "Prazo até 30/10"])).toBe(
      "Estado: SP; Prazo até 30/10. Estes filtros valem para o arquivo: só entraram os editais que passam por eles.",
    );
  });

  it("nas outras escolhas, diz que os filtros estavam na tela mas não limitam o arquivo", () => {
    expect(textoDosFiltros("selecionados", ["Prazo até 26/10"])).toBe(
      "Prazo até 26/10. Estavam ligados na tela, mas não limitam este arquivo: ele leva só os editais marcados.",
    );
    expect(textoDosFiltros("todos", ["Estado: MG"])).toBe(
      "Estado: MG. Estavam ligados na tela, mas não limitam este arquivo: ele leva todos os editais do painel.",
    );
  });

  it("sem filtro, diz isso", () => {
    expect(textoDosFiltros("filtrados", [])).toBe("Nenhum filtro estava ligado na tela.");
    expect(textoDosFiltros("todos", [])).toBe("Nenhum filtro estava ligado na tela.");
  });
});

describe("insereNoLugar", () => {
  const base = '<worksheet><sheetData/><conditionalFormatting sqref="A1"/><conditionalFormatting sqref="B1"/><pageMargins/></worksheet>';

  it("põe depois do último irmão repetido que deve vir antes, e antes dos que vêm depois", () => {
    expect(insereNoLugar(base, "dataValidations", "<dataValidations/>")).toBe(
      '<worksheet><sheetData/><conditionalFormatting sqref="A1"/><conditionalFormatting sqref="B1"/><dataValidations/><pageMargins/></worksheet>',
    );
    expect(insereNoLugar(base, "autoFilter", "<autoFilter/>")).toBe(
      '<worksheet><sheetData/><autoFilter/><conditionalFormatting sqref="A1"/><conditionalFormatting sqref="B1"/><pageMargins/></worksheet>',
    );
  });

  it("acha o fim de elementos com conteúdo e o de elementos que se fecham sozinhos", () => {
    const xml = "<worksheet><sheetData><row r=\"1\"><c r=\"A1\"/></row></sheetData></worksheet>";
    expect(insereNoLugar(xml, "autoFilter", "<autoFilter/>")).toBe(
      '<worksheet><sheetData><row r="1"><c r="A1"/></row></sheetData><autoFilter/></worksheet>',
    );
  });

  it("avisa se a aba não tem onde receber o elemento", () => {
    expect(() => insereNoLugar("<worksheet/>", "autoFilter", "<autoFilter/>")).toThrow(/não achei onde inserir/);
  });
});

describe("geraPlanilha", () => {
  it("cria um .xlsx de verdade com as duas abas, na ordem", async () => {
    const { blob, texto } = await abre();
    expect(blob.type).toMatch(/spreadsheetml/);
    expect(blob.size).toBeGreaterThan(2000);
    const livro = texto("xl/workbook.xml");
    expect(livro.indexOf(`name="${ABA_EDITAIS}"`)).toBeGreaterThan(-1);
    expect(livro.indexOf(`name="${ABA_SOBRE}"`)).toBeGreaterThan(livro.indexOf(`name="${ABA_EDITAIS}"`));
  });

  it("todo XML do arquivo é bem formado", async () => {
    const { arquivos } = await abre();
    for (const [nome, bytes] of Object.entries(arquivos)) {
      if (!/\.(xml|rels)$/.test(nome)) continue;
      const doc = new DOMParser().parseFromString(strFromU8(bytes), "application/xml");
      expect(doc.getElementsByTagName("parsererror").length, nome).toBe(0);
    }
  });

  it("escreve o cabeçalho, as três colunas para preencher e o texto da tela (caixa normal)", async () => {
    const { comuns } = await abre();
    for (const titulo of ["Prazo das propostas", "Faltam (dias)", "Nota (0 a 100)", "Objeto", "Valor estimado (R$)", "Link no PNCP", "Situação", "Responsável", "Observações"]) {
      expect(comuns, titulo).toContain(titulo);
    }
    expect(comuns).toContain("Reforma da Escola Municipal");
    expect(comuns).toContain('Obra "com aspas" & símbolos <1>'); // caracteres especiais não quebram o arquivo
  });

  it("guarda prazo e valor como data e número de verdade, no horário de Brasília", async () => {
    const { aba1 } = await abre();
    const serie = Date.UTC(2026, 9, 26, 7, 59) / 86_400_000 + 25_569; // dia 1 do Excel = 1900-01-01
    const prazo = Number(/<c r="A2"[^>]*><v>([^<]+)<\/v>/.exec(aba1)?.[1]);
    expect(prazo).toBeCloseTo(serie, 6);
    expect(Number(/<c r="K2"[^>]*><v>([^<]+)<\/v>/.exec(aba1)?.[1])).toBe(1_234_567.5);
    expect(/<c r="K3"[^>]*><v>/.test(aba1)).toBe(false); // valor simbólico (R$ 0,04): em branco
  });

  it("o link do PNCP é clicável (fórmula HYPERLINK, sem o '=' na frente) e some quando não há link", async () => {
    const { aba1 } = await abre();
    expect(aba1).toContain('<f>HYPERLINK("https://pncp.gov.br/app/editais/11111111000111/2026/7","Abrir no PNCP")</f>');
    expect(aba1).not.toContain("<f>=");
    expect(/<c r="O3"[^>]*><f>/.test(aba1)).toBe(false);
  });

  it("põe filtro nas colunas e a lista de opções em 'Situação', na ordem que o formato exige", async () => {
    const { aba1 } = await abre();
    expect(aba1).toContain('<autoFilter ref="A1:R4"/>');
    expect(aba1).toContain('sqref="P2:P4"');
    expect(aba1).toContain(`<formula1>"${SITUACOES.join(",")}"</formula1>`);
    expect(aba1.indexOf("</sheetData>")).toBeLessThan(aba1.indexOf("<autoFilter"));
  });

  it("todos os elementos de cada aba ficam na ordem que o formato exige (senão o Excel acusa arquivo corrompido)", async () => {
    const { aba1, aba2 } = await abre();
    for (const xml of [aba1, aba2]) {
      const doc = new DOMParser().parseFromString(xml, "application/xml");
      const nomes = [...doc.documentElement.children].map((e) => e.localName);
      const posicoes = nomes.map((n) => (ORDEM_DA_ABA as readonly string[]).indexOf(n));
      expect(posicoes.every((p) => p >= 0), `elemento desconhecido em ${nomes.join(",")}`).toBe(true);
      expect(posicoes, nomes.join(",")).toEqual([...posicoes].sort((x, y) => x - y));
    }
    // e as duas regras de cor ficam juntas, antes da lista de opções
    const ordem = [...new DOMParser().parseFromString(aba1, "application/xml").documentElement.children].map((e) => e.localName);
    expect(ordem.filter((n) => n === "conditionalFormatting")).toHaveLength(2);
    expect(ordem.indexOf("dataValidations")).toBeGreaterThan(ordem.lastIndexOf("conditionalFormatting"));
  });

  it("fixa o cabeçalho, ajusta a largura das colunas e colore os prazos que acabam logo", async () => {
    const { aba1 } = await abre();
    expect(aba1).toMatch(/<pane[^>]*ySplit="1"[^>]*state="frozen"/);
    expect(aba1).toContain('<col min="5" max="5" width="62" customWidth="1"/>'); // Objeto
    expect((aba1.match(/<conditionalFormatting sqref="B2:B4"/g) ?? []).length).toBe(2); // vermelho (até 2) e amarelo (até 7)
  });

  it("a aba 'Sobre' diz o que foi exportado, com quais filtros, e que é uma demonstração sem limite", async () => {
    const { comuns } = await abre();
    const junto = comuns.join(" | ");
    expect(junto).toContain("Todos os 3 da lista, com os filtros que estavam ligados");
    expect(junto).toContain("Estado: SP; Prazo até 30/10. Estes filtros valem para o arquivo");
    expect(junto).toContain("Perfil de demonstração: Construtora de médio porte");
    expect(junto).toContain("21/10/2026 15:00 (horário de Brasília)");
    expect(junto).toContain("É uma demonstração, não um limite");
    expect(junto).toContain("esfera do órgão, o modo de disputa e o número do processo");
    expect(junto).toContain("Confira sempre o edital no PNCP");
  });

  it("sem filtro ligado a aba 'Sobre' diz que nenhum estava ligado", async () => {
    const { comuns } = await abre(editais, { ...contexto, filtros: [], escopo: "todos" });
    expect(comuns).toContain("Nenhum filtro estava ligado na tela.");
    expect(comuns.join(" ")).toMatch(/Todos os 3 editais abertos do painel, sem nenhum filtro/);
  });

  it("leva a nota de 0 a 100 como número, para ordenar", async () => {
    const { aba1 } = await abre();
    expect(Number(/<c r="D2"[^>]*><v>([^<]+)<\/v>/.exec(aba1)?.[1])).toBe(85);
  });

  it("leva o texto inteiro do objeto e do órgão quando o painel mandou, e o resumo quando não mandou", async () => {
    const inteiro = "Contratação de empresa especializada para a execução de obras de reforma predial da escola municipal, com fornecimento de materiais e mão de obra, conforme projeto básico";
    const lista = [
      edital({ objeto: "Contratação de empresa especializada para a execução de obras de reforma predial…", objeto_completo: inteiro, orgao: "SECRETARIA DE OBRAS…", orgao_completo: "SECRETARIA DE OBRAS E INFRAESTRUTURA", municipio: null }),
      edital({ objeto: "Resumo sem texto inteiro…" }),
    ];
    const { comuns } = await abre(lista);
    expect(comuns).toContain(inteiro);
    expect(comuns.some((c) => c.endsWith("predial…"))).toBe(false); // o resumo cortado não vai quando há o inteiro
    expect(comuns).toContain("Secretaria de Obras e Infraestrutura");
    expect(comuns).toContain("Resumo sem texto inteiro…"); // sem o inteiro, vale o resumo
  });

  it("guarda o texto do link junto da fórmula, para aparecer mesmo no Modo de Exibição Protegido", async () => {
    const { aba1 } = await abre();
    const celulas = aba1.match(/<c r="O\d+"[^>]*><f>HYPERLINK[^<]*<\/f>(<v>[^<]*<\/v>)?<\/c>/g) ?? [];
    expect(celulas.length).toBeGreaterThan(0);
    for (const c of celulas) {
      expect(c, c).toContain(' t="str"');
      expect(c, c).toContain("<v>Abrir no PNCP</v>");
    }
    expect(aba1).not.toMatch(/<f>HYPERLINK[^<]*<\/f><\/c>/); // nenhuma fórmula sem valor guardado
  });

  it("a aba 'Sobre' explica a nota", async () => {
    const { comuns } = await abre();
    expect(comuns).toContain("Nota (0 a 100)");
    expect(comuns).toContain(TEXTO_DA_NOTA);
    expect(TEXTO_DA_NOTA).toMatch(/80 ou mais: Combina muito.*60 a 79: Combina.*40 a 59: Combina em parte/);
  });

  it("aguenta o painel inteiro (1.300 editais) em poucos segundos", async () => {
    const muitos = Array.from({ length: 1300 }, (_, i) => edital({ objeto: `Obra número ${i}`, prazo: emDias(1 + (i % 29)) }));
    const inicio = performance.now();
    const { aba1 } = await abre(muitos);
    expect(performance.now() - inicio).toBeLessThan(8000);
    expect(aba1).toContain('<autoFilter ref="A1:R1301"/>');
  });
});
