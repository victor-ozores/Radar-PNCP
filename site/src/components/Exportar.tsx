import { useEffect, useId, useRef, useState } from "react";

import { m, surgir } from "../animacao";
import { AVISO_DEMONSTRACAO, nomeDoArquivo, type Escopo } from "../lib/exportar";
import { formataInteiro, plural } from "../lib/formatos";
import type { SituacaoDoGrupo } from "../lib/selecao";
import { Dica } from "./Dica";
import { Icone } from "./Icone";

interface BarraProps {
  /** Quantos cartões aparecem agora, e quantos editais o filtro acha no total. */
  aparecem: number;
  filtrados: number;
  /** Quantos dos que aparecem / do filtro inteiro estão marcados. */
  naPagina: SituacaoDoGrupo;
  noFiltro: SituacaoDoGrupo;
  marcados: number;
  aoMarcarPagina: () => void;
  aoMarcarFiltro: () => void;
  aoLimpar: () => void;
  /** O painel de exportar (aberto ou não). */
  exportar: React.ReactNode;
  exportarAberto: boolean;
  aoAlternarExportar: () => void;
  idDoPainel: string;
}

/**
 * Acima da lista: marcar editais (os que aparecem, ou todos os do filtro, como num e-mail) e abrir o painel
 * de exportar. Marcar é opcional: dá para exportar tudo que está filtrado sem marcar nada.
 */
export function BarraSelecao({
  aparecem,
  filtrados,
  naPagina,
  noFiltro,
  marcados,
  aoMarcarPagina,
  aoMarcarFiltro,
  aoLimpar,
  exportar,
  exportarAberto,
  aoAlternarExportar,
  idDoPainel,
}: BarraProps) {
  const caixa = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (caixa.current) caixa.current.indeterminate = naPagina === "alguns";
  }, [naPagina]);

  const todosAparecem = aparecem >= filtrados;
  const faltaMarcar = naPagina === "todos" && noFiltro !== "todos" && !todosAparecem;
  const filtroTodo = noFiltro === "todos" && !todosAparecem;

  return (
    <div className="selecao">
      <div className="selecao-linha" role="group" aria-label="Marcar editais e exportar">
        <label className="marcar-pagina">
          <input
            ref={caixa}
            type="checkbox"
            checked={naPagina === "todos"}
            disabled={aparecem === 0}
            onChange={aoMarcarPagina}
          />
          <span>
            {todosAparecem ? `Marcar os ${formataInteiro(aparecem)}` : `Marcar os ${formataInteiro(aparecem)} que aparecem`}
          </span>
        </label>

        <p className="marcados" role="status">
          {marcados === 0 ? (
            "Nenhum marcado"
          ) : (
            <>
              <strong>{formataInteiro(marcados)}</strong> {plural(marcados, "marcado", "marcados")}
              <button type="button" className="link-botao" onClick={aoLimpar}>
                Desmarcar tudo
              </button>
            </>
          )}
        </p>

        <button
          type="button"
          className="botao botao-excel"
          aria-expanded={exportarAberto}
          aria-controls={idDoPainel}
          onClick={aoAlternarExportar}
        >
          <Icone nome="planilha" tam={18} />
          Exportar para Excel
        </button>
      </div>

      {faltaMarcar && (
        <m.p className="banner-selecao" role="status" variants={surgir} initial="oculto" animate="visivel">
          Os {formataInteiro(aparecem)} que aparecem estão marcados.
          <button type="button" className="link-botao" onClick={aoMarcarFiltro}>
            Marcar todos os {formataInteiro(filtrados)} da lista
          </button>
        </m.p>
      )}
      {filtroTodo && (
        <m.p className="banner-selecao" role="status" variants={surgir} initial="oculto" animate="visivel">
          Todos os {formataInteiro(filtrados)} da lista estão marcados, até os que ainda não aparecem.
          <button type="button" className="link-botao" onClick={aoLimpar}>
            Desmarcar tudo
          </button>
        </m.p>
      )}

      {exportar}
    </div>
  );
}

// ---------------------------------------------------------------------------- painel de exportar

interface PainelProps {
  id: string;
  marcados: number;
  filtrados: number;
  todos: number;
  /** Texto de cada filtro ligado ("Estado: SP"); vazio = nenhum. */
  filtros: string[];
  agora: Date;
  /** Gera e entrega o arquivo. Devolve o nome e a quantidade, para a mensagem; erro é mostrado na tela. */
  aoExportar: (escopo: Escopo) => Promise<{ nome: string; quantos: number }>;
}

type Fase = { tipo: "parado" } | { tipo: "gerando" } | { tipo: "pronto"; nome: string; quantos: number } | { tipo: "erro" };

const OPCOES: { escopo: Escopo; titulo: string }[] = [
  { escopo: "selecionados", titulo: "Só os que marquei" },
  { escopo: "filtrados", titulo: "Todos os que estão na lista" },
  { escopo: "todos", titulo: "Todos os editais abertos do painel" },
];

export function PainelExportar({ id, marcados, filtrados, todos, filtros, agora, aoExportar }: PainelProps) {
  const grupo = useId();
  const [escolha, setEscolha] = useState<Escopo>(marcados > 0 ? "selecionados" : "filtrados");
  const [fase, setFase] = useState<Fase>({ tipo: "parado" });

  // quem abre o painel e só depois marca editais quer exportar os marcados: a escolha acompanha
  const anteriores = useRef(marcados);
  useEffect(() => {
    if (anteriores.current === 0 && marcados > 0) setEscolha("selecionados");
    anteriores.current = marcados;
  }, [marcados]);

  const quantos: Record<Escopo, number> = { selecionados: marcados, filtrados, todos };
  // a escolha que já não vale (desmarcou tudo, filtro sem resultado) cai para a que vale
  const escopo: Escopo =
    quantos[escolha] > 0 ? escolha : marcados > 0 ? "selecionados" : filtrados > 0 ? "filtrados" : "todos";
  const gerando = fase.tipo === "gerando";

  async function baixar() {
    setFase({ tipo: "gerando" });
    try {
      const r = await aoExportar(escopo);
      setFase({ tipo: "pronto", ...r });
    } catch {
      setFase({ tipo: "erro" });
    }
  }

  return (
    <m.section
      id={id}
      className="exportar"
      aria-labelledby={`${id}-titulo`}
      variants={surgir}
      initial="oculto"
      animate="visivel"
    >
      <header className="exportar-topo">
        <h3 id={`${id}-titulo`}>Exportar para Excel</h3>
        <Dica rotulo="O que vai no arquivo?">
          Uma aba “Editais” com prazo, quantos dias faltam, objeto, órgão, estado, cidade, modalidade, valor, registro de
          preços, palavras do perfil e o link do PNCP, mais três colunas em branco (Situação, Responsável e Observações) e
          uma aba “Sobre este arquivo” com a data, os filtros e o aviso de que é uma demonstração.
        </Dica>
      </header>
      <p className="exportar-intro">
        Leve os editais para a sua planilha de acompanhamento. O arquivo já vem formatado, com filtro nas colunas, o link de
        cada edital e três colunas em branco para a sua equipe preencher.
      </p>

      <fieldset className="exportar-opcoes">
        <legend>O que colocar no arquivo</legend>
        {OPCOES.map((o) => (
          <label key={o.escopo} className={`opcao ${quantos[o.escopo] === 0 ? "opcao-sem" : ""}`}>
            <input
              type="radio"
              name={grupo}
              value={o.escopo}
              checked={escopo === o.escopo}
              disabled={quantos[o.escopo] === 0}
              onChange={() => setEscolha(o.escopo)}
            />
            <span>
              {o.titulo} <strong>({formataInteiro(quantos[o.escopo])})</strong>
              {o.escopo === "filtrados" && (
                <small>{filtros.length > 0 ? `Filtros ligados: ${filtros.join(" · ")}` : "Nenhum filtro ligado: são os que combinam com o perfil."}</small>
              )}
              {o.escopo === "todos" && <small>Ignora os filtros e inclui os que combinam só em parte.</small>}
              {o.escopo === "selecionados" && marcados === 0 && <small>Marque editais na lista para usar esta opção.</small>}
            </span>
          </label>
        ))}
      </fieldset>

      <div className="exportar-acao">
        <button type="button" className="botao-primario" onClick={baixar} disabled={gerando || quantos[escopo] === 0}>
          <Icone nome="baixar" tam={18} />
          {gerando ? "Gerando o arquivo…" : "Baixar arquivo .xlsx"}
        </button>
        <p className="exportar-nome">{nomeDoArquivo(escopo, agora)}</p>
      </div>

      <p className="exportar-estado" role="status">
        {fase.tipo === "pronto" && (
          <>
            <Icone nome="check" tam={16} /> Pronto: {formataInteiro(fase.quantos)} {plural(fase.quantos, "edital", "editais")} em{" "}
            <strong>{fase.nome}</strong>. Veja na pasta de downloads.
          </>
        )}
        {fase.tipo === "erro" && (
          <>
            <Icone nome="alerta" tam={16} /> Não consegui gerar o arquivo agora. Tente de novo em instantes.
          </>
        )}
      </p>

      <p className="exportar-demo">
        <strong>É uma demonstração, não um limite.</strong> {AVISO_DEMONSTRACAO}
      </p>
    </m.section>
  );
}
