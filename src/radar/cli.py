"""Linha de comando: ``python -m radar <comando>``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

from radar import __version__
from radar.alerts import render
from radar.alerts.telegram import discover_chats, notifier_from_env
from radar.audit import scrub_secrets
from radar.config import Config, load_config
from radar.heartbeat import check_heartbeat
from radar.pipeline import RunOptions, now_br, run_pipeline
from radar.pncp_client import PncpClient

log = logging.getLogger("radar")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            # com deslocamento (+00:00 no GitHub, -03:00 no seu PC): sem ambiguidade entre fusos
            "ts": datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds"),
            "nivel": record.levelname,
            "msg": record.getMessage(),
            **getattr(record, "ctx", {}),
        }
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # o httpx registra a URL completa; a do Telegram carrega o token do bot
    for nome in ("httpx", "httpcore"):
        logging.getLogger(nome).setLevel(logging.WARNING)


def load_dotenv(path: str | Path = ".env") -> None:
    """Carrega KEY=VALUE de um .env local sem sobrescrever o que já está no ambiente."""
    p = Path(path)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def _data(valor: str) -> date:
    return date.fromisoformat(valor)


def build_client(cfg: Config) -> PncpClient:
    i = cfg.ingestao
    return PncpClient(
        tamanho_pagina=i.tamanho_pagina,
        intervalo_minimo_s=i.intervalo_minimo_s,
        backoff_429_s=i.backoff_429_s,
        max_tentativas_5xx=i.max_tentativas_5xx,
        timeout_s=i.timeout_s,
        max_paginas_por_serie=i.max_paginas_por_serie,
    )


def _sem_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", "", texto)


def _secrets() -> list[str]:
    return [os.environ.get("TELEGRAM_BOT_TOKEN", "")]


def cmd_run(args: argparse.Namespace, modo: str) -> int:
    cfg = load_config(args.config)
    dias = getattr(args, "dias", None)
    opts = RunOptions(
        data_dir=Path(args.data_dir),
        modo=modo,
        trigger=args.trigger,
        dry_run=args.dry_run,
        send_alerts=(modo == "daily" and not args.no_alerts),
        desde=getattr(args, "desde", None),
        ate=getattr(args, "ate", None),
        bootstrap_dias=dias or 30,
        reconciliar_dias=dias if modo == "reconcile" else None,
        simulate_failure=getattr(args, "simulate_failure", False),
    )
    notifier = notifier_from_env() if opts.send_alerts and not opts.dry_run else None
    client = build_client(cfg)
    try:
        outcome = run_pipeline(cfg, opts, client=client, notifier=notifier, secrets=_secrets())
    finally:
        client.close()
    rec = outcome.record
    log.info(
        "resumo",
        extra={"ctx": {
            "status": rec.status, "lidas": rec.rows_read, "novas": rec.rows_new,
            "atualizadas": rec.rows_updated, "relevantes_novas": rec.rows_relevant_new,
            "lidas_atualizacao": rec.rows_atualizacao, "prazos_alterados": rec.prazos_alterados,
            "situacoes_alteradas": rec.situacoes_alteradas,
            "series_falhas": len(rec.series_failed), "chamadas_api": rec.api_calls,
            "http_429": rec.http_429, "alerta_enviado": rec.alert_sent,
        }},
    )  # fmt: skip
    if opts.dry_run:
        print(
            "\n"
            + "=" * 60
            + "\nPRÉVIA DO ALERTA (dry-run, nada foi gravado nem enviado)\n"
            + "=" * 60
        )
        for m in outcome.mensagens:
            print(_sem_html(m) + "\n" + "-" * 60)
        print("\nPor que cada edital ganhou essa nota (use para calibrar o config.yaml):")
        for it in outcome.itens:
            print(f"  [{it.result.score}] {it.row['id']}: {' | '.join(it.result.motivos)}")
    return 0


def cmd_check_config(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    i = cfg.ingestao
    print(f"config.yaml válido. Perfil: {cfg.perfil.nome}")
    print(f"  UFs: {', '.join(i.ufs)} | modalidades: {i.modalidades} | buscas por execução: "
          f"{len(i.ufs) * len(i.modalidades)}")  # fmt: skip
    return 0


def cmd_get_chat_id(_: argparse.Namespace) -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Defina TELEGRAM_BOT_TOKEN (no .env ou no ambiente) e mande uma mensagem ao seu bot.")
        return 2
    chats = discover_chats(token)
    if not chats:
        print("Nenhuma mensagem encontrada. Abra o bot no Telegram, envie 'oi' e rode de novo.")
        return 1
    for c in chats:
        print(f"chat_id={c['chat_id']} (tipo: {c['tipo']})")
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    res = check_heartbeat(args.data_dir, now_br(), args.max_horas)
    log.info(
        "heartbeat", extra={"ctx": {"ok": res.ok, "horas": res.horas, "ultimo_ok": res.ultimo_ok}}
    )
    if res.ok:
        return 0
    notifier = notifier_from_env()
    if notifier and not args.no_alerts:
        notifier.send(render.heartbeat_message(res.ultimo_ok, res.horas, args.max_horas))
    return 1


def cmd_notify_failure(args: argparse.Namespace) -> int:
    status_path = Path(args.data_dir) / "status.json"
    tipo = msg = ultimo_ok = None
    if status_path.exists():
        st = json.loads(status_path.read_text(encoding="utf-8"))
        ultima = st.get("ultima_execucao") or {}
        ultimo_ok = st.get("ultima_execucao_ok_em")
        if ultima.get("status") == "failed":
            tipo, msg = ultima.get("error_type"), ultima.get("error_message")
    if not tipo:
        tipo, msg = (
            "FalhaAntesDoRegistro",
            "A execução caiu antes de gravar o status (veja os logs).",
        )
    notifier = notifier_from_env()
    if notifier is None:
        print("Telegram não configurado: defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        return 2
    notifier.send(render.failure_message(args.run_url, tipo, msg, ultimo_ok))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="radar", description="Radar de Licitações PNCP")
    p.add_argument("--version", action="version", version=f"radar {__version__}")
    sub = p.add_subparsers(dest="comando", required=True)

    def comum(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--config", default="config.yaml")
        sp.add_argument("--data-dir", default="data")

    sp = sub.add_parser("run", help="execução diária: busca, grava, pontua e alerta")
    comum(sp)
    sp.add_argument("--dry-run", action="store_true", help="não grava nem envia; mostra a prévia")
    sp.add_argument("--no-alerts", action="store_true")
    sp.add_argument("--trigger", default="manual", help="schedule | workflow_dispatch | manual")
    sp.add_argument(
        "--simulate-failure", action="store_true", help="força uma falha (testa o alerta)"
    )

    sp = sub.add_parser("backfill", help="reprocessa uma janela de datas (sem alerta)")
    comum(sp)
    sp.add_argument("--desde", type=_data, required=True, metavar="AAAA-MM-DD")
    sp.add_argument("--ate", type=_data, required=True, metavar="AAAA-MM-DD")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-alerts", action="store_true", default=True)
    sp.add_argument("--trigger", default="manual")

    sp = sub.add_parser("bootstrap", help="carga inicial das propostas abertas (rode uma vez)")
    comum(sp)
    sp.add_argument("--dias", type=int, default=30, help="prazo máximo das propostas abertas")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-alerts", action="store_true", default=True)
    sp.add_argument("--trigger", default="manual")

    sp = sub.add_parser(
        "reconcile",
        help="conferência semanal: corrige, no PNCP, editais abertos que a listagem não confirma",
    )
    comum(sp)
    sp.add_argument(
        "--dias", type=int, default=None, help="prazo máximo das propostas (padrão: o do config)"
    )
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-alerts", action="store_true", default=True)
    sp.add_argument("--trigger", default="manual")

    sp = sub.add_parser("check-config", help="valida o config.yaml")
    sp.add_argument("--config", default="config.yaml")

    sub.add_parser("get-chat-id", help="descobre o chat_id do seu bot do Telegram")

    sp = sub.add_parser("heartbeat", help="alerta se o robô ficou muito tempo sem rodar")
    sp.add_argument("--data-dir", default="data")
    sp.add_argument("--max-horas", type=float, default=26)
    sp.add_argument("--no-alerts", action="store_true")

    sp = sub.add_parser("notify-failure", help="envia o alerta de falha (usado pelo workflow)")
    sp.add_argument("--data-dir", default="data")
    sp.add_argument("--run-url", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    setup_logging()
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        match args.comando:
            case "run":
                return cmd_run(args, "daily")
            case "backfill":
                return cmd_run(args, "backfill")
            case "bootstrap":
                return cmd_run(args, "bootstrap")
            case "reconcile":
                return cmd_run(args, "reconcile")
            case "check-config":
                return cmd_check_config(args)
            case "get-chat-id":
                return cmd_get_chat_id(args)
            case "heartbeat":
                return cmd_heartbeat(args)
            case "notify-failure":
                return cmd_notify_failure(args)
    except Exception as exc:  # um traceback cru poderia vazar detalhes de requisições
        log.error(
            "falha",
            extra={"ctx": {"erro": type(exc).__name__, "msg": scrub_secrets(str(exc), _secrets())}},
        )
        return 1
    return 0
