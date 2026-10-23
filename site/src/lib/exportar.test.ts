import { describe, expect, it } from "vitest";

import { editaisDoEscopo, linhaDoEdital, nomeDoArquivo, textoDoEscopo } from "./exportar";
import { alterna, desmarca, marca, situacaoDoGrupo, SEM_MARCADOS } from "./selecao";
import { AGORA, edital, emDias } from "../testes/modelos";

describe("linhaDoEdital", () => {
  it("leva o que a tela mostra: texto em caixa normal, órgão com a cidade acentuada, valor e prazo", () => {
    const e = edital({
      objeto: "[LICITANET] - CONTRATAÇÃO DE EMPRESA PARA REFORMA DA ESCOLA MUNICIPAL",
      orgao: "MUNICIPIO DE IBIRITE",
      municipio: "Ibirité",
      uf: "MG",
      numero: "12/2026",
      valor: 978_000,
      registro_de_precos: true,
      termos: ["obra", "reforma"],
      prazo: emDias(2, "07:59"),
    });
    const l = linhaDoEdital(e, AGORA);
    expect(l.objeto).toBe("Contratação de Empresa para Reforma da Escola Municipal");
    expect(l.orgao).toBe("Município de Ibirité");
    expect([l.uf, l.municipio, l.numero]).toEqual(["MG", "Ibirité", "12/2026"]);
    expect(l.valor).toBe(978_000);
    expect(l.registroDePrecos).toBe("Sim");
    expect(l.palavras).toBe("obra, reforma");
    expect(l.faltam).toBe(2);
    expect(l.combina).toBe("Combina muito");
  });

  it("leva a nota e o texto inteiro do objeto e do órgão quando existem, senão o resumo", () => {
    const cheio = linhaDoEdital(
      edital({
        nota: 72,
        objeto: "OBRAS DE REFORMA DA ESCOLA MUNICIPAL JARDIM…",
        objeto_completo: "OBRAS DE REFORMA DA ESCOLA MUNICIPAL JARDIM MONTANHÊS, COM FORNECIMENTO DE MATERIAIS",
        orgao: "SECRETARIA MUNICIPAL DE OBRAS…",
        orgao_completo: "SECRETARIA MUNICIPAL DE OBRAS E INFRAESTRUTURA",
        municipio: "Campinas",
      }),
      AGORA,
    );
    expect(cheio.nota).toBe(72);
    expect(cheio.objeto).toBe("Obras de Reforma da Escola Municipal Jardim Montanhês, com Fornecimento de Materiais");
    expect(cheio.orgao).toBe("Secretaria Municipal de Obras e Infraestrutura");
    const curto = linhaDoEdital(edital({ objeto: "Reforma da escola", objeto_completo: null }), AGORA);
    expect(curto.objeto).toBe("Reforma da escola");
  });

  it("guarda o prazo como o relógio de Brasília, para o Excel mostrar o mesmo horário em qualquer computador", () => {
    const l = linhaDoEdital(edital({ prazo: "2026-10-26T07:59:00-03:00" }), AGORA);
    expect(l.prazo.toISOString()).toBe("2026-10-26T07:59:00.000Z"); // o "Z" aqui é só o jeito de guardar o relógio
    const meiaNoite = linhaDoEdital(edital({ prazo: "2026-10-27T00:00:00-03:00" }), AGORA);
    expect(meiaNoite.prazo.toISOString()).toBe("2026-10-27T00:00:00.000Z"); // não vira "24:00" do dia anterior
  });

  it("valor simbólico ou ausente fica em branco, e sem repetido a coluna fica vazia", () => {
    expect(linhaDoEdital(edital({ valor: 0.04 }), AGORA).valor).toBeNull();
    expect(linhaDoEdital(edital({ valor: null }), AGORA).valor).toBeNull();
    const l = linhaDoEdital(edital({ registro_de_precos: false, numero: null }), AGORA);
    expect([l.registroDePrecos, l.numero, l.tambemPublicadoComo]).toEqual(["Não", "", ""]);
  });

  it("diz em que outros registros o edital foi publicado e não deixa 'faltam' negativo", () => {
    const outros = [
      { id: "a", numero: "34/2026", link: null, publicado: null },
      { id: "b", numero: null, link: null, publicado: null },
    ];
    const l = linhaDoEdital(edital({ repetidos: outros, prazo: emDias(-1) }), AGORA);
    expect(l.tambemPublicadoComo).toBe("nº 34/2026, outro registro");
    expect(l.faltam).toBe(0);
  });
});

describe("editaisDoEscopo", () => {
  const a = edital({ prazo: emDias(5), valor: 100_000 });
  const b = edital({ prazo: emDias(2), valor: 900_000 });
  const c = edital({ prazo: emDias(9), valor: 500_000, combina: "parcial" });
  const todos = [a, b, c];
  const filtrados = [b, a]; // o que a lista mostra agora (por prazo)

  it("'todos do filtro' leva exatamente o que a lista mostra, na ordem dela", () => {
    expect(editaisDoEscopo("filtrados", { marcados: SEM_MARCADOS, filtrados, todos }, "prazo")).toEqual([b, a]);
  });

  it("'todos do painel' ignora o filtro e inclui os que combinam só em parte", () => {
    const r = editaisDoEscopo("todos", { marcados: SEM_MARCADOS, filtrados, todos }, "prazo");
    expect(r.map((e) => e.id)).toEqual([b.id, a.id, c.id]);
  });

  it("'só os marcados' leva os marcados, mesmo os que o filtro de agora escondeu, na ordem escolhida", () => {
    const marcados = new Set([c.id, a.id]); // c não está no filtro
    expect(editaisDoEscopo("selecionados", { marcados, filtrados, todos }, "prazo").map((e) => e.id)).toEqual([a.id, c.id]);
    expect(editaisDoEscopo("selecionados", { marcados, filtrados, todos }, "valor").map((e) => e.id)).toEqual([c.id, a.id]);
  });

  it("marcado que já saiu do painel (prazo passou) não vai para o arquivo", () => {
    const marcados = new Set([a.id, "sumiu"]);
    expect(editaisDoEscopo("selecionados", { marcados, filtrados, todos }, "prazo")).toEqual([a]);
  });
});

describe("nome e texto do arquivo", () => {
  it("o dia de Brasília e o que foi escolhido vão no nome", () => {
    expect(nomeDoArquivo("filtrados", AGORA)).toBe("radar-pncp-2026-10-21-filtro.xlsx");
    expect(nomeDoArquivo("selecionados", AGORA)).toBe("radar-pncp-2026-10-21-selecionados.xlsx");
    expect(nomeDoArquivo("todos", AGORA)).toBe("radar-pncp-2026-10-21-todos.xlsx");
  });

  it("descreve a escolha por extenso, no singular e no plural", () => {
    expect(textoDoEscopo("selecionados", 1)).toBe("1 edital marcado por quem exportou");
    expect(textoDoEscopo("selecionados", 3)).toBe("3 editais marcados por quem exportou");
    expect(textoDoEscopo("filtrados", 1243)).toBe("Todos os 1.243 da lista, com os filtros que estavam ligados");
    expect(textoDoEscopo("todos", 1317)).toMatch(/^Todos os 1\.317 editais abertos do painel, sem nenhum filtro/);
  });
});

describe("marcar editais", () => {
  it("alterna um, marca e desmarca vários, sem mexer no conjunto antigo", () => {
    const vazio = SEM_MARCADOS;
    const um = alterna(vazio, "a");
    expect([...um]).toEqual(["a"]);
    expect(vazio.size).toBe(0);
    expect(alterna(um, "a").size).toBe(0);
    const tres = marca(um, ["b", "c"]);
    expect([...tres].sort()).toEqual(["a", "b", "c"]);
    expect([...desmarca(tres, ["a", "c"])]).toEqual(["b"]);
  });

  it("diz se de um grupo nenhum, alguns ou todos estão marcados", () => {
    const m = new Set(["a", "b"]);
    expect(situacaoDoGrupo(m, ["a", "b"])).toBe("todos");
    expect(situacaoDoGrupo(m, ["a", "c"])).toBe("alguns");
    expect(situacaoDoGrupo(m, ["c", "d"])).toBe("nenhum");
    expect(situacaoDoGrupo(m, [])).toBe("nenhum");
  });
});
