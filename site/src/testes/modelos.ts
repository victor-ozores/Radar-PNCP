import type { Edital, Painel } from "../lib/types";

/** Hora fixa dos testes: quarta-feira, 21/10/2026, 15h00 em Brasília. */
export const AGORA = new Date("2026-10-21T15:00:00-03:00");

/** ISO em Brasília, N dias depois de `AGORA`, no horário dado (ex.: "10:00"). */
export function emDias(dias: number, hora = "10:00"): string {
  const base = new Date(AGORA.getTime() + dias * 86_400_000);
  const dia = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(base);
  return `${dia}T${hora}:00-03:00`;
}

let contador = 0;

export function edital(parcial: Partial<Edital> = {}): Edital {
  contador += 1;
  return {
    id: `0000000000${String(contador).padStart(4, "0")}-1-000${contador}/2026`,
    objeto: "Execução de obras de reforma da escola municipal",
    orgao: "MUNICIPIO DE EXEMPLO",
    uf: "SP",
    municipio: "Campinas",
    modalidade: "Concorrência Eletrônica",
    numero: null,
    valor: 900_000,
    registro_de_precos: false,
    abertura: null,
    prazo: emDias(10),
    nota: 100,
    combina: "muito",
    termos: ["obra", "reforma"],
    link: "https://pncp.gov.br/app/editais/00000000000000/2026/1",
    repetidos: [],
    ...parcial,
  };
}

export function painel(editais: Edital[], parcial: Partial<Painel> = {}): Painel {
  return {
    versao: 1,
    gerado_em: "2026-10-21T12:40:00-03:00",
    janela_dias: 30,
    perfil: {
      nome: "Construtora de médio porte",
      descricao: "Perfil fictício",
      ufs: ["SP", "RJ"],
      modalidades: ["Concorrência Eletrônica", "Pregão Eletrônico"],
      valor_min: 100_000,
      valor_max: 20_000_000,
    },
    totais: { abertos: 500, combinam: editais.length },
    robo: {
      ultima_execucao_ok_em: "2026-10-21T12:38:21-03:00",
      execucoes_30d: 3,
      taxa_sucesso_30d_pct: 100,
      ultima: {
        em: "2026-10-21T12:08:58-03:00",
        status: "success",
        duracao_min: 29.4,
        lidos: 2291,
        novos: 1009,
        prazos_corrigidos: 92,
        situacoes_corrigidas: 74,
      },
      ultimas: [
        { em: "2026-10-19T12:06:25-03:00", status: "success" },
        { em: "2026-10-20T12:06:25-03:00", status: "failed" },
        { em: "2026-10-21T12:08:58-03:00", status: "success" },
      ],
    },
    editais,
    ...parcial,
  };
}
