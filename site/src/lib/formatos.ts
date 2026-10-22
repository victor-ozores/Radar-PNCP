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

// --------------------------------------------------------------------------- TEXTO EM CAIXA ALTA

const PALAVRAS_PEQUENAS = new Set(
  "a as o os e em de da das do dos na nas no nos para por com sem ao aos ou um uma pelo pela pelos pelas que à às".split(" "),
);

const PRONOMES_COLADOS = new Set("se lhe lhes me te nos vos lo la los las".split(" "));

/** Siglas conhecidas que devem continuar em maiúsculas (as sem vogal, como "PRC" ou "MG", já são siglas). */
const SIGLAS = new Set(
  (
    "ubs upa cras creas caps cei cmei emei emef cbuq bdi nbr abnt srp pncp cnpj cpf ltda epp ete eta epi art rrt crea cau " +
    "saae sabesp copasa sanepar cemig der dnit tjmg tjsp tjrj trf trt ufmg ufpr usp unesp unicamp ifsp ifmg ifpr " +
    "fiocruz sus ses sms pmf led pvc pead pcmso ltcat embrapa sesc senai senac sebrae incra ibama utfpr ufrj uff ufv"
  ).split(" "),
);

/** Nomes de órgãos vêm sem acento na origem; só estas palavras, que se repetem muito, voltam acentuadas. */
const ACENTOS: Record<string, string> = {
  municipio: "município",
  municipios: "municípios",
  justica: "justiça",
  saude: "saúde",
  educacao: "educação",
  agropecuaria: "agropecuária",
  publico: "público",
  publica: "pública",
  publicos: "públicos",
  publicas: "públicas",
  fundacao: "fundação",
  camara: "câmara",
  consorcio: "consórcio",
  consorcios: "consórcios",
  ministerio: "ministério",
  policia: "polícia",
  seguranca: "segurança",
  administracao: "administração",
  assistencia: "assistência",
  agencia: "agência",
  ciencia: "ciência",
  ciencias: "ciências",
  regiao: "região",
  orgao: "órgão",
  agua: "água",
  aguas: "águas",
  habitacao: "habitação",
  transito: "trânsito",
  superintendencia: "superintendência",
  servico: "serviço",
  servicos: "serviços",
};

const SEM_VOGAL = /^[^aeiouáéíóúâêôãõ]+$/i;
const ROMANO = /^[IVX]{1,4}$/;

/** O texto está quase todo em maiúsculas (como muitos objetos e órgãos do PNCP)? */
export function estaGritando(texto: string): boolean {
  const letras = texto.match(/\p{L}/gu) ?? [];
  if (letras.length < 12) return false;
  const maiusculas = letras.filter((c) => c !== c.toLowerCase()).length;
  return maiusculas / letras.length >= 0.7;
}

/**
 * Só na tela: texto em CAIXA ALTA vira "Caixa Alta Normal" (preposições em minúsculas, siglas mantidas).
 * Texto que já está em caixa normal passa sem mudança. O texto original continua no PNCP.
 */
export function suavizaCaixa(texto: string, restauraAcentos = false): string {
  if (!estaGritando(texto)) return texto;
  let primeira = true;
  return texto.replace(/[\p{L}\p{N}]+/gu, (palavra, posicao: number) => {
    const ehPrimeira = primeira;
    primeira = false;
    if (/\d/.test(palavra)) return palavra;
    const baixa = palavra.toLowerCase();
    const base = dobra(palavra);
    if (palavra.length === 1) {
      return ["a", "e", "o", "à"].includes(baixa) && !ehPrimeira ? baixa : palavra.toUpperCase();
    }
    if (texto[posicao - 1] === "-" && PRONOMES_COLADOS.has(baixa)) return baixa; // "refere-se", "dê-lhe"
    if (SIGLAS.has(base) || ROMANO.test(palavra) || (palavra.length <= 5 && SEM_VOGAL.test(palavra))) {
      return palavra.toUpperCase();
    }
    if (!ehPrimeira && PALAVRAS_PEQUENAS.has(baixa)) return baixa;
    const final = restauraAcentos ? (ACENTOS[base] ?? baixa) : baixa;
    return final.charAt(0).toUpperCase() + final.slice(1);
  });
}

/** "Rio de Janeiro / RJ", "SP" ou "". */
export function localidade(municipio: string | null, uf: string | null): string {
  return [municipio, uf].filter(Boolean).join(" / ");
}

export function plural(n: number, singular: string, pluralForma: string): string {
  return n === 1 ? singular : pluralForma;
}
