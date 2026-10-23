import { useEffect, useState, type ReactNode } from "react";

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
} from "../lib/painel";
import { diaBR } from "../lib/tempo";
import { Dica } from "./Dica";
import { Icone } from "./Icone";

const PRAZOS_RAPIDOS = [3, 7, 15] as const;

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

/** Só vale data inteira e de ano plausível: enquanto se digita o ano o navegador passa por "0002", "0020"... */
const dataCompleta = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v) && Number(v.slice(0, 4)) >= 2000;

/**
 * Campo de data com rascunho: o que a pessoa digita fica no campo, mas o filtro só muda quando a data está
 * completa (ou quando ela apaga). Sem isso a lista piscava a cada tecla do ano.
 */
function CampoData({
  rotulo,
  valor,
  min,
  max,
  aoMudar,
}: {
  rotulo: string;
  valor: string;
  min: string;
  max: string;
  aoMudar: (valor: string) => void;
}) {
  const [rascunho, setRascunho] = useState(valor);
  useEffect(() => setRascunho(valor), [valor]); // atalhos e "limpar" mudam o valor por fora

  return (
    <label className="campo-data">
      <span>{rotulo}</span>
      <input
        type="date"
        value={rascunho}
        min={min}
        max={max}
        onChange={(ev) => {
          const v = ev.target.value;
          setRascunho(v);
          if (v === "" || dataCompleta(v)) aoMudar(v);
        }}
      />
    </label>
  );
}

function Chip({ ativo, aoClicar, children }: { ativo: boolean; aoClicar: () => void; children: ReactNode }) {
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

function Grupo({ titulo, dica, children }: { titulo: string; dica?: { pergunta: string; texto: ReactNode }; children: ReactNode }) {
  return (
    <div className="grupo">
      <p className="grupo-rotulo">
        {titulo}
        {dica && <Dica rotulo={dica.pergunta}>{dica.texto}</Dica>}
      </p>
      {children}
    </div>
  );
}

function Interruptor({
  marcado,
  aoMudar,
  texto,
  dica,
}: {
  marcado: boolean;
  aoMudar: (v: boolean) => void;
  texto: string;
  dica: { pergunta: string; texto: ReactNode };
}) {
  return (
    <div className="interruptor-linha">
      <label className="interruptor">
        <input type="checkbox" checked={marcado} onChange={(ev) => aoMudar(ev.target.checked)} />
        <span className="interruptor-trilho" aria-hidden="true" />
        <span>{texto}</span>
      </label>
      <Dica rotulo={dica.pergunta}>{dica.texto}</Dica>
    </div>
  );
}

/**
 * Os filtros da lista. No computador ficam numa coluna ao lado dos cartões, sempre à vista; no celular a busca
 * fica à mostra e o resto abre num botão ("Filtrar"), para a lista não ficar lá embaixo.
 */
export function Filtros({ filtro, aoMudar, agora, ufs, datas, emParte, registro }: Props) {
  const [aberto, setAberto] = useState(false);
  const muda = (parcial: Partial<Filtro>) => aoMudar({ ...filtro, ...parcial });
  const hoje = diaBR(agora);
  const escolhidos = filtrosAtivos(filtro).filter((a) => a.chave !== "busca").length;

  return (
    <form className="filtros" role="search" aria-label="Filtrar os editais" onSubmit={(ev) => ev.preventDefault()}>
      <label className="busca">
        <span className="so-leitor">Buscar</span>
        <Icone nome="lupa" tam={18} />
        <input
          type="search"
          value={filtro.busca}
          placeholder="Buscar: escola, praça…"
          onChange={(ev) => muda({ busca: ev.target.value })}
        />
      </label>

      <button
        type="button"
        className="filtros-alternar"
        aria-expanded={aberto}
        aria-controls="filtros-corpo"
        onClick={() => setAberto((v) => !v)}
      >
        <Icone nome="filtro" tam={18} />
        Filtrar por prazo, estado e valor
        {escolhidos > 0 && <span className="contador-filtros">{escolhidos}</span>}
      </button>

      <div id="filtros-corpo" className={`filtros-corpo ${aberto ? "" : "filtros-fechado"}`}>
        <Grupo
          titulo="Prazo para entregar a proposta"
          dica={{
            pergunta: "O que é o prazo para entregar a proposta?",
            texto:
              "É o último dia e hora em que uma empresa pode enviar a proposta. “Até 7 dias” mostra só os que fecham na próxima semana. Para escolher outro intervalo, use as datas.",
          }}
        >
          <div className="chips" role="group" aria-label="Prazo para entregar a proposta">
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
              <CampoData
                rotulo="De"
                valor={filtro.prazoDe}
                min={datas.min}
                max={filtro.prazoAte || datas.max}
                aoMudar={(v) => muda({ prazoDe: v })}
              />
              <CampoData
                rotulo="Até"
                valor={filtro.prazoAte}
                min={filtro.prazoDe || datas.min}
                max={datas.max}
                aoMudar={(v) => muda({ prazoAte: v })}
              />
            </div>
          )}
        </Grupo>

        <Grupo titulo="Estado">
          <div className="chips" role="group" aria-label="Estado">
            {ufs.map((u) => (
              <Chip key={u} ativo={filtro.uf === u} aoClicar={() => muda({ uf: filtro.uf === u ? "" : u })}>
                {u}
              </Chip>
            ))}
          </div>
        </Grupo>

        <Grupo
          titulo="Valor estimado"
          dica={{
            pergunta: "O que é o valor estimado?",
            texto:
              "É quanto o órgão calcula que a contratação vai custar. Não é o preço final, que só aparece depois da disputa. Alguns editais não informam o valor.",
          }}
        >
          <select aria-label="Valor estimado" value={filtro.faixa} onChange={(ev) => muda({ faixa: ev.target.value })}>
            <option value="">Qualquer valor</option>
            {FAIXAS_VALOR.map((f) => (
              <option key={f.id} value={f.id}>
                {f.rotulo}
              </option>
            ))}
            <option value={SEM_VALOR}>Valor não informado</option>
          </select>
        </Grupo>

        {(registro > 0 || emParte > 0) && (
          <div className="grupo grupo-interruptores">
            {registro > 0 && (
              <Interruptor
                marcado={filtro.registro}
                aoMudar={(v) => muda({ registro: v })}
                texto={`Só registro de preços (${formataInteiro(registro)})`}
                dica={{
                  pergunta: "O que é registro de preços?",
                  texto:
                    "O órgão fixa os preços com o vencedor e vai comprando aos poucos, geralmente durante até 1 ano, sem obrigação de comprar tudo. Para a empresa, vira uma ata de preços e não um contrato único.",
                }}
              />
            )}
            {emParte > 0 && (
              <Interruptor
                marcado={filtro.incluirEmParte}
                aoMudar={(v) => muda({ incluirEmParte: v })}
                texto={`Incluir os que combinam só em parte (${formataInteiro(emParte)})`}
                dica={{
                  pergunta: "O que é combinar só em parte?",
                  texto:
                    "São editais que têm algumas características do perfil, mas não todas (nota mais baixa). Ficam fora dos números do painel; marque para vê-los na lista.",
                }}
              />
            )}
          </div>
        )}
      </div>
    </form>
  );
}

/** As escolhas feitas, cada uma numa etiqueta que se tira com um toque, e o botão de limpar tudo. */
export function FiltrosAtivos({ filtro, aoMudar }: { filtro: Filtro; aoMudar: (filtro: Filtro) => void }) {
  const ativos = filtrosAtivos(filtro);
  if (ativos.length === 0) return null;
  return (
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
  );
}
