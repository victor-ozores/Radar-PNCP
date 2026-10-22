/** Formas cinza no lugar do conteúdo enquanto o arquivo carrega, para a página não "pular" depois. */
export function Esqueleto() {
  return (
    <div className="esqueleto" role="status" aria-live="polite">
      <span className="so-leitor">Carregando os editais…</span>
      <div className="esq esq-hero" aria-hidden="true" />
      <div className="esq-linha" aria-hidden="true">
        <div className="esq esq-bloco" />
        <div className="esq esq-bloco" />
        <div className="esq esq-bloco" />
      </div>
      <div className="esq-linha" aria-hidden="true">
        <div className="esq esq-cartao" />
        <div className="esq esq-cartao" />
      </div>
    </div>
  );
}
