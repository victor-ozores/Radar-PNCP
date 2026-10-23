import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { PNCP_URL, REPO_URL, TAMANHO_PAGINA } from "../config";
import { baixaArquivo } from "../lib/baixar";
import { geraPlanilha } from "../lib/excel";
import { editaisDoEscopo, nomeDoArquivo, type Escopo } from "../lib/exportar";
import { formataInteiro, plural } from "../lib/formatos";
import { filtrar, filtroLimpo, filtrosAtivos, intervaloDisponivel, type Filtro, type Ordem } from "../lib/painel";
import { SEM_MARCADOS, alterna, desmarca, marca, situacaoDoGrupo, type Marcados } from "../lib/selecao";
import type { Edital } from "../lib/types";
import { CartaoEdital } from "./CartaoEdital";
import { Dica } from "./Dica";
import { BarraSelecao, PainelExportar } from "./Exportar";
import { Filtros, FiltrosAtivos } from "./Filtros";

interface Props {
  /** Os editais abertos (inclui os que combinam só em parte). */
  editais: Edital[];
  agora: Date;
  filtro: Filtro;
  aoMudar: (filtro: Filtro) => void;
  /** O que o arquivo do Excel diz sobre a origem dos dados. */
  origem: { geradoEm: string; perfil: string };
}

const ORDENS: { valor: Ordem; rotulo: string }[] = [
  { valor: "prazo", rotulo: "Prazo mais próximo" },
  { valor: "nota", rotulo: "Combina mais" },
  { valor: "valor", rotulo: "Maior valor" },
];

export function Lista({ editais, agora, filtro, aoMudar, origem }: Props) {
  const [visiveis, setVisiveis] = useState(TAMANHO_PAGINA);
  const [marcados, setMarcados] = useState<Marcados>(SEM_MARCADOS);
  const [exportando, setExportando] = useState(false);
  const idDoPainel = useId();

  const ufs = useMemo(
    () => [...new Set(editais.map((e) => e.uf).filter((u): u is string => !!u))].sort(),
    [editais],
  );
  const emParte = useMemo(() => editais.filter((e) => e.combina === "parcial").length, [editais]);
  const registro = useMemo(
    () => editais.filter((e) => e.combina !== "parcial" && e.registro_de_precos).length,
    [editais],
  );
  const datas = useMemo(() => intervaloDisponivel(editais), [editais]);
  const achados = useMemo(() => filtrar(editais, filtro), [editais, filtro]);

  // mudou o filtro: volta a mostrar só a primeira página
  useEffect(() => setVisiveis(TAMANHO_PAGINA), [filtro]);

  const filtrado = filtrosAtivos(filtro).length > 0;
  const mostrando = Math.min(visiveis, achados.length);

  // ---- marcar para o Excel
  const idsQueAparecem = useMemo(() => achados.slice(0, visiveis).map((e) => e.id), [achados, visiveis]);
  const idsDoFiltro = useMemo(() => achados.map((e) => e.id), [achados]);
  /** Marcado que já saiu do painel (o prazo passou) não conta. */
  const quantosMarcados = useMemo(
    () => (marcados.size === 0 ? 0 : editais.reduce((n, e) => n + (marcados.has(e.id) ? 1 : 0), 0)),
    [marcados, editais],
  );
  const naPagina = situacaoDoGrupo(marcados, idsQueAparecem);
  const noFiltro = situacaoDoGrupo(marcados, idsDoFiltro);

  const marcaEdital = useCallback((id: string) => setMarcados((m) => alterna(m, id)), []);
  const marcaPagina = () =>
    setMarcados((m) => (situacaoDoGrupo(m, idsQueAparecem) === "todos" ? desmarca(m, idsQueAparecem) : marca(m, idsQueAparecem)));
  const marcaFiltro = () => setMarcados((m) => marca(m, idsDoFiltro));
  const limpaMarcados = () => setMarcados(SEM_MARCADOS);

  // ---- exportar
  const [painelAberto, setPainelAberto] = useState(false);

  async function exporta(escopo: Escopo): Promise<{ nome: string; quantos: number }> {
    if (exportando) throw new Error("já está gerando");
    setExportando(true);
    try {
      const lista = editaisDoEscopo(escopo, { marcados, filtrados: achados, todos: editais }, filtro.ordem);
      const arquivo = await geraPlanilha(lista, {
        agora: new Date(),
        geradoEm: origem.geradoEm,
        perfil: origem.perfil,
        escopo,
        filtros: filtrosAtivos(filtro).map((f) => f.texto),
        painelUrl: window.location.origin + window.location.pathname,
        repoUrl: REPO_URL,
        pncpUrl: PNCP_URL,
      });
      const nome = nomeDoArquivo(escopo, new Date());
      baixaArquivo(arquivo, nome);
      return { nome, quantos: lista.length };
    } finally {
      setExportando(false);
    }
  }

  return (
    <section className="lista" id="editais" aria-labelledby="lista-titulo">
      <div className="secao-topo">
        <div>
          <h2 id="lista-titulo">Editais abertos</h2>
          <p className="dica-secao">
            Cada cartão é um edital que ainda aceita proposta. O quadrado da esquerda mostra o dia em que o prazo
            acaba.
          </p>
        </div>
        <p className="como-ler">
          Como ler os cartões
          <Dica rotulo="Como ler os cartões">
            <strong>Combina muito</strong> e <strong>Combina</strong>: o edital tem as palavras, o estado, a
            modalidade e o valor do perfil. <strong>Combina em parte</strong>: tem só algumas dessas características.
            Quadrado do prazo: <strong>vermelho</strong> acaba em até 2 dias, <strong>amarelo</strong> em até 7,
            <strong> cinza</strong> depois disso. Sempre confira o edital no PNCP.
          </Dica>
        </p>
      </div>

      <div className="lista-layout">
        <aside className="lista-lateral" aria-label="Filtros">
          <Filtros filtro={filtro} aoMudar={aoMudar} agora={agora} ufs={ufs} datas={datas} emParte={emParte} registro={registro} />
        </aside>

        <div className="lista-resultado">
          <div className="resultado-topo">
            <p className="contagem" role="status">
              {achados.length === 0
                ? "Nenhum edital com esses filtros."
                : `Mostrando ${formataInteiro(mostrando)} de ${formataInteiro(achados.length)} ${plural(achados.length, "edital", "editais")}`}
            </p>
            <label className="campo-ordem">
              <span>Ordenar por</span>
              <select value={filtro.ordem} onChange={(ev) => aoMudar({ ...filtro, ordem: ev.target.value as Ordem })}>
                {ORDENS.map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.rotulo}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <FiltrosAtivos filtro={filtro} aoMudar={aoMudar} />

          {editais.length > 0 && (
            <BarraSelecao
              aparecem={idsQueAparecem.length}
              filtrados={achados.length}
              naPagina={naPagina}
              noFiltro={noFiltro}
              marcados={quantosMarcados}
              aoMarcarPagina={marcaPagina}
              aoMarcarFiltro={marcaFiltro}
              aoLimpar={limpaMarcados}
              exportarAberto={painelAberto}
              aoAlternarExportar={() => setPainelAberto((v) => !v)}
              idDoPainel={idDoPainel}
              exportar={
                painelAberto && (
                  <PainelExportar
                    id={idDoPainel}
                    marcados={quantosMarcados}
                    filtrados={achados.length}
                    todos={editais.length}
                    filtros={filtrosAtivos(filtro).map((f) => f.texto)}
                    agora={agora}
                    aoExportar={exporta}
                  />
                )
              }
            />
          )}

          {achados.length > 0 ? (
            <ul className="editais">
              {achados.slice(0, visiveis).map((e, i) => (
                <CartaoEdital
                  key={e.id}
                  edital={e}
                  agora={agora}
                  posicao={i % TAMANHO_PAGINA}
                  marcado={marcados.has(e.id)}
                  aoMarcar={marcaEdital}
                />
              ))}
            </ul>
          ) : (
            <div className="sem-resultado">
              <p>Nenhum edital combina com essa escolha.</p>
              {filtrado && (
                <button type="button" className="botao" onClick={() => aoMudar(filtroLimpo(filtro))}>
                  Limpar filtros
                </button>
              )}
            </div>
          )}

          {achados.length > visiveis && (
            <p className="mais">
              <button type="button" className="botao" onClick={() => setVisiveis((v) => v + TAMANHO_PAGINA)}>
                Mostrar mais {formataInteiro(Math.min(TAMANHO_PAGINA, achados.length - visiveis))}
              </button>
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
