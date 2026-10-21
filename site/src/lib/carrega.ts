import { lePainel, PainelInvalido } from "./painel";
import type { Painel } from "./types";

export async function carregaPainel(url: string, sinal?: AbortSignal): Promise<Painel> {
  // `no-cache`: confere com o servidor se o arquivo mudou, em vez de reaproveitar uma cópia velha
  const resposta = await fetch(url, { cache: "no-cache", signal: sinal ?? null });
  if (!resposta.ok) throw new Error(`o servidor respondeu ${resposta.status}`);
  let bruto: unknown;
  try {
    bruto = await resposta.json();
  } catch {
    throw new PainelInvalido("formato", "o arquivo não é um JSON válido");
  }
  return lePainel(bruto);
}
