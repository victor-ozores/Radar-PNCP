import { describe, expect, it } from "vitest";

import {
  dicaCidade,
  dicaPrazo,
  dicaTermo,
  dicaUf,
  dicaValor,
  fraseOnde,
  frasePrazo,
  fraseValor,
  listaEm,
} from "./historia";
import { faixasPrazo, porUf, resumoValores, termosMaisCitados, topMunicipios } from "./painel";
import { AGORA, edital, emDias } from "../testes/modelos";

describe("listaEm", () => {
  it("junta com vírgula e 'e'", () => {
    expect(listaEm([])).toBe("");
    expect(listaEm(["SP"])).toBe("SP");
    expect(listaEm(["SP", "MG"])).toBe("SP e MG");
    expect(listaEm(["SP", "MG", "PR"])).toBe("SP, MG e PR");
  });
});

describe("frasePrazo", () => {
  it("conta os que acabam logo e diz quando termina o primeiro", () => {
    const fortes = [
      edital({ prazo: emDias(1, "09:00") }),
      edital({ prazo: emDias(3, "10:00") }),
      edital({ prazo: emDias(20) }),
    ];
    expect(frasePrazo(fortes, AGORA)).toBe(
      "2 prazos acabam em até 3 dias. O mais próximo termina amanhã às 09h00.",
    );
  });

  it("usa o singular quando é só um", () => {
    const fortes = [edital({ prazo: emDias(2, "08:30") }), edital({ prazo: emDias(20) })];
    expect(frasePrazo(fortes, AGORA)).toMatch(/^1 prazo acaba em até 3 dias\./);
  });

  it("diz que nenhum acaba logo e quando é o primeiro", () => {
    const fortes = [edital({ prazo: emDias(9, "10:00") }), edital({ prazo: emDias(20) })];
    expect(frasePrazo(fortes, AGORA)).toMatch(/^Nenhum prazo acaba em até 3 dias\. O mais próximo termina .+ 10h00\.$/);
  });

  it("não inventa prazo quando não há edital", () => {
    expect(frasePrazo([], AGORA)).toBe("Nenhum edital aberto combina com o perfil agora.");
  });
});

describe("fraseOnde", () => {
  it("diz qual estado lidera e quais vêm depois", () => {
    const fortes = [
      ...Array.from({ length: 6 }, () => edital({ uf: "SP" })),
      ...Array.from({ length: 3 }, () => edital({ uf: "MG" })),
      edital({ uf: "PR" }),
    ];
    expect(fraseOnde(fortes)).toBe("SP concentra 60% dos editais (6). Depois vêm MG e PR.");
  });

  it("com um estado só, diz que todos estão nele", () => {
    expect(fraseOnde([edital({ uf: "SP" }), edital({ uf: "SP" })])).toBe("Todos estão em SP.");
  });

  it("sem estado nenhum, não escreve nada", () => {
    expect(fraseOnde([])).toBeNull();
    expect(fraseOnde([edital({ uf: null })])).toBeNull();
  });
});

describe("fraseValor", () => {
  it("conta os acima de 1 milhão e diz o maior", () => {
    const fortes = [edital({ valor: 2_500_000 }), edital({ valor: 1_000_000 }), edital({ valor: 300_000 })];
    expect(fraseValor(fortes)).toBe("2 passam de R$ 1 milhão. O maior vale R$ 2,5 mi.");
  });

  it("sem nenhum acima de 1 milhão, só diz o maior", () => {
    expect(fraseValor([edital({ valor: 300_000 }), edital({ valor: 80_000 })])).toBe("O maior vale R$ 300 mil.");
  });

  it("ignora valor simbólico e diz quando ninguém informa", () => {
    expect(fraseValor([edital({ valor: 0.04 }), edital({ valor: null })])).toBe("Nenhum deles informa o valor estimado.");
  });
});

describe("uma frase por gráfico", () => {
  it("prazo: a faixa mais cheia e quantos acabam em até 3 dias", () => {
    const fortes = [
      edital({ prazo: emDias(1) }),
      edital({ prazo: emDias(20) }),
      edital({ prazo: emDias(21) }),
      edital({ prazo: emDias(22) }),
    ];
    expect(dicaPrazo(faixasPrazo(fortes, AGORA))).toBe(
      "A faixa mais cheia é “16 a 30 dias”, com 3 de 4 (75%). 1 acaba em até 3 dias.",
    );
  });

  it("prazo: avisa quando nenhum acaba logo; sem editais, não escreve", () => {
    expect(dicaPrazo(faixasPrazo([edital({ prazo: emDias(20) })], AGORA))).toMatch(/Nenhum acaba em até 3 dias\.$/);
    expect(dicaPrazo(faixasPrazo([], AGORA))).toBeNull();
  });

  it("valor: a faixa mais comum", () => {
    const fortes = [edital({ valor: 900_000 }), edital({ valor: 800_000 }), edital({ valor: 3_000_000 })];
    expect(dicaValor(resumoValores(fortes))).toBe("A faixa mais comum é “R$ 500 mil a 1 mi”: 2 editais (67%).");
    expect(dicaValor(resumoValores([edital({ valor: null })]))).toBeNull();
  });

  it("estado, cidade e palavra", () => {
    const fortes = [
      edital({ uf: "SP", municipio: "Campinas", termos: ["obra", "reforma"] }),
      edital({ uf: "SP", municipio: "Campinas", termos: ["obra"] }),
      edital({ uf: "MG", municipio: "Uberaba", termos: ["obra"] }),
    ];
    expect(dicaUf(porUf(fortes), fortes.length)).toBe("SP lidera, com 2 editais (67%).");
    expect(dicaUf(porUf([edital({ uf: "SP" })]), 1)).toBe("Todos estão em SP.");
    expect(dicaCidade(topMunicipios(fortes, 8))).toBe("Campinas / SP é a cidade com mais editais: 2.");
    expect(dicaTermo(termosMaisCitados(fortes, 10), fortes.length)).toBe("“obra” aparece em 3 dos 3 editais (100%).");
  });

  it("sem dados, nenhuma frase", () => {
    expect(dicaUf([], 0)).toBeNull();
    expect(dicaCidade([])).toBeNull();
    expect(dicaTermo([], 0)).toBeNull();
  });
});
