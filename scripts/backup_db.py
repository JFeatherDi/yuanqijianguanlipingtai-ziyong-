#!/usr/bin/env python3
"""数据库在线备份：SQLite .backup API + 滚动保留 N 份。

为什么不用 cp 直接拷文件：运行中的库启用了 WAL，直接复制可能拿到
主库与 WAL 不一致的瞬间，恢复时丢最近几笔写入。sqlite3 的 .backup
API 会在同一把读锁内完成整库快照，保证备份文件自洽可恢复。

用法：
    python3 scripts/backup_db.py                # 默认保留最近 14 份
    python3 scripts/backup_db.py --keep 30      # 自定义保留份数
    python3 scripts/backup_db.py --out /mnt/nas # 备份到其他目录

crontab 示例（每天 03:30 自动备份，路径按实际仓库位置修改）：
    30 3 * * * cd /opt/components && python3 scripts/backup_db.py >> deploy.log 2>&1

恢复方法（服务停止后执行）：
    cp backend/backups/components-YYYYMMDD-HHMMSS.db backend/data.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from config import Config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite 在线备份")
    parser.add_argument("--keep", type=int, default=14, help="保留最近几份")
    parser.add_argument(
        "--out",
        type=str,
        default=str(PROJECT_DIR / "backend" / "backups"),
        help="备份输出目录",
    )
    args = parser.parse_args()

    source = Path(Config.DB_PATH)
    if not source.exists():
        print(f"备份失败：数据库不存在 {source}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"components-{time.strftime('%Y%m%d-%H%M%S')}.db"

    src_conn = sqlite3.connect(str(source))
    dst_conn = sqlite3.connect(str(target))
    try:
        # pages=-1 表示一次性复制整库；备份期间持有读锁，写入方最多等一小会儿
        src_conn.backup(dst_conn, pages=-1)
    finally:
        dst_conn.close()
        src_conn.close()

    size_kb = target.stat().st_size / 1024
    print(f"备份完成: {target} ({size_kb:.0f} KB)")

    # 快照校验：能通过 integrity check 的备份才算成功
    check = sqlite3.connect(str(target))
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        print(f"警告：备份完整性校验未通过 ({result})", file=sys.stderr)
        return 2

    # 滚动删除超出保留份数的旧备份
    backups = sorted(out_dir.glob("components-*.db"))
    for stale in backups[: max(len(backups) - args.keep, 0)]:
        stale.unlink()
        print(f"清理旧备份: {stale.name}")
    print(f"当前保留 {min(len(backups), args.keep)} 份备份")
    return 0


if __name__ == "__main__":
    sys.exit(main())
