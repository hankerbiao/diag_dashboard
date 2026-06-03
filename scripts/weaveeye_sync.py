#!/usr/bin/env python3
"""
WeaveEye 数据同步统一入口（独立于 FastAPI 服务）

将 SIMS 测试数据（sync_data.py）与 MES 维修数据（sync_mes.py）串行执行，
适合 crontab / 任务平台定期调用。

示例:
    python scripts/weaveeye_sync.py run
    python scripts/weaveeye_sync.py run -c scripts/sync_config.yaml
    python scripts/weaveeye_sync.py sims --hours 48 --factory kunshan
    python scripts/weaveeye_sync.py mes --sync-recent 7
    python scripts/weaveeye_sync.py run --dry-run

环境变量（会注入子进程）:
    MONGODB_URI, MONGODB_DB / MONGODB_DB_NAME
    SYNC_LOG_LEVEL, SYNC_LOG_DIR, SYNC_LOG_JSON
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG = SCRIPT_DIR / "sync_config.yaml"
DEFAULT_FACTORIES = REPO_ROOT / "diag_backend" / "configs" / "factories.yaml"


@dataclass
class SyncPlan:
    run_sims: bool = True
    run_mes: bool = True
    sims_hours: int = 24
    sims_factories: list[str] | None = None
    sims_dry_run: bool = False
    mes_sync_recent: int = 1
    factories_yaml: Path = DEFAULT_FACTORIES
    mongodb_uri: str = ""
    mongodb_db: str = ""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        print("需要 PyYAML: pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    if not path.is_file():
        print(f"配置文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _resolve_mongo(cfg: dict[str, Any]) -> tuple[str, str]:
    mongo = cfg.get("mongodb") or {}
    uri = (
        os.environ.get("MONGODB_URI")
        or mongo.get("uri")
        or "mongodb://localhost:27017"
    )
    db = (
        os.environ.get("MONGODB_DB_NAME")
        or os.environ.get("MONGODB_DB")
        or mongo.get("db_name")
        or "diag_analysis"
    )
    return str(uri), str(db)


def plan_from_config(config_path: Path) -> SyncPlan:
    cfg = _load_yaml(config_path)
    sims = cfg.get("sims") or {}
    mes = cfg.get("mes") or {}
    factories_path = cfg.get("factories_yaml") or "diag_backend/configs/factories.yaml"
    fp = Path(factories_path)
    if not fp.is_absolute():
        fp = REPO_ROOT / fp
    uri, db = _resolve_mongo(cfg)
    factories = sims.get("factories")
    return SyncPlan(
        run_sims=bool(sims.get("enabled", True)),
        run_mes=bool(mes.get("enabled", True)),
        sims_hours=int(sims.get("hours", 24)),
        sims_factories=list(factories) if factories else None,
        sims_dry_run=bool(sims.get("dry_run", False)),
        mes_sync_recent=int(mes.get("sync_recent_days", 1)),
        factories_yaml=fp,
        mongodb_uri=uri,
        mongodb_db=db,
    )


def _child_env(plan: SyncPlan) -> dict[str, str]:
    env = os.environ.copy()
    env["MONGODB_URI"] = plan.mongodb_uri
    env["MONGODB_DB"] = plan.mongodb_db
    env["MONGODB_DB_NAME"] = plan.mongodb_db
    return env


def _run(cmd: list[str], *, env: dict[str, str], label: str) -> int:
    print(f"\n{'=' * 60}\n▶ {label}\n  {' '.join(cmd)}\n{'=' * 60}")
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    elapsed = time.time() - started
    status = "OK" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
    print(f"◀ {label}: {status} ({elapsed:.1f}s)")
    return proc.returncode


def run_sims(plan: SyncPlan) -> int:
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "sync_data.py"),
        "--hours",
        str(plan.sims_hours),
        "--config",
        str(plan.factories_yaml),
        "--mongodb-uri",
        plan.mongodb_uri,
        "--mongodb-db",
        plan.mongodb_db,
    ]
    if plan.sims_factories:
        if len(plan.sims_factories) == 1:
            cmd.extend(["--factory", plan.sims_factories[0]])
        else:
            for fid in plan.sims_factories:
                code = run_sims(
                    SyncPlan(
                        run_sims=True,
                        run_mes=False,
                        sims_hours=plan.sims_hours,
                        sims_factories=[fid],
                        sims_dry_run=plan.sims_dry_run,
                        factories_yaml=plan.factories_yaml,
                        mongodb_uri=plan.mongodb_uri,
                        mongodb_db=plan.mongodb_db,
                    )
                )
                if code != 0:
                    return code
            return 0
    if plan.sims_dry_run:
        cmd.append("--dry-run")
    return _run(cmd, env=_child_env(plan), label="SIMS 测试数据同步")


def run_mes(plan: SyncPlan) -> int:
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "sync_mes.py"),
        "--sync-recent",
        str(plan.mes_sync_recent),
    ]
    return _run(cmd, env=_child_env(plan), label="MES 维修数据同步")


def execute_plan(plan: SyncPlan) -> int:
    print(
        f"WeaveEye 同步计划: SIMS={'开' if plan.run_sims else '关'}, "
        f"MES={'开' if plan.run_mes else '关'}"
    )
    print(f"  MongoDB: {plan.mongodb_uri} / {plan.mongodb_db}")
    exit_code = 0
    if plan.run_sims:
        code = run_sims(plan)
        if code != 0:
            exit_code = code
    if plan.run_mes:
        code = run_mes(plan)
        if code != 0:
            exit_code = code
    print(f"\n{'=' * 60}\nWeaveEye 同步结束，退出码 {exit_code}\n{'=' * 60}")
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="WeaveEye 独立数据同步（SIMS + MES）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="按配置文件执行（默认 SIMS + MES）")
    run_p.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"YAML 配置路径（默认 {DEFAULT_CONFIG.relative_to(REPO_ROOT)})",
    )
    run_p.add_argument("--dry-run", action="store_true", help="仅 SIMS 试运行，不写库")

    sims_p = sub.add_parser("sims", help="仅执行 SIMS（sync_data.py）")
    sims_p.add_argument("--hours", type=int, default=24)
    sims_p.add_argument("--factory", action="append", dest="factories")
    sims_p.add_argument("--dry-run", action="store_true")
    sims_p.add_argument("--config", type=Path, default=DEFAULT_FACTORIES, help="factories.yaml")

    mes_p = sub.add_parser("mes", help="仅执行 MES 维修同步（sync_mes.py）")
    mes_p.add_argument("--sync-recent", type=int, default=1, metavar="N")

    p.add_argument("--mongodb-uri", default=os.environ.get("MONGODB_URI", ""))
    p.add_argument("--mongodb-db", default=os.environ.get("MONGODB_DB_NAME", ""))
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "run"

    if command == "run":
        config_path = args.config
        if not config_path.is_file():
            fallback = SCRIPT_DIR / "sync_config.example.yaml"
            if fallback.is_file():
                print(f"未找到 {config_path}，使用示例配置 {fallback}")
                config_path = fallback
            else:
                print(f"请创建配置文件: cp scripts/sync_config.example.yaml scripts/sync_config.yaml")
                sys.exit(1)
        plan = plan_from_config(config_path)
        if getattr(args, "dry_run", False):
            plan.sims_dry_run = True
    elif command == "sims":
        uri = args.mongodb_uri or "mongodb://localhost:27017"
        db = args.mongodb_db or "diag_analysis"
        fp = args.config
        if not fp.is_absolute():
            fp = REPO_ROOT / fp
        plan = SyncPlan(
            run_sims=True,
            run_mes=False,
            sims_hours=args.hours,
            sims_factories=args.factories,
            sims_dry_run=args.dry_run,
            factories_yaml=fp,
            mongodb_uri=uri,
            mongodb_db=db,
        )
    elif command == "mes":
        uri = args.mongodb_uri or "mongodb://localhost:27017"
        db = args.mongodb_db or "diag_analysis"
        plan = SyncPlan(
            run_sims=False,
            run_mes=True,
            mes_sync_recent=args.sync_recent,
            mongodb_uri=uri,
            mongodb_db=db,
        )
    else:
        parser.print_help()
        sys.exit(1)

    if args.mongodb_uri:
        plan.mongodb_uri = args.mongodb_uri
    if args.mongodb_db:
        plan.mongodb_db = args.mongodb_db

    sys.exit(execute_plan(plan))


if __name__ == "__main__":
    main()
