import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { Icone } from "./Icone";

interface Props {
  /** O nome do botão para leitor de tela, em forma de pergunta: "O que é registro de preços?". */
  rotulo: string;
  children: ReactNode;
}

const FOLGA = 8;

/** Foco por teclado (Tab) abre o balão; foco que veio de um toque não, senão o segundo toque não conseguiria fechar. */
function foiPeloTeclado(el: HTMLElement): boolean {
  try {
    return el.matches(":focus-visible");
  } catch {
    return false; // navegador sem o seletor: só o clique abre
  }
}

/**
 * Um "?" pequeno que explica o termo ao lado. Abre ao passar o mouse, ao focar com o teclado e ao tocar (toque
 * de novo, Esc ou toque fora fecha). O balão é desenhado fora do resto da página (em `body`) para nenhum
 * cartão cortar nem a animação de entrada deslocar; ele fecha ao rolar, porque fica preso à tela.
 */
export function Dica({ rotulo, children }: Props) {
  const id = useId();
  const botao = useRef<HTMLButtonElement>(null);
  const balao = useRef<HTMLSpanElement>(null);
  const [fixa, setFixa] = useState(false); // aberta por clique/toque
  const [passando, setPassando] = useState(false); // aberta por mouse ou teclado
  const [posicao, setPosicao] = useState<{ top: number; left: number } | null>(null);
  const aberta = fixa || passando;

  // coloca o balão logo abaixo do botão (ou acima, se não couber), sempre dentro da tela
  useLayoutEffect(() => {
    if (!aberta || !botao.current || !balao.current) {
      setPosicao(null);
      return;
    }
    const b = botao.current.getBoundingClientRect();
    const { width, height } = balao.current.getBoundingClientRect();
    const cabeEmBaixo = b.bottom + FOLGA + height <= window.innerHeight - FOLGA;
    const top = cabeEmBaixo ? b.bottom + FOLGA : Math.max(FOLGA, b.top - FOLGA - height);
    const centro = b.left + b.width / 2 - width / 2;
    const left = Math.min(Math.max(FOLGA, centro), Math.max(FOLGA, window.innerWidth - width - FOLGA));
    setPosicao({ top, left });
  }, [aberta]);

  useEffect(() => {
    if (!aberta) return;
    const fecha = () => {
      setFixa(false);
      setPassando(false);
    };
    const aoTeclar = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") fecha();
    };
    const aoTocarFora = (ev: Event) => {
      const alvo = ev.target as Node;
      if (!botao.current?.contains(alvo) && !balao.current?.contains(alvo)) fecha();
    };
    document.addEventListener("keydown", aoTeclar);
    document.addEventListener("pointerdown", aoTocarFora);
    window.addEventListener("scroll", fecha, { passive: true });
    window.addEventListener("resize", fecha);
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.removeEventListener("pointerdown", aoTocarFora);
      window.removeEventListener("scroll", fecha);
      window.removeEventListener("resize", fecha);
    };
  }, [aberta]);

  return (
    <>
      <button
        ref={botao}
        type="button"
        className="dica-botao"
        aria-label={rotulo}
        aria-describedby={aberta ? id : undefined}
        aria-expanded={aberta}
        onClick={() => setFixa((v) => !v)}
        onPointerEnter={(ev) => ev.pointerType === "mouse" && setPassando(true)}
        onPointerLeave={() => setPassando(false)}
        onFocus={(ev) => foiPeloTeclado(ev.currentTarget) && setPassando(true)}
        onBlur={() => setPassando(false)}
      >
        <Icone nome="info" tam={16} />
      </button>
      {aberta &&
        createPortal(
          <span
            ref={balao}
            id={id}
            role="tooltip"
            className="balao"
            style={{ top: posicao?.top ?? 0, left: posicao?.left ?? 0, visibility: posicao ? "visible" : "hidden" }}
          >
            {children}
          </span>,
          document.body,
        )}
    </>
  );
}
