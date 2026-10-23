import { dobra, valorConfiavel } from "./formatos";
import { diaBR, diasAte, diaCurto, somaDias } from "./tempo";
import type { Combina, Edital, Painel, Repetido } from "./types";

/** Versão do `painel.json` que esta página sabe ler (ver `VERSAO` em src/radar/painel.py). */
export const VERSAO_SUPORTADA = 1;

export class PainelInvalido extends Error {
  constructor(
    readonly motivo: "formato" | "versao",
    mensagem: string,
  ) {
    super(mensagem);
  }
}

const COMBINA: readonly Combina[] = ["muito", "combina", "parcial"];

/** Como o robô diz o quanto o edital combina com o perfil (cartão da lista e arquivo do Excel). */
export const ROTULO_COMBINA: Record<Combina, string> = {
  muito: "Combina muito",
  combina: "Combina",
  parcial: "Combina em parte",
};

/** Como o edital chega no arquivo: `link` e `repetidos` ainda não foram conferidos. */
type EditalBruto = Omit<Edital, "link" | "repetidos" | "numero"> & {
  link?: unknown;
  repetidos?: unknown;
  numero?: unknown;
};

function ehEdital(x: unknown): x is EditalBruto {
  if (typeof x !== "object" || x === null) return false;
  const e = x as Record<string, unknown>;
  return (
    typeof e.id === "string" &&
    typeof e.objeto === "string" &&
    typeof e.orgao === "string" &&
    typeof e.prazo === "string" &&
    Number.isFinite(Date.parse(e.prazo)) &&
    typeof e.combina === "string" &&
    (COMBINA as readonly string[]).includes(e.combina) &&
    Array.isArray(e.termos)
  );
}

/** Só endereço web de verdade vira link (o arquivo é de fora da página). */
function linkSeguro(x: unknown): string | null {
  return typeof x === "string" && /^https?:\/\//i.test(x) ? x : null;
}

function leRepetidos(x: unknown): Repetido[] {
  if (!Array.isArray(x)) return [];
  return x.flatMap((r): Repetido[] => {
    if (typeof r !== "object" || r === null) return [];
    const o = r as Record<string, unknown>;
    if (typeof o.id !== "string") return [];
    return [
      {
        id: o.id,
        numero: numeroLimpo(o.numero),
        link: linkSeguro(o.link),
        publicado: typeof o.publicado === "string" ? o.publicado : null,
      },
    ];
  });
}

const numeroLimpo = (x: unknown): string | null => (typeof x === "string" && x.trim() ? x.trim() : null);

function leEdital(e: EditalBruto): Edital {
  return { ...e, numero: numeroLimpo(e.numero), link: linkSeguro(e.link), repetidos: leRepetidos(e.repetidos) };
}

/** Confere o arquivo antes de a página confiar nele. Edital com defeito é descartado, não derruba a página. */
export function lePainel(bruto: unknown): Painel {
  if (typeof bruto !== "object" || bruto === null) {
    throw new PainelInvalido("formato", "o arquivo não é um objeto JSON");
  }
  const p = bruto as Record<string, unknown>;
  if (typeof p.versao !== "number") throw new PainelInvalido("formato", "arquivo sem versão");
  if (p.versao > VERSAO_SUPORTADA) {
    throw new PainelInvalido("versao", `arquivo na versão ${p.versao}, a página lê até a ${VERSAO_SUPORTADA}`);
  }
  if (
    typeof p.gerado_em !== "string" ||
    !Number.isFinite(Date.parse(p.gerado_em)) ||
    !Array.isArray(p.editais) ||
    typeof p.perfil !== "object" ||
    p.perfil === null ||
    typeof p.robo !== "object" ||
    p.robo === null ||
    typeof p.totais !== "object" ||
    p.totais === null
  ) {
    throw new PainelInvalido("formato", "faltam campos obrigatórios");
  }
  return { ...(p as unknown as Painel), editais: p.editais.filter(ehEdital).map(leEdital) };
}

// --------------------------------------------------------------------------- quais editais valem

/** Só mostra o que ainda está aberto no momento em que a pessoa olha (o arquivo é de horas atrás). */
export function vigentes(editais: Edital[], agora: Date): Edital[] {
  const t = agora.getTime();
  return editais.filter((e) => Date.parse(e.prazo) > t);
}

/** "Combina muito" e "Combina". O "combina em parte" fica de fora dos números do painel. */
export function combinam(editais: Edital[]): Edital[] {
  return editais.filter((e) => e.combina !== "parcial");
}

// --------------------------------------------------------------------------- números do painel

export interface Linha {
  id: string;
  rotulo: string;
  n: number;
}

/** `min`/`max`: dias de calendário até o prazo, como o filtro da lista os usa (`null` = sem limite). */
export const FAIXAS_PRAZO = [
  { id: "ate3", rotulo: "Até 3 dias", min: null, max: 3 },
  { id: "4a7", rotulo: "4 a 7 dias", min: 4, max: 7 },
  { id: "8a15", rotulo: "8 a 15 dias", min: 8, max: 15 },
  { id: "16a30", rotulo: "16 a 30 dias", min: 16, max: null },
] as const;

export const FAIXAS_VALOR = [
  { id: "ate250", rotulo: "Até R$ 250 mil", max: 250_000 },
  { id: "250a500", rotulo: "R$ 250 a 500 mil", max: 500_000 },
  { id: "500a1mi", rotulo: "R$ 500 mil a 1 mi", max: 1_000_000 },
  { id: "1a5mi", rotulo: "R$ 1 a 5 mi", max: 5_000_000 },
  { id: "5mi", rotulo: "Acima de R$ 5 mi", max: Infinity },
] as const;

export const SEM_VALOR = "sem-valor";

/** As datas de uma faixa de prazo do gráfico, contadas a partir de `hoje` (`AAAA-MM-DD`). */
export function intervaloDaFaixa(faixa: (typeof FAIXAS_PRAZO)[number], hoje: string): { de: string; ate: string } {
  return {
    de: faixa.min === null ? "" : somaDias(hoje, faixa.min),
    ate: faixa.max === null ? "" : somaDias(hoje, faixa.max),
  };
}

/** "Até N dias": do começo até hoje + N. */
export function atePrazoEmDias(hoje: string, dias: number): { de: string; ate: string } {
  return { de: "", ate: somaDias(hoje, dias) };
}

/** Primeiro e último dia de prazo entre os editais (para limitar o calendário aos dias que existem). */
export function intervaloDisponivel(editais: Edital[]): { min: string; max: string } | null {
  let min = "";
  let max = "";
  for (const e of editais) {
    const d = diaDoPrazo(e);
    if (!min || d < min) min = d;
    if (!max || d > max) max = d;
  }
  return min ? { min, max } : null;
}

export function faixasPrazo(editais: Edital[], agora: Date): Linha[] {
  const contagem = new Map<string, number>(FAIXAS_PRAZO.map((f) => [f.id, 0]));
  for (const e of editais) {
    const dias = diasAte(e.prazo, agora);
    const faixa = FAIXAS_PRAZO.find((f) => f.max === null || dias <= f.max);
    if (faixa) contagem.set(faixa.id, (contagem.get(faixa.id) ?? 0) + 1);
  }
  return FAIXAS_PRAZO.map((f) => ({ id: f.id, rotulo: f.rotulo, n: contagem.get(f.id) ?? 0 }));
}

export function idFaixaValor(valor: number | null): string {
  const v = valorConfiavel(valor);
  if (v === null) return SEM_VALOR;
  return (FAIXAS_VALOR.find((f) => v < f.max) ?? FAIXAS_VALOR[FAIXAS_VALOR.length - 1]!).id;
}

export function mediana(numeros: number[]): number | null {
  if (numeros.length === 0) return null;
  const s = [...numeros].sort((a, b) => a - b);
  const meio = Math.floor(s.length / 2);
  return s.length % 2 ? s[meio]! : (s[meio - 1]! + s[meio]!) / 2;
}

export interface ResumoValores {
  faixas: Linha[];
  semValor: number;
  mediana: number | null;
}

export function resumoValores(editais: Edital[]): ResumoValores {
  const contagem = new Map<string, number>();
  const valores: number[] = [];
  for (const e of editais) {
    const id = idFaixaValor(e.valor);
    contagem.set(id, (contagem.get(id) ?? 0) + 1);
    const v = valorConfiavel(e.valor);
    if (v !== null) valores.push(v);
  }
  return {
    faixas: FAIXAS_VALOR.map((f) => ({ id: f.id, rotulo: f.rotulo, n: contagem.get(f.id) ?? 0 })),
    semValor: contagem.get(SEM_VALOR) ?? 0,
    mediana: mediana(valores),
  };
}

function ranking(
  editais: Edital[],
  chaves: (e: Edital) => string[],
  limite: number,
): Linha[] {
  const contagem = new Map<string, number>();
  for (const e of editais) {
    // um edital conta uma vez por chave, mesmo que ela se repita
    for (const k of new Set(chaves(e))) contagem.set(k, (contagem.get(k) ?? 0) + 1);
  }
  return [...contagem.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "pt-BR"))
    .slice(0, limite)
    .map(([rotulo, n]) => ({ id: rotulo, rotulo, n }));
}

export function porUf(editais: Edital[]): Linha[] {
  return ranking(editais, (e) => (e.uf ? [e.uf] : []), 50);
}

export function topMunicipios(editais: Edital[], limite: number): Linha[] {
  return ranking(editais, (e) => (e.municipio && e.uf ? [`${e.municipio} / ${e.uf}`] : []), limite);
}

export function termosMaisCitados(editais: Edital[], limite: number): Linha[] {
  return ranking(editais, (e) => e.termos, limite);
}

export interface Resumo {
  combinam: number;
  emParte: number;
  vencemEm7Dias: number;
  registroDePrecos: number;
}

/** `editais` = o que está vigente. */
export function resumir(editais: Edital[], agora: Date): Resumo {
  const fortes = combinam(editais);
  return {
    combinam: fortes.length,
    emParte: editais.length - fortes.length,
    vencemEm7Dias: fortes.filter((e) => diasAte(e.prazo, agora) <= 7).length,
    registroDePrecos: fortes.filter((e) => e.registro_de_precos).length,
  };
}

// --------------------------------------------------------------------------- lista filtrável

export type Ordem = "prazo" | "nota" | "valor";

export interface Filtro {
  busca: string;
  uf: string;
  /** "Município / UF", como nas barras do panorama; "" = qualquer. */
  cidade: string;
  /** Uma palavra do perfil que o robô encontrou ("obra"); "" = qualquer. */
  termo: string;
  /** Prazo entre duas datas (dia de Brasília, `AAAA-MM-DD`, inclusive); "" = sem limite naquele lado. */
  prazoDe: string;
  prazoAte: string;
  /** id de `FAIXAS_VALOR`, `SEM_VALOR` ou "" (qualquer). */
  faixa: string;
  registro: boolean;
  incluirEmParte: boolean;
  ordem: Ordem;
}

export const FILTRO_INICIAL: Filtro = {
  busca: "",
  uf: "",
  cidade: "",
  termo: "",
  prazoDe: "",
  prazoAte: "",
  faixa: "",
  registro: false,
  incluirEmParte: false,
  ordem: "prazo",
};

/** Os filtros que a pessoa escolheu (tudo menos a ordem), um por etiqueta removível. */
export type ChaveFiltro = "busca" | "uf" | "cidade" | "termo" | "prazo" | "faixa" | "registro" | "incluirEmParte";

export interface FiltroAtivo {
  chave: ChaveFiltro;
  texto: string;
}

function textoPrazo(de: string, ate: string): string {
  if (de && ate) return de === ate ? `Prazo em ${diaCurto(de)}` : `Prazo de ${diaCurto(de)} a ${diaCurto(ate)}`;
  if (ate) return `Prazo até ${diaCurto(ate)}`;
  return `Prazo a partir de ${diaCurto(de)}`;
}

export function filtrosAtivos(f: Filtro): FiltroAtivo[] {
  const ativos: FiltroAtivo[] = [];
  if (f.busca.trim()) ativos.push({ chave: "busca", texto: `Busca: “${f.busca.trim()}”` });
  if (f.uf) ativos.push({ chave: "uf", texto: `Estado: ${f.uf}` });
  if (f.cidade) ativos.push({ chave: "cidade", texto: `Cidade: ${f.cidade}` });
  if (f.termo) ativos.push({ chave: "termo", texto: `Palavra: ${f.termo}` });
  if (f.prazoDe || f.prazoAte) ativos.push({ chave: "prazo", texto: textoPrazo(f.prazoDe, f.prazoAte) });
  if (f.faixa) {
    const faixa = FAIXAS_VALOR.find((v) => v.id === f.faixa);
    ativos.push({ chave: "faixa", texto: f.faixa === SEM_VALOR ? "Valor não informado" : `Valor: ${faixa?.rotulo ?? f.faixa}` });
  }
  if (f.registro) ativos.push({ chave: "registro", texto: "Registro de preços" });
  if (f.incluirEmParte) ativos.push({ chave: "incluirEmParte", texto: "Incluindo “combina em parte”" });
  return ativos;
}

/** O mesmo filtro, sem uma das escolhas. */
export function semFiltro(f: Filtro, chave: ChaveFiltro): Filtro {
  switch (chave) {
    case "prazo":
      return { ...f, prazoDe: "", prazoAte: "" };
    case "busca":
    case "uf":
    case "cidade":
    case "termo":
    case "faixa":
      return { ...f, [chave]: "" };
    case "registro":
    case "incluirEmParte":
      return { ...f, [chave]: false };
  }
}

/** Limpa as escolhas e mantém só a ordem. */
export function filtroLimpo(f: Filtro): Filtro {
  return { ...FILTRO_INICIAL, ordem: f.ordem };
}

const textos = new WeakMap<Edital, string>();

function textoBusca(e: Edital): string {
  let t = textos.get(e);
  if (t === undefined) {
    t = dobra([e.objeto, e.orgao, e.municipio, e.uf, e.modalidade, ...e.termos].filter(Boolean).join(" "));
    textos.set(e, t);
  }
  return t;
}

const diaPorEdital = new WeakMap<Edital, string>();

/** O dia (em Brasília) em que o prazo do edital acaba, `AAAA-MM-DD`. */
export function diaDoPrazo(e: Edital): string {
  let d = diaPorEdital.get(e);
  if (d === undefined) {
    d = diaBR(new Date(e.prazo));
    diaPorEdital.set(e, d);
  }
  return d;
}

export function filtrar(editais: Edital[], f: Filtro): Edital[] {
  const palavras = dobra(f.busca).split(" ").filter(Boolean);
  // datas trocadas de lugar não dão lista vazia: vale o intervalo entre as duas
  const [de, ate] = f.prazoDe && f.prazoAte && f.prazoDe > f.prazoAte ? [f.prazoAte, f.prazoDe] : [f.prazoDe, f.prazoAte];
  const achados = editais.filter((e) => {
    if (!f.incluirEmParte && e.combina === "parcial") return false;
    if (f.uf && e.uf !== f.uf) return false;
    if (f.cidade && `${e.municipio} / ${e.uf}` !== f.cidade) return false;
    if (f.termo && !e.termos.includes(f.termo)) return false;
    if (f.registro && !e.registro_de_precos) return false;
    if (de || ate) {
      const dia = diaDoPrazo(e);
      if (de && dia < de) return false;
      if (ate && dia > ate) return false;
    }
    if (f.faixa && idFaixaValor(e.valor) !== f.faixa) return false;
    if (palavras.length) {
      const t = textoBusca(e);
      if (!palavras.every((p) => t.includes(p))) return false;
    }
    return true;
  });
  return ordenar(achados, f.ordem);
}

const porPrazo = (a: Edital, b: Edital) => Date.parse(a.prazo) - Date.parse(b.prazo) || a.id.localeCompare(b.id);

export function ordenar(editais: Edital[], ordem: Ordem): Edital[] {
  const copia = [...editais];
  if (ordem === "nota") return copia.sort((a, b) => b.nota - a.nota || porPrazo(a, b));
  if (ordem === "valor") {
    return copia.sort((a, b) => {
      const va = valorConfiavel(a.valor);
      const vb = valorConfiavel(b.valor);
      if (va === null && vb === null) return porPrazo(a, b);
      if (va === null) return 1; // sem valor informado vai para o fim
      if (vb === null) return -1;
      return vb - va || porPrazo(a, b);
    });
  }
  return copia.sort(porPrazo);
}
