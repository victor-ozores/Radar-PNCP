import { describe, expect, it } from "vitest";

import { AGORA } from "../testes/modelos";
import {
  dataCurta,
  dataEHora,
  diaBR,
  diaCurto,
  diaDoMes,
  diasAte,
  emQuantosDias,
  haQuantoTempo,
  horaCurta,
  horasDesde,
  mesCurto,
  somaDias,
} from "./tempo";

describe("dia em Brasília", () => {
  it("usa o fuso de Brasília, não o UTC", () => {
    expect(diaBR(new Date("2026-10-22T01:30:00Z"))).toBe("2026-10-21"); // 22h30 de quarta em Brasília
    expect(diaBR(new Date("2026-10-21T02:30:00Z"))).toBe("2026-10-20"); // 23h30 de terça
  });

  it("conta dias de calendário, não blocos de 24 horas", () => {
    expect(diasAte("2026-10-21T23:59:00-03:00", AGORA)).toBe(0);
    expect(diasAte("2026-10-22T00:01:00-03:00", AGORA)).toBe(1); // 10 minutos de diferença, mas é amanhã
    expect(diasAte("2026-10-28T10:00:00-03:00", AGORA)).toBe(7);
    expect(diasAte("2026-10-20T10:00:00-03:00", AGORA)).toBe(-1);
  });

  it("atravessa a virada do mês e do ano", () => {
    expect(diasAte("2026-11-01T10:00:00-03:00", new Date("2026-10-31T23:00:00-03:00"))).toBe(1);
    expect(diasAte("2027-01-02T10:00:00-03:00", new Date("2026-12-31T08:00:00-03:00"))).toBe(2);
  });

  it("aceita Date e texto ISO", () => {
    expect(diasAte(new Date("2026-10-23T12:00:00-03:00"), AGORA)).toBe(2);
  });
});

describe("dias em texto AAAA-MM-DD", () => {
  it("soma dias de calendário, virando mês e ano", () => {
    expect(somaDias("2026-10-21", 7)).toBe("2026-10-28");
    expect(somaDias("2026-10-28", 7)).toBe("2026-11-04");
    expect(somaDias("2026-12-30", 3)).toBe("2027-01-02");
    expect(somaDias("2026-03-01", -1)).toBe("2026-02-28");
    expect(somaDias("2024-02-28", 1)).toBe("2024-02-29"); // ano bissexto
  });

  it("diaCurto", () => {
    expect(diaCurto("2026-10-05")).toBe("05/10");
  });
});

describe("textos de data", () => {
  it("formata dia, hora e quando", () => {
    expect(dataCurta("2026-10-28T10:00:00-03:00")).toBe("28/10");
    expect(horaCurta("2026-10-28T10:05:00-03:00")).toBe("10h05");
    expect(horaCurta("2026-10-28T00:30:00-03:00")).toBe("00h30"); // meia-noite não vira "24h"
  });

  it("dia e mês abreviado, no fuso de Brasília", () => {
    expect(diaDoMes("2026-10-05T10:00:00-03:00")).toBe("5");
    expect(mesCurto("2026-10-05T10:00:00-03:00")).toBe("out");
    expect(mesCurto("2026-12-28T10:00:00-03:00")).toBe("dez");
    // 1h da manhã de 1º/11 em UTC ainda é 31/10 à noite em Brasília
    expect(diaDoMes("2026-11-01T01:30:00Z")).toBe("31");
    expect(mesCurto("2026-11-01T01:30:00Z")).toBe("out");
  });

  it("diz hoje, amanhã ou o dia da semana", () => {
    expect(dataEHora("2026-10-21T23:59:00-03:00", AGORA)).toBe("hoje às 23h59");
    expect(dataEHora("2026-10-22T08:00:00-03:00", AGORA)).toBe("amanhã às 08h00");
    expect(dataEHora("2026-10-28T10:00:00-03:00", AGORA)).toBe("qua 28/10 às 10h00");
  });

  it("mostra a hora de Brasília mesmo quando o texto vem em UTC", () => {
    expect(horaCurta("2026-10-28T13:00:00Z")).toBe("10h00");
  });

  it("emQuantosDias", () => {
    expect(emQuantosDias("2026-10-21T23:00:00-03:00", AGORA)).toBe("hoje");
    expect(emQuantosDias("2026-10-22T09:00:00-03:00", AGORA)).toBe("amanhã");
    expect(emQuantosDias("2026-10-28T09:00:00-03:00", AGORA)).toBe("em 7 dias");
  });
});

describe("há quanto tempo", () => {
  const depois = (min: number) => new Date(AGORA.getTime() + min * 60_000);

  it("escolhe a unidade certa", () => {
    expect(haQuantoTempo(AGORA, depois(1))).toBe("agora há pouco");
    expect(haQuantoTempo(AGORA, depois(45))).toBe("há 45 min");
    expect(haQuantoTempo(AGORA, depois(7 * 60))).toBe("há 7 h");
    expect(haQuantoTempo(AGORA, depois(48 * 60))).toBe("há 2 dias");
  });

  it("não dá número negativo se o relógio de quem abre estiver atrasado", () => {
    expect(haQuantoTempo(depois(30), AGORA)).toBe("agora há pouco");
  });

  it("horasDesde", () => {
    expect(horasDesde(AGORA, depois(90))).toBe(1.5);
  });
});
