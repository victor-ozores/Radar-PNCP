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
    "ubs upa cras creas caps cei cmei emei emef cbuq bdi nbr abnt srp pncp cnpj cpf ltda epp ete " +
    "eta epi art rrt crea cau saae sabesp copasa sanepar cemig der dnit tjmg tjsp tjrj trf trt " +
    "ufmg ufpr usp unesp unicamp ifsp ifmg ifpr fiocruz sus ses sms pmf led pvc pead pcmso ltcat " +
    "embrapa sesc senai senac sebrae incra ibama utfpr ufrj uff ufv fnde pac avcb ee cep emeb " +
    "uenp fnhis cefet cemei usf icb cer cpi sam cac utm saa mdic mesp deadm diap dehis decs " +
    "deart fad sesa semop repi iftm dga secod pirf tre copom saaeb feq baep cope femib cejusc " +
    "fema cro ufjf sesmg sema seduc sesp"
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
  estancia: "estância",
  turistica: "turística",
  parana: "paraná",
  sao: "são",
  jose: "josé",
  joao: "joão",
  conceicao: "conceição",
  goias: "goiás",
};

const SEM_VOGAL = /^[^aeiouáéíóúâêôãõ]+$/i;
const ROMANO = /^[IVX]{1,4}$/;
/** "DR.", "AV." e parecidos: abreviação com inicial maiúscula, não sigla. */
const ABREVIACOES = new Set("dr dra sr sra av prof profa eng".split(" "));

interface Palavra {
  texto: string;
  inicio: number;
  /** Tem letra e nenhuma minúscula. */
  maiuscula: boolean;
  /** Só número: não interrompe um trecho em maiúsculas. */
  neutra: boolean;
}

function palavrasDe(texto: string): Palavra[] {
  return [...texto.matchAll(/[\p{L}\p{N}]+/gu)].map((m) => {
    const p = m[0];
    const temLetra = /\p{L}/u.test(p);
    return { texto: p, inicio: m.index ?? 0, maiuscula: temLetra && p === p.toUpperCase(), neutra: !temLetra };
  });
}

const contaLetras = (p: string) => (p.match(/\p{L}/gu) ?? []).length;

/**
 * Trechos de palavras seguidas só em maiúsculas (número no meio não interrompe), como [primeira, última].
 * Só conta como "gritando" quando é longo: 3 palavras e 12 letras. Sigla solta ("UBS", "CRAS") não é.
 */
function trechosGritando(palavras: Palavra[]): Array<[number, number]> {
  const trechos: Array<[number, number]> = [];
  let i = 0;
  while (i < palavras.length) {
    if (!palavras[i]!.maiuscula) {
      i += 1;
      continue;
    }
    let j = i;
    let ultima = i;
    let maiusculas = 0;
    let letras = 0;
    while (j < palavras.length && (palavras[j]!.maiuscula || palavras[j]!.neutra)) {
      if (palavras[j]!.maiuscula) {
        maiusculas += 1;
        letras += contaLetras(palavras[j]!.texto);
        ultima = j;
      }
      j += 1;
    }
    if (maiusculas >= 3 && letras >= 12) trechos.push([i, ultima]);
    i = j;
  }
  return trechos;
}

/** Tem um trecho longo em MAIÚSCULAS (como muitos objetos e órgãos do PNCP)? */
export function estaGritando(texto: string): boolean {
  return trechosGritando(palavrasDe(texto)).length > 0;
}

function suavizaPalavra(p: Palavra, primeiraDoTrecho: boolean, texto: string, restauraAcentos: boolean): string {
  const palavra = p.texto;
  if (/\d/.test(palavra)) return palavra;
  const baixa = palavra.toLowerCase();
  const base = dobra(palavra);
  if (palavra.length === 1) {
    return ["a", "e", "o", "à"].includes(baixa) && !primeiraDoTrecho ? baixa : palavra.toUpperCase();
  }
  if (texto[p.inicio - 1] === "-" && PRONOMES_COLADOS.has(baixa)) return baixa; // "refere-se", "dê-lhe"
  const sigla =
    SIGLAS.has(base) || ROMANO.test(palavra) || (palavra.length <= 5 && SEM_VOGAL.test(palavra) && !ABREVIACOES.has(base));
  if (sigla) return palavra.toUpperCase();
  if (!primeiraDoTrecho && PALAVRAS_PEQUENAS.has(baixa)) return baixa;
  const final = restauraAcentos ? (ACENTOS[base] ?? baixa) : baixa;
  return final.charAt(0).toUpperCase() + final.slice(1);
}

/**
 * Só na tela: o trecho em CAIXA ALTA vira "Caixa Alta Normal" (preposições em minúsculas, siglas mantidas).
 * O resto do texto não muda, e texto já em caixa normal passa direto. O original continua no PNCP.
 */
export function suavizaCaixa(texto: string, restauraAcentos = false): string {
  const palavras = palavrasDe(texto);
  const trechos = trechosGritando(palavras);
  if (trechos.length === 0) return texto;

  const trocas = new Map<number, string>();
  for (const [de, ate] of trechos) {
    for (let k = de; k <= ate; k += 1) {
      trocas.set(k, suavizaPalavra(palavras[k]!, k === de, texto, restauraAcentos));
    }
  }
  return aplicaTrocas(texto, palavras, trocas);
}

/** Troca só as palavras indicadas; o que está entre elas (espaços, pontuação) fica como estava. */
function aplicaTrocas(texto: string, palavras: Palavra[], trocas: Map<number, string>): string {
  let saida = "";
  let cursor = 0;
  palavras.forEach((p, k) => {
    const novo = trocas.get(k);
    if (novo === undefined) return;
    saida += texto.slice(cursor, p.inicio) + novo;
    cursor = p.inicio + p.texto.length;
  });
  return saida + texto.slice(cursor);
}

/**
 * Onde o nome do órgão cita a cidade, usa a grafia da cidade como o próprio edital a traz. O nome do órgão
 * chega sem acento ("Município de Ibirite") e a cidade do mesmo edital vem certa ("Ibirité"). Só entram
 * palavras que diferem no acento ou na caixa, então o sentido não muda.
 */
export function acertaCidade(orgao: string, municipio: string | null): string {
  const cidade = palavrasDe(municipio ?? "").map((p) => p.texto);
  const palavras = palavrasDe(orgao);
  const alvo = cidade.map(dobra);
  const trocas = new Map<number, string>();
  let i = 0;
  while (cidade.length > 0 && i + cidade.length <= palavras.length) {
    if (alvo.every((a, k) => dobra(palavras[i + k]!.texto) === a)) {
      cidade.forEach((c, k) => trocas.set(i + k, c));
      i += cidade.length;
    } else {
      i += 1;
    }
  }
  return trocas.size > 0 ? aplicaTrocas(orgao, palavras, trocas) : orgao;
}

/** O órgão como se lê na tela: caixa normal, acentos das palavras comuns e da cidade. */
export function nomeDoOrgao(orgao: string, municipio: string | null): string {
  return acertaCidade(suavizaCaixa(orgao, true), municipio);
}

/** "Rio de Janeiro / RJ", "SP" ou "". */
export function localidade(municipio: string | null, uf: string | null): string {
  return [municipio, uf].filter(Boolean).join(" / ");
}

export function plural(n: number, singular: string, pluralForma: string): string {
  return n === 1 ? singular : pluralForma;
}
