/** Formato do arquivo `export/painel.json` (gerado por `src/radar/painel.py`, versão 1). */

export type Combina = "muito" | "combina" | "parcial";

export interface Edital {
  id: string;
  objeto: string;
  orgao: string;
  uf: string | null;
  municipio: string | null;
  modalidade: string;
  valor: number | null;
  registro_de_precos: boolean;
  /** Quando as propostas começam a ser recebidas (ISO com fuso -03:00). */
  abertura: string | null;
  /** Fim do prazo para propostas (ISO com fuso -03:00). */
  prazo: string;
  nota: number;
  combina: Combina;
  termos: string[];
  link: string | null;
}

export interface ExecucaoResumo {
  em: string;
  status: string;
}

export interface UltimaExecucao extends ExecucaoResumo {
  duracao_min: number | null;
  lidos: number | null;
  novos: number | null;
  prazos_corrigidos: number | null;
  situacoes_corrigidas: number | null;
}

export interface Robo {
  ultima_execucao_ok_em: string | null;
  execucoes_30d: number;
  taxa_sucesso_30d_pct: number | null;
  ultima: UltimaExecucao | null;
  ultimas: ExecucaoResumo[];
}

export interface Perfil {
  nome: string;
  descricao: string;
  ufs: string[];
  modalidades: string[];
  valor_min: number | null;
  valor_max: number | null;
}

export interface Painel {
  versao: number;
  gerado_em: string;
  janela_dias: number;
  perfil: Perfil;
  totais: { abertos: number; combinam: number };
  robo: Robo;
  editais: Edital[];
}
