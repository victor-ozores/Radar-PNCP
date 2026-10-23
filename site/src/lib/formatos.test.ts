import { describe, expect, it } from "vitest";

import {
  dobra,
  estaGritando,
  formataValor,
  limpaObjeto,
  localidade,
  nomeDoOrgao,
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

  // Os casos abaixo são os mesmos de tests/test_normalize.py: as duas implementações precisam concordar.
  it("suaviza só o trecho em caixa alta de um texto misto", () => {
    expect(
      suavizaCaixa(
        "Contratação de empresa visando o FORNECIMENTO DE MATERIAL E MÃO DE OBRA PARA REFORMA DA PRAÇA " +
          "DR. JOÃO NEVES CAMARGO, destinados à Secretaria Municipal",
      ),
    ).toBe(
      "Contratação de empresa visando o Fornecimento de Material e Mão de Obra para Reforma da Praça " +
        "Dr. João Neves Camargo, destinados à Secretaria Municipal",
    );
    expect(
      suavizaCaixa("CONTRATAÇÃO DE EMPRESA PARA EXECUÇÃO DE MURO NA TRAVESSA TICO-TICO, NO JORDÃO-SP, conforme o Termo"),
    ).toBe("Contratação de Empresa para Execução de Muro na Travessa Tico-Tico, no Jordão-SP, conforme o Termo");
  });

  it("mantém as siglas conhecidas dentro do trecho em caixa alta", () => {
    expect(suavizaCaixa("CONSTRUÇÃO DE CRECHE PADRÃO FNDE NO MUNICÍPIO DE BANDEIRA")).toBe(
      "Construção de Creche Padrão FNDE no Município de Bandeira",
    );
  });

  it("sigla solta no meio de texto normal não vira grito", () => {
    expect(suavizaCaixa("Reforma da UBS e do CRAS com projeto da SABESP")).toBe(
      "Reforma da UBS e do CRAS com projeto da SABESP",
    );
  });

  it("números no meio não quebram o trecho em maiúsculas", () => {
    expect(suavizaCaixa("OBRAS NA RUA 7 DE SETEMBRO NO BAIRRO CENTRO")).toBe("Obras na Rua 7 de Setembro no Bairro Centro");
  });

  it("estaGritando", () => {
    expect(estaGritando("CONTRATAÇÃO DE EMPRESA")).toBe(true);
    expect(estaGritando("Obra na PRAÇA DA MATRIZ CENTRAL de novo")).toBe(true); // trecho longo no meio
    expect(estaGritando("Contratação de Empresa Especializada")).toBe(false);
    expect(estaGritando("OBRA")).toBe(false);
    expect(estaGritando("Reforma da UBS e do CRAS")).toBe(false);
  });
});

// Os mesmos casos estão em tests/test_normalize.py: as duas pontas precisam concordar.
describe("nomeDoOrgao", () => {
  it.each<[string, string | null, string]>([
    ["MUNICIPIO DE IBIRITE", "Ibirité", "Município de Ibirité"],
    ["MUNICIPIO DA ESTANCIA TURISTICA DE OLIMPIA", "Olímpia", "Município da Estância Turística de Olímpia"],
    ["MUNICIPIO DE MARECHAL CANDIDO RONDON", "Marechal Cândido Rondon", "Município de Marechal Cândido Rondon"],
    ["Prefeitura de Capao Bonito", "Capão Bonito", "Prefeitura de Capão Bonito"], // já em caixa normal
    ["CAMARA MUNICIPAL DE RIO BRANCO", "Rio Branco", "Câmara Municipal de Rio Branco"],
    // nome da cidade que começa por palavra pequena: a suavização o deixaria "para de Minas"
    ["MUNICIPIO DE PARA DE MINAS", "Pará de Minas", "Município de Pará de Minas"],
    // só vale a cidade inteira, na ordem: o "para" solto continua preposição
    ["FUNDO PARA O MUNICIPIO DE PARA DE MINAS", "Pará de Minas", "Fundo para o Município de Pará de Minas"],
    // a cidade não aparece no nome do órgão, ou não se sabe qual é: nada além da suavização
    ["TRIBUNAL DE JUSTICA DO ESTADO DE MINAS GERAIS", "Belo Horizonte", "Tribunal de Justiça do Estado de Minas Gerais"],
    ["MUNICIPIO DE IBIRITE", null, "Município de Ibirite"],
    ["MUNICIPIO DE IBIRITE", "", "Município de Ibirite"],
  ])("%s (%s)", (orgao, municipio, esperado) => {
    expect(nomeDoOrgao(orgao, municipio)).toBe(esperado);
  });

  it("repetir não muda nada", () => {
    const pronto = nomeDoOrgao("MUNICIPIO DE IBIRITE", "Ibirité");
    expect(nomeDoOrgao(pronto, "Ibirité")).toBe(pronto);
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
