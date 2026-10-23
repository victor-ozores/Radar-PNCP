/**
 * As frases que contam o que os números querem dizer ("3 prazos acabam em até 3 dias"). Saem sempre dos
 * dados que a página tem na mão, nunca de texto fixo: se os dados mudam, a história muda junto.
 */
import { formataInteiro, formataValor, plural, valorConfiavel } from "./formatos";
import { porUf, resumoValores, type Linha, type ResumoValores } from "./painel";
import { dataEHora, diasAte } from "./tempo";
import type { Edital } from "./types";

/** Parte de um total, em % arredondado (0 se o total for zero). */
export const porcento = (n: number, total: number): number => (total > 0 ? Math.round((100 * n) / total) : 0);

/** ["SP"] -> "SP"; ["SP", "MG"] -> "SP e MG"; ["SP", "MG", "PR"] -> "SP, MG e PR". */
export function listaEm(itens: string[]): string {
  if (itens.length <= 1) return itens.join("");
  return `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`;
}

/** A linha com mais editais (a primeira, se empatar). */
function maiorLinha(linhas: Linha[]): Linha | null {
  let maior: Linha | null = null;
  for (const l of linhas) if (maior === null || l.n > maior.n) maior = l;
  return maior !== null && maior.n > 0 ? maior : null;
}

// --------------------------------------------------------------------------- o resumo do dia (destaque)

/** Quantos prazos acabam logo e quando termina o mais próximo. `fortes` = só os abertos que combinam. */
export function frasePrazo(fortes: Edital[], agora: Date, dias = 3): string {
  if (fortes.length === 0) return "Nenhum edital aberto combina com o perfil agora.";
  const proximo = fortes.reduce((a, b) => (Date.parse(b.prazo) < Date.parse(a.prazo) ? b : a));
  const perto = fortes.filter((e) => diasAte(e.prazo, agora) <= dias).length;
  const quando = dataEHora(proximo.prazo, agora);
  if (perto === 0) return `Nenhum prazo acaba em até ${dias} dias. O mais próximo termina ${quando}.`;
  return `${formataInteiro(perto)} ${plural(perto, "prazo acaba", "prazos acabam")} em até ${dias} dias. O mais próximo termina ${quando}.`;
}

export function fraseOnde(fortes: Edital[]): string | null {
  const ufs = porUf(fortes);
  const [primeira, ...resto] = ufs;
  if (!primeira) return null;
  if (resto.length === 0) return `Todos estão em ${primeira.rotulo}.`;
  const seguintes = listaEm(resto.slice(0, 2).map((l) => l.rotulo));
  return `${primeira.rotulo} concentra ${porcento(primeira.n, fortes.length)}% dos editais (${formataInteiro(primeira.n)}). Depois vêm ${seguintes}.`;
}

export function fraseValor(fortes: Edital[]): string {
  const valores = fortes.map((e) => valorConfiavel(e.valor)).filter((v): v is number => v !== null);
  if (valores.length === 0) return "Nenhum deles informa o valor estimado.";
  const maior = `O maior vale ${formataValor(Math.max(...valores))}.`;
  const acima = valores.filter((v) => v >= 1_000_000).length;
  if (acima === 0) return maior;
  return `${formataInteiro(acima)} ${plural(acima, "passa", "passam")} de R$ 1 milhão. ${maior}`;
}

// --------------------------------------------------------------------------- uma frase por gráfico

export function dicaPrazo(faixas: Linha[]): string | null {
  const total = faixas.reduce((s, f) => s + f.n, 0);
  const maior = maiorLinha(faixas);
  if (!maior) return null;
  const urgentes = faixas.find((f) => f.id === "ate3")?.n ?? 0;
  const urgentesTexto =
    urgentes === 0
      ? "Nenhum acaba em até 3 dias."
      : `${formataInteiro(urgentes)} ${plural(urgentes, "acaba", "acabam")} em até 3 dias.`;
  return `A faixa mais cheia é “${maior.rotulo}”, com ${formataInteiro(maior.n)} de ${formataInteiro(total)} (${porcento(maior.n, total)}%). ${urgentesTexto}`;
}

export function dicaValor(valores: ResumoValores): string | null {
  const total = valores.faixas.reduce((s, f) => s + f.n, 0);
  const maior = maiorLinha(valores.faixas);
  if (!maior) return null;
  return `A faixa mais comum é “${maior.rotulo}”: ${formataInteiro(maior.n)} editais (${porcento(maior.n, total)}%).`;
}

export function dicaUf(ufs: Linha[], total: number): string | null {
  const [primeira, ...resto] = ufs;
  if (!primeira) return null;
  if (resto.length === 0) return `Todos estão em ${primeira.rotulo}.`;
  return `${primeira.rotulo} lidera, com ${formataInteiro(primeira.n)} editais (${porcento(primeira.n, total)}%).`;
}

export function dicaCidade(cidades: Linha[]): string | null {
  const primeira = cidades[0];
  if (!primeira) return null;
  return `${primeira.rotulo} é a cidade com mais editais: ${formataInteiro(primeira.n)}.`;
}

export function dicaTermo(termos: Linha[], total: number): string | null {
  const primeiro = termos[0];
  if (!primeiro) return null;
  return `“${primeiro.rotulo}” aparece em ${formataInteiro(primeiro.n)} dos ${formataInteiro(total)} editais (${porcento(primeiro.n, total)}%).`;
}

/** Atalho para quem só tem a lista de editais. */
export function dicaValorDe(editais: Edital[]): string | null {
  return dicaValor(resumoValores(editais));
}
