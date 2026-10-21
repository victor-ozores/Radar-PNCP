import { useEffect, useMemo, useState } from "react";

import { TAMANHO_PAGINA } from "../config";
import { formataInteiro, plural } from "../lib/formatos";
import {
  FAIXAS_VALOR,
  FILTRO_INICIAL,
  SEM_VALOR,
  filtrar,
  type Filtro,
  type Ordem,
} from "../lib/painel";
import type { Edital } from "../lib/types";
import { CartaoEdital } from "./CartaoEdital";

const PRAZOS = [
  { valor: "", rotulo: "Qualquer prazo" },
  { valor: "3", rotulo: "Em até 3 dias" },
  { valor: "7", rotulo: "Em até 7 dias" },
  { valor: "15", rotulo: "Em até 15 dias" },
];

const ORDENS: { valor: Ordem; rotulo: string }[] = [
  { valor: "prazo", rotulo: "Prazo mais próximo" },
  { valor: "nota", rotulo: "Combina mais" },
  { valor: "valor", rotulo: "Maior valor" },
];

interface Props {
  /** Os editais abertos (inclui os que combinam só em parte). */
  editais: Edital[];
  agora: Date;
}

export function Lista({ editais, agora }: Props) {
  const [filtro, setFiltro] = useState<Filtro>(FILTRO_INICIAL);
  const [visiveis, setVisiveis] = useState(TAMANHO_PAGINA);

  const ufs = useMemo(
    () => [...new Set(editais.map((e) => e.uf).filter((u): u is string => !!u))].sort(),
    [editais],
  );
  const emParte = useMemo(() => editais.filter((e) => e.combina === "parcial").length, [editais]);
  const achados = useMemo(() => filtrar(editais, filtro, agora), [editais, filtro, agora]);

  // mudou o filtro: volta a mostrar só a primeira página
  useEffect(() => setVisiveis(TAMANHO_PAGINA), [filtro]);

  const muda = (parcial: Partial<Filtro>) => setFiltro((f) => ({ ...f, ...parcial }));
  const filtrado = JSON.stringify({ ...filtro, ordem: "" }) !== JSON.stringify({ ...FILTRO_INICIAL, ordem: "" });

  return (
    <section className="lista" aria-labelledby="lista-titulo">
      <h2 id="lista-titulo">Editais abertos</h2>

      <form className="filtros" role="search" onSubmit={(ev) => ev.preventDefault()}>
        <label className="campo campo-busca">
          <span>Buscar</span>
          <input
            type="search"
            value={filtro.busca}
            placeholder="escola, pavimentação, Campinas…"
            onChange={(ev) => muda({ busca: ev.target.value })}
          />
        </label>
        <label className="campo">
          <span>Estado</span>
          <select value={filtro.uf} onChange={(ev) => muda({ uf: ev.target.value })}>
            <option value="">Todos</option>
            {ufs.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>
        <label className="campo">
          <span>Prazo</span>
          <select
            value={filtro.prazoMax === null ? "" : String(filtro.prazoMax)}
            onChange={(ev) => muda({ prazoMax: ev.target.value ? Number(ev.target.value) : null })}
          >
            {PRAZOS.map((p) => (
              <option key={p.valor} value={p.valor}>
                {p.rotulo}
              </option>
            ))}
          </select>
        </label>
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
        <label className="campo">
          <span>Ordenar por</span>
          <select value={filtro.ordem} onChange={(ev) => muda({ ordem: ev.target.value as Ordem })}>
            {ORDENS.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </select>
        </label>
        {emParte > 0 && (
          <label className="campo-marcar">
            <input
              type="checkbox"
              checked={filtro.incluirEmParte}
              onChange={(ev) => muda({ incluirEmParte: ev.target.checked })}
            />
            <span>
              Incluir os que combinam só em parte ({formataInteiro(emParte)})
            </span>
          </label>
        )}
      </form>

      <p className="contagem" role="status">
        {achados.length === 0
          ? "Nenhum edital com esses filtros."
          : `Mostrando ${formataInteiro(Math.min(visiveis, achados.length))} de ${formataInteiro(achados.length)} ${plural(achados.length, "edital", "editais")}.`}{" "}
        {filtrado && (
          <button type="button" className="link-botao" onClick={() => setFiltro({ ...FILTRO_INICIAL, ordem: filtro.ordem })}>
            Limpar filtros
          </button>
        )}
      </p>

      {achados.length > 0 && (
        <ul className="editais">
          {achados.slice(0, visiveis).map((e) => (
            <CartaoEdital key={e.id} edital={e} agora={agora} />
          ))}
        </ul>
      )}

      {achados.length > visiveis && (
        <p className="mais">
          <button type="button" className="botao" onClick={() => setVisiveis((v) => v + TAMANHO_PAGINA)}>
            Mostrar mais {formataInteiro(Math.min(TAMANHO_PAGINA, achados.length - visiveis))}
          </button>
        </p>
      )}
    </section>
  );
}
