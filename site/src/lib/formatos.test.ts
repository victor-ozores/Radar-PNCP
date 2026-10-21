import { describe, expect, it } from "vitest";

import { dobra, formataValor, limpaObjeto, localidade, valorConfiavel } from "./formatos";

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
