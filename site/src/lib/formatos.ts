/** Valores em reais e textos do edital, no mesmo jeito do alerta do Telegram. */

/** Abaixo disto o valor costuma ser preenchimento simbólico (R$ 0,04), não o valor da obra. */
export const VALOR_MINIMO_CONFIAVEL = 1_000;

const NUM = (casas: number) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas });
const UMA_CASA = NUM(1);
const SEM_CASA = NUM(0);

/** O valor, se der para confiar nele; senão `null` ("valor não informado"). */
export function valorConfiavel(valor: number | null): number | null {
  return valor !== null && Number.isFinite(valor) && valor >= VALOR_MINIMO_CONFIAVEL ? valor : null;
}

export function formataValor(valor: number | null): string {
  const v = valorConfiavel(valor);
  if (v === null) return "valor não informado";
  if (v >= 999_500) return `R$ ${UMA_CASA.format(v / 1_000_000)} mi`; // 999.999 não vira "1.000 mil"
  if (v >= 100_000) return `R$ ${SEM_CASA.format(v / 1_000)} mil`;
  return `R$ ${UMA_CASA.format(v / 1_000)} mil`;
}

export function formataInteiro(n: number): string {
  return SEM_CASA.format(n);
}

/**
 * Tira do começo do objeto a etiqueta do sistema que publicou ("[Portal de Compras Públicas] - "),
 * que não diz nada sobre a obra.
 */
export function limpaObjeto(objeto: string): string {
  const limpo = objeto.replace(/^\s*\[[^\]]{1,60}\]\s*[-–:]?\s*/, "").trim();
  return limpo || objeto.trim();
}

/** Minúsculas e sem acento, para a busca achar "construcao" em "CONSTRUÇÃO". */
export function dobra(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** "Rio de Janeiro / RJ", "SP" ou "". */
export function localidade(municipio: string | null, uf: string | null): string {
  return [municipio, uf].filter(Boolean).join(" / ");
}

export function plural(n: number, singular: string, pluralForma: string): string {
  return n === 1 ? singular : pluralForma;
}
