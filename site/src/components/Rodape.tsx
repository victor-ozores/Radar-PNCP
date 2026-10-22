import { PNCP_URL, REPO_URL } from "../config";
import { VALOR_MINIMO_CONFIAVEL, formataValor } from "../lib/formatos";
import type { Perfil } from "../lib/types";

export function Rodape({ perfil }: { perfil: Perfil | null }) {
  return (
    <footer className="rodape" id="sobre" aria-labelledby="sobre-titulo">
      <h2 id="sobre-titulo">Como ler esta página</h2>
      <div className="rodape-grade">
        <div>
          <h3>Perfil de demonstração</h3>
          <p>
            Os critérios são de uma empresa fictícia de engenharia civil e manutenção predial
            {perfil && (
              <>
                : {perfil.ufs.join(", ")}; {perfil.modalidades.join(", ")}
                {perfil.valor_min !== null && perfil.valor_max !== null && (
                  <>
                    ; valores de {formataValor(perfil.valor_min)} a {formataValor(perfil.valor_max)}
                  </>
                )}
              </>
            )}
            . Para uma empresa de verdade, o perfil é ajustado em um arquivo de configuração.
          </p>
        </div>
        <div>
          <h3>Confira sempre o edital no PNCP</h3>
          <p>
            O robô lê os dados públicos uma vez por dia e pode errar: o prazo pode ter mudado, o edital pode ter
            sido suspenso e o filtro por palavras-chave não entende o contexto como uma pessoa entende.
          </p>
        </div>
        <div>
          <h3>“Combina” é uma estimativa</h3>
          <p>
            Vem de palavras-chave encontradas no objeto do edital (como obra, reforma ou pavimentação), do
            estado, da modalidade e do valor. Não é uma recomendação.
          </p>
        </div>
      </div>
      <p className="rodape-nota">
        Os números consideram só os editais que combinam e continuam abertos agora. Valores abaixo de{" "}
        {formataValor(VALOR_MINIMO_CONFIAVEL)} são tratados como não informados (costumam ser preenchimento
        simbólico). Textos em caixa alta foram ajustados só na tela. Fonte:{" "}
        <a href={PNCP_URL} target="_blank" rel="noopener noreferrer">
          Portal Nacional de Contratações Públicas
        </a>{" "}
        (dados abertos). Projeto e código em{" "}
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          GitHub
        </a>
        .
      </p>
    </footer>
  );
}
