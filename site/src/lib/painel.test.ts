import { describe, expect, it } from "vitest";

import { AGORA, edital, emDias, painel } from "../testes/modelos";
import {
  FILTRO_INICIAL,
  PainelInvalido,
  SEM_VALOR,
  combinam,
  faixasPrazo,
  filtrar,
  idFaixaValor,
  lePainel,
  mediana,
  ordenar,
  porUf,
  resumir,
  resumoValores,
  termosMaisCitados,
  topMunicipios,
  vigentes,
} from "./painel";

describe("lePainel", () => {
  it("aceita o formato da versão 1", () => {
    const p = lePainel(painel([edital()]));
    expect(p.editais).toHaveLength(1);
  });

  it("recusa arquivo de versão mais nova do que a página sabe ler", () => {
    expect(() => lePainel(painel([], { versao: 2 }))).toThrowError(PainelInvalido);
    try {
      lePainel(painel([], { versao: 2 }));
    } catch (e) {
      expect((e as PainelInvalido).motivo).toBe("versao");
    }
  });

  it.each([null, "texto", 42, {}, { versao: 1 }, { ...painel([]), editais: "nada" }, { ...painel([]), robo: null }])(
    "recusa arquivo malformado: %j",
    (lixo) => {
      expect(() => lePainel(lixo)).toThrowError(PainelInvalido);
    },
  );

  it("descarta só o edital com defeito, sem derrubar o resto", () => {
    const bom = edital();
    const semPrazo = { ...edital(), prazo: "ontem" };
    const combinaInventado = { ...edital(), combina: "talvez" };
    const p = lePainel({ ...painel([bom]), editais: [bom, semPrazo, combinaInventado, null, 7] });
    expect(p.editais.map((e) => e.id)).toEqual([bom.id]);
  });
});

describe("quais editais valem", () => {
  it("vigentes: some o que já passou do prazo, inclusive no mesmo minuto", () => {
    const passou = edital({ prazo: "2026-10-21T14:59:00-03:00" });
    const agoraMesmo = edital({ prazo: "2026-10-21T15:00:00-03:00" });
    const falta = edital({ prazo: "2026-10-21T15:01:00-03:00" });
    expect(vigentes([passou, agoraMesmo, falta], AGORA)).toEqual([falta]);
  });

  it("combinam: tira só o 'em parte'", () => {
    const a = edital({ combina: "muito" });
    const b = edital({ combina: "combina" });
    const c = edital({ combina: "parcial" });
    expect(combinam([a, b, c])).toEqual([a, b]);
  });
});

describe("números do painel", () => {
  it("faixas de prazo por dia de calendário", () => {
    const editais = [
      edital({ prazo: emDias(0, "23:00") }),
      edital({ prazo: emDias(3) }),
      edital({ prazo: emDias(4) }),
      edital({ prazo: emDias(7) }),
      edital({ prazo: emDias(8) }),
      edital({ prazo: emDias(15) }),
      edital({ prazo: emDias(16) }),
      edital({ prazo: emDias(30) }),
      edital({ prazo: emDias(31) }), // a página não perde editais que ficaram além do limite
    ];
    expect(faixasPrazo(editais, AGORA).map((f) => f.n)).toEqual([2, 2, 2, 3]);
  });

  it("faixas de prazo somam o total", () => {
    const editais = Array.from({ length: 12 }, (_, i) => edital({ prazo: emDias(i * 3) }));
    expect(faixasPrazo(editais, AGORA).reduce((s, f) => s + f.n, 0)).toBe(12);
  });

  it("faixa de valor: limite pertence à faixa de cima", () => {
    expect(idFaixaValor(249_999)).toBe("ate250");
    expect(idFaixaValor(250_000)).toBe("250a500");
    expect(idFaixaValor(999_999)).toBe("500a1mi");
    expect(idFaixaValor(1_000_000)).toBe("1a5mi");
    expect(idFaixaValor(5_000_000)).toBe("5mi");
    expect(idFaixaValor(216_000_000)).toBe("5mi");
    expect(idFaixaValor(null)).toBe(SEM_VALOR);
    expect(idFaixaValor(0.04)).toBe(SEM_VALOR);
  });

  it("resumoValores: conta cada edital em uma faixa só e separa os sem valor", () => {
    const r = resumoValores([
      edital({ valor: 100_000 }),
      edital({ valor: 300_000 }),
      edital({ valor: 700_000 }),
      edital({ valor: null }),
      edital({ valor: 0.04 }),
    ]);
    expect(r.faixas.map((f) => f.n)).toEqual([1, 1, 1, 0, 0]);
    expect(r.semValor).toBe(2);
    expect(r.mediana).toBe(300_000);
  });

  it("mediana", () => {
    expect(mediana([])).toBeNull();
    expect(mediana([5])).toBe(5);
    expect(mediana([9, 1, 5])).toBe(5);
    expect(mediana([1, 2, 3, 10])).toBe(2.5);
  });

  it("rankings: contam um edital uma vez por item e desempatam em ordem alfabética", () => {
    const editais = [
      edital({ uf: "SP", municipio: "Campinas", termos: ["obra", "obra", "reforma"] }),
      edital({ uf: "SP", municipio: "Campinas", termos: ["obra"] }),
      edital({ uf: "MG", municipio: "Uberaba", termos: ["reforma"] }),
      edital({ uf: null, municipio: null, termos: [] }),
    ];
    expect(porUf(editais).map((l) => [l.rotulo, l.n])).toEqual([
      ["SP", 2],
      ["MG", 1],
    ]);
    expect(topMunicipios(editais, 1)).toEqual([{ id: "Campinas / SP", rotulo: "Campinas / SP", n: 2 }]);
    expect(termosMaisCitados(editais, 10).map((l) => [l.rotulo, l.n])).toEqual([
      ["obra", 2],
      ["reforma", 2],
    ]);
  });

  it("resumir", () => {
    const r = resumir(
      [
        edital({ prazo: emDias(2) }),
        edital({ prazo: emDias(9), registro_de_precos: true }),
        edital({ prazo: emDias(3), combina: "parcial" }),
      ],
      AGORA,
    );
    expect(r).toEqual({ combinam: 2, emParte: 1, vencemEm7Dias: 1, registroDePrecos: 1 });
  });
});

describe("filtrar e ordenar", () => {
  const escola = edital({
    objeto: "Reforma da escola municipal",
    orgao: "PREFEITURA DE CAMPINAS",
    uf: "SP",
    prazo: emDias(2),
    valor: 200_000,
    nota: 90,
  });
  const pista = edital({
    objeto: "Pavimentação asfáltica de ruas",
    orgao: "MUNICIPIO DE UBERABA",
    municipio: "Uberaba",
    uf: "MG",
    prazo: emDias(12),
    valor: 3_000_000,
    nota: 70,
    combina: "combina",
  });
  const parcial = edital({
    objeto: "Serviços de conservação",
    uf: "SP",
    prazo: emDias(5),
    valor: null,
    nota: 45,
    combina: "parcial",
  });
  const todos = [pista, parcial, escola];

  it("por padrão esconde o 'em parte' e ordena pelo prazo", () => {
    expect(filtrar(todos, FILTRO_INICIAL, AGORA)).toEqual([escola, pista]);
  });

  it("incluirEmParte traz o que combina só em parte", () => {
    expect(filtrar(todos, { ...FILTRO_INICIAL, incluirEmParte: true }, AGORA)).toEqual([escola, parcial, pista]);
  });

  it("filtra por estado, prazo e faixa de valor", () => {
    expect(filtrar(todos, { ...FILTRO_INICIAL, uf: "MG" }, AGORA)).toEqual([pista]);
    expect(filtrar(todos, { ...FILTRO_INICIAL, prazoMax: 7 }, AGORA)).toEqual([escola]);
    expect(filtrar(todos, { ...FILTRO_INICIAL, faixa: "1a5mi" }, AGORA)).toEqual([pista]);
    expect(filtrar(todos, { ...FILTRO_INICIAL, faixa: SEM_VALOR, incluirEmParte: true }, AGORA)).toEqual([parcial]);
  });

  it("busca sem se importar com acento, caixa ou ordem das palavras", () => {
    const busca = (texto: string) => filtrar(todos, { ...FILTRO_INICIAL, busca: texto }, AGORA);
    expect(busca("PAVIMENTACAO")).toEqual([pista]);
    expect(busca("campinas escola")).toEqual([escola]); // todas as palavras, em qualquer campo
    expect(busca("escola uberaba")).toEqual([]);
    expect(busca("   ")).toEqual([escola, pista]);
  });

  it("ordena por nota, por valor (sem valor no fim) e desempata pelo prazo", () => {
    const igual = edital({ nota: 90, prazo: emDias(1), valor: 200_000 });
    expect(ordenar([escola, pista, igual], "nota").map((e) => e.id)).toEqual([igual.id, escola.id, pista.id]);
    expect(ordenar([parcial, escola, pista], "valor")).toEqual([pista, escola, parcial]);
    expect(ordenar([pista, escola], "prazo")).toEqual([escola, pista]);
  });

  it("não altera a lista original", () => {
    const original = [pista, escola];
    ordenar(original, "prazo");
    expect(original).toEqual([pista, escola]);
  });
});
