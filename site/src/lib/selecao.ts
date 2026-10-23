/** Os editais que a pessoa marcou para levar ao Excel. Conjuntos novos a cada mudança (é assim que o React percebe). */

export type Marcados = ReadonlySet<string>;

export const SEM_MARCADOS: Marcados = new Set<string>();

export function alterna(marcados: Marcados, id: string): Marcados {
  const novo = new Set(marcados);
  if (!novo.delete(id)) novo.add(id);
  return novo;
}

export function marca(marcados: Marcados, ids: string[]): Marcados {
  return new Set([...marcados, ...ids]);
}

export function desmarca(marcados: Marcados, ids: string[]): Marcados {
  const novo = new Set(marcados);
  for (const id of ids) novo.delete(id);
  return novo;
}

export type SituacaoDoGrupo = "nenhum" | "alguns" | "todos";

/** Quantos de um grupo de editais (a página que aparece, o filtro inteiro) estão marcados. */
export function situacaoDoGrupo(marcados: Marcados, ids: string[]): SituacaoDoGrupo {
  if (ids.length === 0) return "nenhum";
  const n = ids.filter((id) => marcados.has(id)).length;
  return n === 0 ? "nenhum" : n === ids.length ? "todos" : "alguns";
}
