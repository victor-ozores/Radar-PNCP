import { PNCP_URL, REPO_URL } from "../config";
import { VALOR_MINIMO_CONFIAVEL, formataValor } from "../lib/formatos";
import { AVISO_DEMONSTRACAO } from "../lib/exportar";
import type { Perfil } from "../lib/types";


export function Rodape({ perfil }: { perfil: Perfil | null }) {
  return (
    <footer className="rodape" id="sobre" aria-labelledby="sobre-titulo">
      <h2 id="sobre-titulo">Antes de usar</h2>
      <ul className="avisos">
        <li>
          <strong>Perfil de demonstração.</strong> Os critérios são de uma empresa fictícia de engenharia
          civil e manutenção predial; numa empresa de verdade, o perfil é ajustado em um arquivo de
          configuração.
        </li>
        <li>
          <strong>Confira sempre o edital no PNCP.</strong> O robô lê os dados públicos uma vez por dia e
          pode errar: prazo que mudou, edital suspenso ou excluído, texto que o filtro não entende.
        </li>
        <li>
          <strong>É uma demonstração, não um limite.</strong> {AVISO_DEMONSTRACAO}
        </li>
      </ul>

      <details className="detalhes">
        <summary>Como o painel é calculado</summary>
        <ul>
          <li>
            “Combina” é uma estimativa feita com palavras-chave do objeto (obra, reforma, pavimentação…), o
            estado, a modalidade e o valor. Não é uma recomendação.
          </li>
          {perfil && (
            <li>
              Perfil usado: {perfil.ufs.join(", ")}; {perfil.modalidades.join(", ")}
              {perfil.valor_min !== null && perfil.valor_max !== null && (
                <>
                  ; valores de {formataValor(perfil.valor_min)} a {formataValor(perfil.valor_max)}
                </>
              )}
              .
            </li>
          )}
          <li>
            Os números consideram só os editais que combinam e continuam abertos agora. Valores abaixo de{" "}
            {formataValor(VALOR_MINIMO_CONFIAVEL)} são tratados como não informados (costumam ser preenchimento
            simbólico).
          </li>
          <li>Textos em caixa alta aparecem em caixa normal só aqui; o original está no PNCP.</li>
          <li>
            Às vezes o órgão publica o mesmo edital duas vezes no PNCP (mesmo órgão, texto, valor e prazo).
            Aqui ele conta uma vez, e o outro número aparece no cartão, com o link.
          </li>
          <li>
            Fonte:{" "}
            <a href={PNCP_URL} target="_blank" rel="noopener noreferrer">
              Portal Nacional de Contratações Públicas
            </a>{" "}
            (dados abertos). Código em{" "}
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
            .
          </li>
        </ul>
      </details>
    </footer>
  );
}
