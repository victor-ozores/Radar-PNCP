// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { edital, painel } from "./testes/modelos";
import type { Edital, Painel } from "./lib/types";

/** O App usa a hora de verdade; por isso os prazos dos testes são montados a partir dela. */
const emHoras = (h: number) => new Date(Date.now() + h * 3_600_000).toISOString();

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "content-type": "application/json" } });
}

function respondeCom(...respostas: Response[]) {
  const fetchFalso = vi.fn();
  for (const r of respostas) fetchFalso.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchFalso);
  return fetchFalso;
}

function dados(editais: Edital[], parcial: Partial<Painel> = {}): Painel {
  const base = painel(editais, parcial);
  // execução recente, para o aviso de "dados velhos" não aparecer nos testes que não são sobre ele
  base.robo.ultima_execucao_ok_em = emHoras(-2);
  return base;
}

/** Os cartões de edital da lista (e só eles). */
function cartoes(): HTMLElement[] {
  const lista = screen.getByRole("heading", { name: "Editais abertos" }).closest("section")!;
  return within(lista)
    .queryAllByRole("listitem")
    .filter((li) => li.classList.contains("edital"));
}

beforeEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  delete document.documentElement.dataset.tema;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("mostra o esqueleto e depois os números, o panorama e a lista", async () => {
    respondeCom(
      resposta(
        dados([
          edital({ prazo: emHoras(30), uf: "SP" }),
          edital({ prazo: emHoras(80), uf: "MG", municipio: "Uberaba" }),
          edital({ prazo: emHoras(120), combina: "parcial", nota: 45 }),
        ]),
      ),
    );
    render(<App />);

    expect(screen.getByText("Carregando os editais…")).toBeTruthy();
    expect(await screen.findByText("editais abertos combinam com o perfil")).toBeTruthy();
    // 2 combinam; o "em parte" fica fora dos números e só entra na lista se a pessoa pedir
    expect(screen.getByText("Combinam só em parte")).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Panorama dos 2 editais/ })).toBeTruthy();
    expect(cartoes()).toHaveLength(2);
  });

  it("esconde o edital cujo prazo já passou desde que o arquivo foi gerado", async () => {
    respondeCom(
      resposta(
        dados([
          edital({ prazo: emHoras(-1), objeto: "Obra já vencida" }),
          edital({ prazo: emHoras(40), objeto: "Obra ainda aberta" }),
        ]),
      ),
    );
    render(<App />);
    await screen.findByText("Obra ainda aberta");
    expect(screen.queryByText("Obra já vencida")).toBeNull();
  });

  it("filtra pela busca e volta ao normal ao limpar", async () => {
    respondeCom(
      resposta(
        dados([
          edital({ prazo: emHoras(30), objeto: "Pavimentação de ruas" }),
          edital({ prazo: emHoras(60), objeto: "Reforma de escola" }),
        ]),
      ),
    );
    render(<App />);
    await screen.findByText("Pavimentação de ruas");

    fireEvent.change(screen.getByLabelText("Buscar"), { target: { value: "ESCOLA" } });
    expect(screen.queryByText("Pavimentação de ruas")).toBeNull();
    expect(screen.getByText("Reforma de escola")).toBeTruthy();
    expect(screen.getByText("Mostrando 1 de 1 edital")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Tirar filtro: Busca: “ESCOLA”" })).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Buscar"), { target: { value: "zzz" } });
    expect(screen.getByText(/Nenhum edital com esses filtros/)).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: "Limpar filtros" })[0]!);
    expect(screen.getByText("Pavimentação de ruas")).toBeTruthy();
    expect(screen.getByText("Reforma de escola")).toBeTruthy();
    expect((screen.getByLabelText("Buscar") as HTMLInputElement).value).toBe("");
  });

  it("clicar numa barra do panorama filtra a lista, mostra a etiqueta e clicar de novo desfaz", async () => {
    respondeCom(
      resposta(
        dados([
          edital({ prazo: emHoras(30), uf: "SP", objeto: "Obra em São Paulo" }),
          edital({ prazo: emHoras(60), uf: "SP", municipio: "Campinas", objeto: "Obra em Campinas" }),
          edital({ prazo: emHoras(90), uf: "MG", municipio: "Uberaba", objeto: "Obra em Uberaba" }),
        ]),
      ),
    );
    render(<App />);
    await screen.findByText("Obra em Uberaba");

    const barraSP = screen.getByRole("button", { name: "SP: 2 editais" });
    expect(barraSP.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(barraSP);

    expect(cartoes()).toHaveLength(2);
    expect(screen.queryByText("Obra em Uberaba")).toBeNull();
    expect(screen.getByRole("button", { name: "SP: 2 editais" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Tirar filtro: Estado: SP" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "SP: 2 editais" }));
    expect(cartoes()).toHaveLength(3);
    expect(screen.queryByRole("button", { name: /Tirar filtro/ })).toBeNull();
  });

  it("leva até a lista ao escolher uma barra, mas não ao desfazer a escolha", async () => {
    const rolar = vi.fn();
    Element.prototype.scrollIntoView = rolar;
    respondeCom(resposta(dados([edital({ prazo: emHoras(30), uf: "SP" }), edital({ prazo: emHoras(60), uf: "MG" })])));
    render(<App />);
    await screen.findByRole("button", { name: "SP: 1 edital" });

    fireEvent.click(screen.getByRole("button", { name: "SP: 1 edital" }));
    expect(rolar).toHaveBeenCalledTimes(1);
    expect(rolar.mock.contexts[0]).toBe(document.getElementById("editais"));

    fireEvent.click(screen.getByRole("button", { name: "SP: 1 edital" })); // desfaz
    expect(rolar).toHaveBeenCalledTimes(1);
  });

  it("o botão do destaque mostra só o que vence em até 7 dias", async () => {
    respondeCom(
      resposta(
        dados([
          edital({ prazo: emHoras(48), objeto: "Vence logo" }),
          edital({ prazo: emHoras(24 * 20), objeto: "Vence depois" }),
        ]),
      ),
    );
    render(<App />);
    await screen.findByText("Vence depois");

    fireEvent.click(screen.getByRole("button", { name: "Só os que vencem em até 7 dias" }));
    expect(screen.getByText("Vence logo")).toBeTruthy();
    expect(screen.queryByText("Vence depois")).toBeNull();
    expect(screen.getByRole("button", { name: "Tirar filtro: Prazo em até 7 dias" })).toBeTruthy();
  });

  it("os botões de estado e de prazo da lista alternam e somam filtros", async () => {
    respondeCom(
      resposta(
        dados([
          edital({ prazo: emHoras(48), uf: "SP", objeto: "SP perto" }),
          edital({ prazo: emHoras(24 * 20), uf: "SP", objeto: "SP longe" }),
          edital({ prazo: emHoras(48), uf: "MG", objeto: "MG perto" }),
        ]),
      ),
    );
    render(<App />);
    await screen.findByText("MG perto");

    fireEvent.click(screen.getByRole("button", { name: "MG" }));
    expect(cartoes()).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "MG" })); // de novo: desliga
    expect(cartoes()).toHaveLength(3);

    fireEvent.click(screen.getByRole("button", { name: "SP" }));
    fireEvent.click(screen.getByRole("button", { name: "Até 7 dias" }));
    expect(cartoes()).toHaveLength(1);
    expect(screen.getByText("SP perto")).toBeTruthy();
  });

  it("mostra 30 de cada vez e pede para mostrar mais", async () => {
    const muitos = Array.from({ length: 35 }, (_, i) => edital({ prazo: emHoras(24 + i), objeto: `Obra ${i}` }));
    respondeCom(resposta(dados(muitos)));
    render(<App />);
    await screen.findByText("Mostrando 30 de 35 editais");

    fireEvent.click(screen.getByRole("button", { name: "Mostrar mais 5" }));
    expect(screen.getByText("Mostrando 35 de 35 editais")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Mostrar mais/ })).toBeNull();
  });

  it("escreve em caixa normal o objeto que veio em CAIXA ALTA", async () => {
    respondeCom(
      resposta(
        dados([
          edital({
            prazo: emHoras(40),
            objeto: "[LICITANET] - CONTRATAÇÃO DE EMPRESA PARA REFORMA DA ESCOLA MUNICIPAL",
            orgao: "MUNICIPIO DE LAMBARI",
          }),
        ]),
      ),
    );
    render(<App />);
    expect(await screen.findByText("Contratação de Empresa para Reforma da Escola Municipal")).toBeTruthy();
    expect(screen.getByText("Município de Lambari")).toBeTruthy();
  });

  it("avisa quando o robô está há mais de um dia e meio sem atualizar", async () => {
    const velho = dados([edital({ prazo: emHoras(50) })]);
    velho.robo.ultima_execucao_ok_em = emHoras(-90);
    respondeCom(resposta(velho));
    render(<App />);
    expect(await screen.findByText("Atenção")).toBeTruthy();
    expect(screen.getByText(/podem estar desatualizados/)).toBeTruthy();
    expect(screen.getByText(/Parado há/)).toBeTruthy(); // e a barra do topo também diz
  });

  it("mostra o robô em dia quando a última execução é recente", async () => {
    respondeCom(resposta(dados([edital({ prazo: emHoras(50) })])));
    render(<App />);
    expect(await screen.findByText("Robô em dia")).toBeTruthy();
    expect(screen.getByText(/Atualizado há/)).toBeTruthy();
  });

  it("alterna o tema, lembra a escolha e aplica no documento", async () => {
    respondeCom(resposta(dados([edital({ prazo: emHoras(50) })])));
    render(<App />);
    await screen.findByText("Robô em dia");

    fireEvent.click(screen.getByRole("button", { name: "Usar tema escuro" }));
    expect(document.documentElement.dataset.tema).toBe("escuro");
    expect(window.localStorage.getItem("radar-tema")).toBe("escuro");

    fireEvent.click(screen.getByRole("button", { name: "Usar tema claro" }));
    expect(document.documentElement.dataset.tema).toBe("claro");
  });

  it("explica o erro e tenta de novo", async () => {
    const fetchFalso = respondeCom(
      resposta({ erro: "fora do ar" }, 503),
      resposta(dados([edital({ prazo: emHoras(50), objeto: "Obra que voltou" })])),
    );
    render(<App />);

    const alerta = await screen.findByRole("alert");
    expect(within(alerta).getByText("Não consegui carregar os editais")).toBeTruthy();
    expect(within(alerta).getByText(/503/)).toBeTruthy();

    fireEvent.click(within(alerta).getByRole("button", { name: "Tentar de novo" }));
    await waitFor(() => expect(screen.getByText("Obra que voltou")).toBeTruthy());
    expect(fetchFalso).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("pede para recarregar quando o arquivo é de uma versão que a página não conhece", async () => {
    respondeCom(resposta(dados([], { versao: 9 })));
    render(<App />);
    const alerta = await screen.findByRole("alert");
    expect(within(alerta).getByText(/Recarregue a página/)).toBeTruthy();
  });

  it("não quebra com lista vazia", async () => {
    respondeCom(resposta(dados([])));
    render(<App />);
    expect(await screen.findByText("editais abertos combinam com o perfil")).toBeTruthy();
    expect(screen.getByText(/Nenhum edital com esses filtros/)).toBeTruthy();
  });
});
