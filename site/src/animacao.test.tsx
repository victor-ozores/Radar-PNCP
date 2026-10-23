// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useContagem } from "./animacao";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

/** Troca o relógio e o "próximo quadro" por versões que o teste comanda. */
function quadrosComandados(inicio: number) {
  vi.spyOn(performance, "now").mockReturnValue(inicio);
  const fila: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => fila.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});
  return (momento: number) => {
    const cb = fila.shift();
    if (cb) act(() => cb(momento));
  };
}

describe("useContagem", () => {
  it("sobe até o valor sem nunca passar por número negativo, mesmo se o 1º quadro chegar adiantado", () => {
    const quadro = quadrosComandados(1000);
    const { result } = renderHook(() => useContagem(1000));
    const vistos = [result.current];

    for (const momento of [995, 1100, 1500, 2300]) {
      quadro(momento); // 995: o navegador entregou o quadro um instante antes do início
      vistos.push(result.current);
    }

    expect(Math.min(...vistos)).toBeGreaterThanOrEqual(0);
    expect(vistos).toEqual([...vistos].sort((a, b) => a - b));
    expect(result.current).toBe(1000);
  });

  it("quando o alvo muda no meio, a nova contagem parte do número que está na tela, não do zero", () => {
    const quadro = quadrosComandados(1000);
    const { result, rerender } = renderHook(({ alvo }) => useContagem(alvo), { initialProps: { alvo: 1000 } });
    quadro(1200);
    const naTela = result.current;
    expect(naTela).toBeGreaterThan(0);
    expect(naTela).toBeLessThan(1000);

    rerender({ alvo: 900 });
    quadro(1201);
    expect(result.current).toBeGreaterThan(naTela - 50); // continua por perto, sem voltar a 0
    quadro(1900);
    expect(result.current).toBe(900);
  });
});
