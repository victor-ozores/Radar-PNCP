import { m, surgir } from "../animacao";
import { formataInteiro } from "../lib/formatos";
import {
  FAIXAS_VALOR,
  SEM_VALOR,
  atePrazoEmDias,
  filtroLimpo,
  filtrosAtivos,
  semFiltro,
  type Filtro,
  type Ordem,
} from "../lib/painel";
import { diaBR } from "../lib/tempo";
import { Icone } from "./Icone";

const PRAZOS_RAPIDOS = [3, 7, 15] as const;

const ORDENS: { valor: Ordem; rotulo: string }[] = [
  { valor: "prazo", rotulo: "Prazo mais próximo" },
  { valor: "nota", rotulo: "Combina mais" },
  { valor: "valor", rotulo: "Maior valor" },
];

interface Props {
  filtro: Filtro;
  aoMudar: (filtro: Filtro) => void;
  agora: Date;
  /** UFs que aparecem entre os editais abertos. */
  ufs: string[];
  /** Primeiro e último dia de prazo entre os editais abertos (limita o calendário). */
  datas: { min: string; max: string } | null;
  /** Quantos combinam só em parte (a opção some se for zero). */
  emParte: number;
  /** Quantos estão em registro de preços. */
  registro: number;
}

function Chip({ ativo, aoClicar, children }: { ativo: boolean; aoClicar: () => void; children: React.ReactNode }) {
  return (
    <m.button
      type="button"
      className={`chip ${ativo ? "chip-ativo" : ""}`}
      aria-pressed={ativo}
      onClick={aoClicar}
      whileTap={{ scale: 0.96 }}
    >
      {ativo && <Icone nome="check" tam={14} />}
      {children}
    </m.button>
  );
}

export function Filtros({ filtro, aoMudar, agora, ufs, datas, emParte, registro }: Props) {
  const muda = (parcial: Partial<Filtro>) => aoMudar({ ...filtro, ...parcial });
  const ativos = filtrosAtivos(filtro);
  const hoje = diaBR(agora);
  const avancados = [filtro.faixa, filtro.registro, filtro.incluirEmParte].filter(Boolean).length;

  return (
    <form className="filtros" role="search" aria-label="Filtrar os editais" onSubmit={(ev) => ev.preventDefault()}>
      <label className="busca">
        <span className="so-leitor">Buscar</span>
        <Icone nome="lupa" tam={18} />
        <input
          type="search"
          value={filtro.busca}
          placeholder="Buscar: escola, pavimentação…"
          onChange={(ev) => muda({ busca: ev.target.value })}
        />
      </label>

      <div className="grupo-chips">
        <span className="grupo-rotulo" id="rotulo-estado">
          Estado
        </span>
        <div className="chips" role="group" aria-labelledby="rotulo-estado">
          {ufs.map((u) => (
            <Chip key={u} ativo={filtro.uf === u} aoClicar={() => muda({ uf: filtro.uf === u ? "" : u })}>
              {u}
            </Chip>
          ))}
        </div>
      </div>

      <div className="grupo-chips">
        <span className="grupo-rotulo" id="rotulo-prazo">
          Prazo para entregar a proposta
        </span>
        <div className="chips" role="group" aria-labelledby="rotulo-prazo">
          {PRAZOS_RAPIDOS.map((dias) => {
            const { de, ate } = atePrazoEmDias(hoje, dias);
            const ativo = filtro.prazoDe === de && filtro.prazoAte === ate;
            return (
              <Chip key={dias} ativo={ativo} aoClicar={() => muda(ativo ? { prazoDe: "", prazoAte: "" } : { prazoDe: de, prazoAte: ate })}>
                Até {dias} dias
              </Chip>
            );
          })}
        </div>
        {datas && (
          <div className="periodo" role="group" aria-label="Escolher as datas do prazo">
            <label className="campo-data">
              <span>De</span>
              <input
                type="date"
                value={filtro.prazoDe}
                min={datas.min}
                max={filtro.prazoAte || datas.max}
                onChange={(ev) => muda({ prazoDe: ev.target.value })}
              />
            </label>
            <label className="campo-data">
              <span>Até</span>
              <input
                type="date"
                value={filtro.prazoAte}
                min={filtro.prazoDe || datas.min}
                max={datas.max}
                onChange={(ev) => muda({ prazoAte: ev.target.value })}
              />
            </label>
          </div>
        )}
      </div>

      <label className="campo campo-ordem">
        <span>Ordenar por</span>
        <select value={filtro.ordem} onChange={(ev) => muda({ ordem: ev.target.value as Ordem })}>
          {ORDENS.map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.rotulo}
            </option>
          ))}
        </select>
      </label>

      <details className="mais-filtros" open={avancados > 0 || undefined}>
        <summary>
          Mais filtros
          {avancados > 0 && <span className="contador-filtros">{avancados}</span>}
        </summary>
        <div className="mais-filtros-corpo">
          <label className="campo">
            <span>Valor</span>
            <select value={filtro.faixa} onChange={(ev) => muda({ faixa: ev.target.value })}>
              <option value="">Qualquer valor</option>
              {FAIXAS_VALOR.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.rotulo}
                </option>
              ))}
              <option value={SEM_VALOR}>Valor não informado</option>
            </select>
          </label>
          {registro > 0 && (
            <label className="interruptor">
              <input type="checkbox" checked={filtro.registro} onChange={(ev) => muda({ registro: ev.target.checked })} />
              <span className="interruptor-trilho" aria-hidden="true" />
              <span>Só registro de preços ({formataInteiro(registro)})</span>
            </label>
          )}
          {emParte > 0 && (
            <label className="interruptor">
              <input
                type="checkbox"
                checked={filtro.incluirEmParte}
                onChange={(ev) => muda({ incluirEmParte: ev.target.checked })}
              />
              <span className="interruptor-trilho" aria-hidden="true" />
              <span>Incluir os que combinam só em parte ({formataInteiro(emParte)})</span>
            </label>
          )}
        </div>
      </details>

      {ativos.length > 0 && (
        <div className="ativos" aria-label="Filtros ativos">
          <ul>
            {ativos.map((a) => (
              <m.li key={a.chave} variants={surgir} initial="oculto" animate="visivel">
                <button
                  type="button"
                  className="etiqueta-filtro"
                  aria-label={`Tirar filtro: ${a.texto}`}
                  onClick={() => aoMudar(semFiltro(filtro, a.chave))}
                >
                  {a.texto}
                  <Icone nome="fechar" tam={14} />
                </button>
              </m.li>
            ))}
          </ul>
          <button type="button" className="link-botao" onClick={() => aoMudar(filtroLimpo(filtro))}>
            Limpar filtros
          </button>
        </div>
      )}
    </form>
  );
}
