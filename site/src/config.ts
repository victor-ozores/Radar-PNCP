export const REPO_URL = "https://github.com/victor-ozores/Radar-PNCP";
export const PNCP_URL = "https://pncp.gov.br/app/editais";

/**
 * De onde a página lê os dados: o arquivo público que o robô grava na branch `data`.
 * Em desenvolvimento lê `site/public/painel.json` (uma cópia local, fora do git).
 */
export const PAINEL_URL: string =
  import.meta.env.VITE_PAINEL_URL ??
  (import.meta.env.DEV
    ? "/painel.json"
    : "https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/painel.json");

/** Depois de quantas horas sem atualizar o painel avisa que os dados podem estar velhos. */
export const HORAS_ATE_AVISAR = 36;

/** Quantos editais aparecem de cada vez na lista. */
export const TAMANHO_PAGINA = 30;
