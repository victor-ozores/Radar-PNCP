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

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("mostra os números, o panorama e a lista depois de carregar", async () => {
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
    // 2 combinam; o "em parte" fica fora dos números e aparece só como aviso
    expect(screen.getByText(/Há ainda 1 edital que combina só em parte/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Panorama dos 2 editais que combinam/ })).toBeTruthy();
    const lista = screen.getByRole("heading", { name: "Editais abertos" }).closest("section")!;
    expect(within(lista).getAllByRole("listitem").filter((li) => li.className === "edital")).toHaveLength(2);
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
    expect(screen.getByText("Mostrando 1 de 1 edital.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Buscar"), { target: { value: "zzz" } });
    expect(screen.getByText(/Nenhum edital com esses filtros/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));
    expect(screen.getByText("Pavimentação de ruas")).toBeTruthy();
    expect(screen.getByText("Reforma de escola")).toBeTruthy();
  });

  it("mostra 30 de cada vez e pede para mostrar mais", async () => {
    const muitos = Array.from({ length: 35 }, (_, i) => edital({ prazo: emHoras(24 + i), objeto: `Obra ${i}` }));
    respondeCom(resposta(dados(muitos)));
    render(<App />);
    await screen.findByText("Mostrando 30 de 35 editais.");

    fireEvent.click(screen.getByRole("button", { name: "Mostrar mais 5" }));
    expect(screen.getByText("Mostrando 35 de 35 editais.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Mostrar mais/ })).toBeNull();
  });

  it("avisa quando o robô está há mais de um dia e meio sem atualizar", async () => {
    const velho = dados([edital({ prazo: emHoras(50) })]);
    velho.robo.ultima_execucao_ok_em = emHoras(-90);
    respondeCom(resposta(velho));
    render(<App />);
    expect(await screen.findByText("Atenção")).toBeTruthy();
    expect(screen.getByText(/podem estar desatualizados/)).toBeTruthy();
  });

  it("mostra o robô em dia quando a última execução é recente", async () => {
    respondeCom(resposta(dados([edital({ prazo: emHoras(50) })])));
    render(<App />);
    expect(await screen.findByText("Robô em dia")).toBeTruthy();
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
