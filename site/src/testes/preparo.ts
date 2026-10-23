/** Roda antes de todos os testes: deixa o movimento instantâneo e dá ao jsdom o que ele não tem. */
import { configure } from "@testing-library/dom";
import { MotionGlobalConfig } from "motion/react";

// animações terminam na hora: o teste não espera frame nem "sobe 14 px"
MotionGlobalConfig.skipAnimations = true;

// máquina lenta (o CI, ou o PC ocupado) não pode reprovar teste por um segundo a menos
configure({ asyncUtilTimeout: 4000 });

// jsdom não tem IntersectionObserver (usado por "aparecer ao rolar"): aqui tudo já está à vista
class SempreVisivel implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly scrollMargin = "";
  readonly thresholds = [0];

  constructor(private readonly aoVer: IntersectionObserverCallback) {}

  observe(alvo: Element): void {
    this.aoVer(
      [{ isIntersecting: true, intersectionRatio: 1, target: alvo } as IntersectionObserverEntry],
      this,
    );
  }

  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

if (typeof globalThis.IntersectionObserver === "undefined") {
  globalThis.IntersectionObserver = SempreVisivel;
}
