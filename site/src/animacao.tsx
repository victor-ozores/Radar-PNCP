/**
 * Movimento da página, todo num lugar só (biblioteca Motion).
 *
 * Regras: só aparece/sobe/cresce (nada piscando nem girando sem parar), tudo curto, e quem pediu "menos
 * movimento" no sistema não vê deslocamentos: sem pulo, sem contagem, a barra já vem cheia.
 * `LazyMotion` + `m.*` carregam só o necessário (a página não paga pelo recurso que não usa).
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { LazyMotion, MotionConfig, domAnimation, useReducedMotion, type Variants } from "motion/react";

export * as m from "motion/react-m";

export const SUAVE = [0.22, 1, 0.36, 1] as const; // sai rápido e pousa devagar

/** Sobe 14 px e aparece. Use com `initial="oculto"` e `animate`/`whileInView="visivel"`. */
export const subir: Variants = {
  oculto: { opacity: 0, y: 14 },
  visivel: { opacity: 1, y: 0, transition: { duration: 0.5, ease: SUAVE } },
};

/** Os filhos (com `variants={subir}`) entram um depois do outro. */
export const emSequencia: Variants = {
  oculto: {},
  visivel: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};

/** Só aparece e cresce um pouco (etiquetas dos filtros). */
export const surgir: Variants = {
  oculto: { opacity: 0, scale: 0.85 },
  visivel: { opacity: 1, scale: 1, transition: { duration: 0.2, ease: SUAVE } },
};

/** Quando a pessoa entra na tela vendo o item (rolagem), uma vez só. */
export const NA_TELA = { once: true, margin: "0px 0px -8% 0px" } as const;

export function Animacao({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}

/**
 * Um número que "conta" até o valor (curva suave, sem biblioteca: é só um laço de quadros).
 * Com "menos movimento" ele vai direto. Quem lê pela tela vê a contagem; leitor de tela lê o valor final.
 */
export function useContagem(alvo: number, duracaoMs = 1100): number {
  const reduzido = useReducedMotion();
  const [mostrado, setMostrado] = useState(reduzido ? alvo : 0);
  const anterior = useRef(reduzido ? alvo : 0);

  useEffect(() => {
    if (reduzido) {
      anterior.current = alvo;
      setMostrado(alvo);
      return;
    }
    const de = anterior.current;
    const duracao = de === 0 ? duracaoMs : 400;
    const inicio = performance.now();
    let quadro = 0;
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / duracao);
      const suave = 1 - Math.pow(1 - t, 4); // sai rápido e pousa devagar
      setMostrado(Math.round(de + (alvo - de) * suave));
      if (t < 1) {
        quadro = requestAnimationFrame(passo);
      } else {
        anterior.current = alvo;
      }
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [alvo, duracaoMs, reduzido]);

  return mostrado;
}

export { useReducedMotion };
