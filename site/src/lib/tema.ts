import { useCallback, useEffect, useState } from "react";

export type Tema = "claro" | "escuro";

const CHAVE = "radar-tema";

function temaSalvo(): Tema | null {
  try {
    const v = window.localStorage.getItem(CHAVE);
    return v === "claro" || v === "escuro" ? v : null;
  } catch {
    return null; // modo privado ou armazenamento bloqueado: segue o tema do sistema
  }
}

function temaDaUrl(): Tema | null {
  const v = new URLSearchParams(window.location.search).get("tema");
  return v === "claro" || v === "escuro" ? v : null;
}

function temaDoSistema(): Tema {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
}

/**
 * Claro ou escuro. Sem escolha, vale o do sistema; ao escolher, a página lembra (só neste navegador).
 * `?tema=escuro` no endereço força um tema sem gravar nada.
 */
export function useTema(): { tema: Tema; alternar: () => void } {
  const [escolhido, setEscolhido] = useState<Tema | null>(() => temaDaUrl() ?? temaSalvo());
  const [sistema, setSistema] = useState<Tema>(temaDoSistema);

  useEffect(() => {
    const consulta = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!consulta) return;
    const aoMudar = () => setSistema(consulta.matches ? "escuro" : "claro");
    consulta.addEventListener("change", aoMudar);
    return () => consulta.removeEventListener("change", aoMudar);
  }, []);

  useEffect(() => {
    const raiz = document.documentElement;
    if (escolhido) raiz.dataset.tema = escolhido;
    else delete raiz.dataset.tema;
  }, [escolhido]);

  const tema = escolhido ?? sistema;
  const alternar = useCallback(() => {
    const novo: Tema = tema === "escuro" ? "claro" : "escuro";
    setEscolhido(novo);
    try {
      window.localStorage.setItem(CHAVE, novo);
    } catch {
      /* sem armazenamento: vale só até recarregar */
    }
  }, [tema]);

  return { tema, alternar };
}
