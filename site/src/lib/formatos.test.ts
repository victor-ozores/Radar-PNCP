import { describe, expect, it } from "vitest";

import {
  dobra,
  estaGritando,
  formataValor,
  limpaObjeto,
  localidade,
  suavizaCaixa,
  valorConfiavel,
} from "./formatos";

describe("formataValor", () => {
  it.each([
    [null, "valor não informado"],
    [0, "valor não informado"],
    [0.04, "valor não informado"], // preenchimento simbólico visto nos dados reais
    [999, "valor não informado"],
    [1_000, "R$ 1 mil"],
    [27_300, "R$ 27,3 mil"],
    [164_000, "R$ 164 mil"],
    [861_000, "R$ 861 mil"],
    [999_999, "R$ 1 mi"], // não vira "R$ 1.000 mil"
    [1_300_000, "R$ 1,3 mi"],
    [4_000_000, "R$ 4 mi"],
    [216_606_351.29, "R$ 216,6 mi"],
  ])("%s -> %s", (valor, texto) => {
    expect(formataValor(valor)).toBe(texto);
  });

  it("valorConfiavel descarta o que não é número útil", () => {
    expect(valorConfiavel(NaN)).toBeNull();
    expect(valorConfiavel(-5)).toBeNull();
    expect(valorConfiavel(1_500)).toBe(1_500);
  });
});

describe("limpaObjeto", () => {
  it("tira a etiqueta do sistema que publicou", () => {
    expect(limpaObjeto("[Portal de Compras Públicas] - CONTRATAÇÃO DE EMPRESA")).toBe("CONTRATAÇÃO DE EMPRESA");
    expect(limpaObjeto("[LICITANET] Reforma da escola")).toBe("Reforma da escola");
  });

  it("não mexe em colchetes que fazem parte do texto", () => {
    expect(limpaObjeto("Reforma da escola [lote 2]")).toBe("Reforma da escola [lote 2]");
  });

  it("nunca devolve texto vazio", () => {
    expect(limpaObjeto("[Publicenter]")).toBe("[Publicenter]");
    expect(limpaObjeto("  Obra  ")).toBe("Obra");
  });
});

describe("suavizaCaixa", () => {
  it("transforma CAIXA ALTA em texto normal, mantendo siglas e números", () => {
    expect(
      suavizaCaixa("CONTRATAÇÃO DE EMPRESA ESPECIALIZADA PARA EXECUÇÃO DA OBRA DA UBS DO BAIRRO RURAL"),
    ).toBe("Contratação de Empresa Especializada para Execução da Obra da UBS do Bairro Rural");
    expect(suavizaCaixa("OBRAS NA RODOVIA PRC-467 E PRS-495 NO LOTE II")).toBe(
      "Obras na Rodovia PRC-467 e PRS-495 no Lote II",
    );
  });

  it("não mexe em texto que já está em caixa normal ou é curto", () => {
    expect(suavizaCaixa("Contratação de empresa para a reforma da escola")).toBe(
      "Contratação de empresa para a reforma da escola",
    );
    expect(suavizaCaixa("Reforma da UBS e do CRAS")).toBe("Reforma da UBS e do CRAS");
    expect(suavizaCaixa("OBRA CIVIL")).toBe("OBRA CIVIL"); // curto demais para ter certeza
  });

  it("mantém o pronome colado em minúsculas e o à com crase", () => {
    expect(suavizaCaixa("REFERE-SE A CONTRATAÇÃO DE EMPRESA LOCALIZADA À RUA DAS FLORES")).toBe(
      "Refere-se a Contratação de Empresa Localizada à Rua das Flores",
    );
  });

  it("devolve a letra solta e o artigo certos", () => {
    expect(suavizaCaixa("EXECUÇÃO DA OBRA NO BLOCO B A PARTIR DO PROJETO")).toBe(
      "Execução da Obra no Bloco B a Partir do Projeto",
    );
  });

  it("restaura acentos só nas palavras conhecidas de nomes de órgãos", () => {
    expect(suavizaCaixa("MUNICIPIO DE BONFINOPOLIS DE MINAS", true)).toBe("Município de Bonfinopolis de Minas");
    expect(suavizaCaixa("TRIBUNAL DE JUSTICA DO ESTADO DE MINAS GERAIS", true)).toBe(
      "Tribunal de Justiça do Estado de Minas Gerais",
    );
    expect(suavizaCaixa("MUNICIPIO DE BONFINOPOLIS DE MINAS")).toBe("Municipio de Bonfinopolis de Minas");
  });

  it("estaGritando", () => {
    expect(estaGritando("CONTRATAÇÃO DE EMPRESA")).toBe(true);
    expect(estaGritando("Contratação de Empresa Especializada")).toBe(false);
    expect(estaGritando("OBRA")).toBe(false);
  });
});

describe("textos", () => {
  it("dobra tira acento e caixa", () => {
    expect(dobra("  CONSTRUÇÃO   Água ")).toBe("construcao agua");
  });

  it("localidade", () => {
    expect(localidade("Campinas", "SP")).toBe("Campinas / SP");
    expect(localidade(null, "SP")).toBe("SP");
    expect(localidade(null, null)).toBe("");
  });
});
