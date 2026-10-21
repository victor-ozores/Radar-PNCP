import { REPO_URL } from "../config";
import type { Perfil } from "../lib/types";

export function Topo({ perfil }: { perfil: Perfil | null }) {
  return (
    <header className="topo">
      <div className="topo-linha">
        <h1>Radar de Licitações PNCP</h1>
        <span className="selo-demo" title={perfil?.nome}>
          Perfil de demonstração
        </span>
      </div>
      <p className="introducao">
        Todo dia um robô lê os editais publicados no PNCP (Portal Nacional de Contratações Públicas),
        separa as obras e os serviços de engenharia que combinam com um perfil de empresa e mostra aqui
        o que ainda está com prazo aberto.
      </p>
      <p className="topo-links">
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          Código no GitHub
        </a>
      </p>
    </header>
  );
}
