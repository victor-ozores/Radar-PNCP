/** Entrega um arquivo gerado na própria página para a pessoa guardar (o navegador abre a caixa de "salvar"). */
export function baixaArquivo(arquivo: Blob, nome: string): void {
  const endereco = URL.createObjectURL(arquivo);
  const link = document.createElement("a");
  link.href = endereco;
  link.download = nome;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.append(link);
  link.click();
  link.remove();
  // o navegador ainda está lendo o arquivo neste instante: solta a memória só depois
  setTimeout(() => URL.revokeObjectURL(endereco), 10_000);
}
