/** Datas e horas sempre no fuso de Brasília, não importa onde a pessoa abriu a página. */

const FUSO = "America/Sao_Paulo";

const ANO_MES_DIA = new Intl.DateTimeFormat("en-CA", {
  timeZone: FUSO,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const DIA_MES = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, day: "2-digit", month: "2-digit" });
const HORA = new Intl.DateTimeFormat("pt-BR", {
  timeZone: FUSO,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const DIA_SEMANA = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, weekday: "short" });

const MS_DIA = 86_400_000;

export function paraData(iso: string | Date): Date {
  return iso instanceof Date ? iso : new Date(iso);
}

/** Dia do calendário em Brasília, como `AAAA-MM-DD`. */
export function diaBR(d: Date): string {
  const partes = Object.fromEntries(ANO_MES_DIA.formatToParts(d).map((p) => [p.type, p.value]));
  return `${partes.year}-${partes.month}-${partes.day}`;
}

/** Quantos dias de calendário (em Brasília) faltam de `agora` até `alvo`. 0 = hoje; negativo = passou. */
export function diasAte(alvo: string | Date, agora: Date): number {
  const [a, m, d] = diaBR(paraData(alvo)).split("-").map(Number) as [number, number, number];
  const [a0, m0, d0] = diaBR(agora).split("-").map(Number) as [number, number, number];
  return Math.round((Date.UTC(a, m - 1, d) - Date.UTC(a0, m0 - 1, d0)) / MS_DIA);
}

export function dataCurta(iso: string | Date): string {
  return DIA_MES.format(paraData(iso));
}

export function horaCurta(iso: string | Date): string {
  return HORA.format(paraData(iso)).replace(":", "h");
}

export function diaSemana(iso: string | Date): string {
  return DIA_SEMANA.format(paraData(iso)).replace(".", "");
}

/** "hoje às 14h30", "amanhã às 09h00" ou "sex 30/10 às 10h00". */
export function dataEHora(iso: string | Date, agora: Date): string {
  const dias = diasAte(iso, agora);
  const hora = horaCurta(iso);
  if (dias === 0) return `hoje às ${hora}`;
  if (dias === 1) return `amanhã às ${hora}`;
  return `${diaSemana(iso)} ${dataCurta(iso)} às ${hora}`;
}

/** "hoje", "amanhã" ou "em 7 dias" (dias de calendário). */
export function emQuantosDias(iso: string | Date, agora: Date): string {
  const dias = diasAte(iso, agora);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "amanhã";
  return `em ${dias} dias`;
}

/** "agora há pouco", "há 3 h", "há 2 dias": para dizer há quanto tempo o robô atualizou. */
export function haQuantoTempo(iso: string | Date, agora: Date): string {
  const min = Math.max(0, Math.round((agora.getTime() - paraData(iso).getTime()) / 60_000));
  if (min < 2) return "agora há pouco";
  if (min < 60) return `há ${min} min`;
  const horas = Math.round(min / 60);
  if (horas < 36) return `há ${horas} h`;
  return `há ${Math.round(horas / 24)} dias`;
}

export function horasDesde(iso: string | Date, agora: Date): number {
  return (agora.getTime() - paraData(iso).getTime()) / 3_600_000;
}
