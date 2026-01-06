"""Command line workflow for importing data into LightRAG with resume support."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from epip.config import LightRAGConfig
from epip.core.kg_builder import InsertResult, KGBuilder

PROGRESS_FILE = Path("data/lightrag/.import_progress.json")

# 全局中断标志
_interrupted = False


def _signal_handler(signum, frame):
    """处理 Ctrl+C 信号。"""
    global _interrupted
    if _interrupted:
        print("\n\n强制退出...")
        sys.exit(1)
    _interrupted = True
    print("\n\n收到中断信号，将在当前文件处理完成后安全退出...")
    print("再次按 Ctrl+C 强制退出\n")


def _collect_files(path: Path, pattern: str, recursive: bool = False) -> list[Path]:
    if not path.exists():
        return []
    if recursive:
        return sorted(path.rglob(pattern))
    return sorted(path.glob(pattern))


def _load_progress() -> dict:
    """加载导入进度。"""
    default = {"completed": [], "failed": {}, "last_update": None, "stats": {}}
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
            # 兼容旧格式
            if isinstance(data.get("failed"), list):
                data["failed"] = {f: "unknown error" for f in data["failed"]}
            return data
        except json.JSONDecodeError:
            return default
    return default


def _save_progress(progress: dict) -> None:
    """保存导入进度。"""
    progress["last_update"] = datetime.now().isoformat()
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2, ensure_ascii=False))


def _classify_error(error: Exception) -> tuple[str, str]:
    """分类错误，返回 (错误类型, 简短描述)。"""
    error_str = str(error)
    error_type = type(error).__name__

    if "timeout" in error_str.lower() or "Timeout" in error_type:
        return "timeout", "LLM 处理超时"
    if "connection" in error_str.lower():
        return "connection", "连接错误"
    if "JSONDecode" in error_type or "json" in error_str.lower():
        return "json_error", "JSON 解析错误"
    if "memory" in error_str.lower():
        return "memory", "内存不足"
    return "unknown", error_str[:100]


def _print_progress_bar(current: int, total: int, width: int = 40) -> str:
    """生成进度条。"""
    if total == 0:
        return "[" + "=" * width + "] 100%"
    percent = current / total
    filled = int(width * percent)
    bar = "=" * filled + "-" * (width - filled)
    return f"[{bar}] {percent * 100:.1f}%"


async def process_single_file(
    builder: KGBuilder,
    file_path: Path,
    file_type: str,
    progress: dict,
    timeout: int = 600,
    max_retries: int = 5,
) -> tuple[bool, str]:
    """
    处理单个文件。

    Returns:
        (success: bool, message: str)
    """
    file_key = str(file_path)

    if file_key in progress["completed"]:
        return True, "skipped (already completed)"

    retryable_types = {"timeout", "connection", "json_error"}
    last_error_type: str | None = None
    last_error_msg: str | None = None

    for attempt in range(max_retries):
        try:
            # 使用 asyncio.wait_for 添加额外的超时保护
            if file_type == "parquet":
                result = await asyncio.wait_for(
                    builder.insert_from_parquet([file_path]),
                    timeout=timeout,
                )
            elif file_type == "pdf":
                result = await asyncio.wait_for(
                    builder.insert_from_pdf([file_path]),
                    timeout=timeout,
                )
            else:
                return False, f"unknown file type: {file_type}"

            # 检查结果
            if result.errors:
                # 有错误但部分成功
                error_summary = f"{len(result.errors)} errors, {result.entity_count} entities"
                progress["completed"].append(file_key)
                _save_progress(progress)
                return True, f"partial success: {error_summary}"
            else:
                progress["completed"].append(file_key)
                _save_progress(progress)
                return True, f"OK: {result.entity_count} entities, {result.relation_count} relations"

        except asyncio.CancelledError:
            # 被取消，不记录为失败
            return False, "cancelled"
        except asyncio.TimeoutError:
            last_error_type, last_error_msg = "timeout", f"处理超时 ({timeout}s)"
        except Exception as e:
            last_error_type, last_error_msg = _classify_error(e)

        is_retryable = last_error_type in retryable_types
        is_last_attempt = attempt == max_retries - 1

        if is_retryable and not is_last_attempt:
            delay = min(2 ** attempt * 5, 60)
            print(
                f"[retry] {file_path.name}: {last_error_type} "
                f"(attempt {attempt + 1}/{max_retries}) - retrying in {delay}s"
            )
            await asyncio.sleep(delay)
            continue
        break

    error_type = last_error_type or "unknown"
    error_msg = last_error_msg or "unknown error"
    progress["failed"][file_key] = {"type": error_type, "msg": error_msg}
    _save_progress(progress)
    return False, f"{error_type}: {error_msg}"


async def main() -> None:
    global _interrupted

    # 注册信号处理
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    parser = argparse.ArgumentParser(description="Import data into LightRAG (resume-capable)")
    parser.add_argument("--reset", action="store_true", help="重置进度，从头开始")
    parser.add_argument("--dry-run", action="store_true", help="仅显示待处理文件，不实际导入")
    parser.add_argument("--skip-parquet", action="store_true", help="跳过 Parquet 文件")
    parser.add_argument("--skip-pdf", action="store_true", help="跳过 PDF 文件")
    parser.add_argument("--retry-failed", action="store_true", help="重试之前失败的文件")
    parser.add_argument("--retry-timeout", action="store_true", help="仅重试超时的文件")
    parser.add_argument("--cooldown", type=int, default=3, help="文件间隔秒数 (default: 3)")
    parser.add_argument("--timeout", type=int, default=600, help="单文件超时秒数 (default: 600)")
    parser.add_argument("--max-retries", type=int, default=5, help="单文件最大重试次数 (default: 5)")
    parser.add_argument("--status", action="store_true", help="仅显示当前进度状态")
    args = parser.parse_args()

    print("=" * 60)
    print("EPIP LightRAG Data Import (Resume Mode)")
    print("=" * 60)

    # 加载进度
    progress = _load_progress()

    # 仅显示状态
    if args.status:
        print(f"  Last update: {progress.get('last_update', 'Never')}")
        print(f"  Completed: {len(progress['completed'])} files")
        print(f"  Failed: {len(progress['failed'])} files")
        if progress["failed"]:
            print("\n  Failed files:")
            for f, info in list(progress["failed"].items())[:10]:
                if isinstance(info, dict):
                    print(f"    - [{info['type']}] {Path(f).name}")
                else:
                    print(f"    - {Path(f).name}")
            if len(progress["failed"]) > 10:
                print(f"    ... and {len(progress['failed']) - 10} more")
        return

    # 重置进度
    if args.reset:
        progress = {"completed": [], "failed": {}, "last_update": None, "stats": {}}
        _save_progress(progress)
        print("  Progress reset.")
    else:
        if progress["last_update"]:
            print(f"  Resuming from: {progress['last_update']}")
            print(f"  Completed: {len(progress['completed'])} files")
            print(f"  Failed: {len(progress['failed'])} files")

    # 重试失败的文件
    if args.retry_failed:
        retry_count = len(progress["failed"])
        progress["failed"] = {}
        _save_progress(progress)
        print(f"  Cleared {retry_count} failed entries for retry")
    elif args.retry_timeout:
        # 仅重试超时的文件
        timeout_files = [f for f, info in progress["failed"].items()
                        if isinstance(info, dict) and info.get("type") == "timeout"]
        for f in timeout_files:
            del progress["failed"][f]
        _save_progress(progress)
        print(f"  Cleared {len(timeout_files)} timeout entries for retry")

    config = LightRAGConfig()
    print(f"  LLM: {config.llm_backend}/{config.llm_model}")
    print(f"  Timeout: {args.timeout}s per file")
    print(f"  Max retries: {args.max_retries}")
    print(f"  Cooldown: {args.cooldown}s between files")
    print("=" * 60)

    if args.dry_run:
        print("\n*** DRY RUN MODE - No actual imports ***\n")
        builder = None
    else:
        builder = KGBuilder(config=config)

    stats = {"total": 0, "skipped": 0, "processed": 0, "failed": 0}

    # 收集所有文件
    all_files: list[tuple[Path, str]] = []

    if not args.skip_parquet:
        parquet_dir = Path("data/processed")
        parquet_files = _collect_files(parquet_dir, "*.parquet")
        all_files.extend((f, "parquet") for f in parquet_files)

    if not args.skip_pdf:
        pdf_dir = Path("dataset")
        pdf_files = _collect_files(pdf_dir, "*.pdf", recursive=True)
        all_files.extend((f, "pdf") for f in pdf_files)

    total_files = len(all_files)
    pending_files = [(f, t) for f, t in all_files if str(f) not in progress["completed"]]

    print(f"\n  Total files: {total_files}")
    print(f"  Already completed: {total_files - len(pending_files)}")
    print(f"  Pending: {len(pending_files)}")
    print(f"  {_print_progress_bar(total_files - len(pending_files), total_files)}")

    if args.dry_run:
        print("\n  Pending files:")
        for f, t in pending_files[:20]:
            print(f"    [{t}] {f.name}")
        if len(pending_files) > 20:
            print(f"    ... and {len(pending_files) - 20} more")
        return

    if not pending_files:
        print("\n  All files already processed!")
        return

    print("\n" + "-" * 60)

    # 处理文件
    for i, (file_path, file_type) in enumerate(pending_files, 1):
        if _interrupted:
            print("\n中断：安全退出")
            break

        stats["total"] += 1
        file_key = str(file_path)

        # 跳过之前失败的文件（除非 --retry-failed）
        if file_key in progress["failed"] and not args.retry_failed:
            print(f"\n({i}/{len(pending_files)}) {file_path.name}")
            print(f"  [SKIP] Previously failed: {progress['failed'][file_key]}")
            stats["skipped"] += 1
            continue

        print(f"\n({i}/{len(pending_files)}) [{file_type.upper()}] {file_path.name}")
        print(f"  {_print_progress_bar(len(progress['completed']), total_files)}")

        success, message = await process_single_file(
            builder, file_path, file_type, progress, args.timeout, args.max_retries
        )

        if success:
            if "skipped" in message:
                stats["skipped"] += 1
                print(f"  [SKIP] {message}")
            else:
                stats["processed"] += 1
                print(f"  [OK] {message}")
        else:
            stats["failed"] += 1
            print(f"  [FAILED] {message}")

        # 冷却时间
        if i < len(pending_files) and not _interrupted:
            await asyncio.sleep(args.cooldown)

    # 最终统计
    print("\n" + "=" * 60)
    print("Import Summary")
    print("=" * 60)
    print(f"  Total files: {total_files}")
    print(f"  Completed (all time): {len(progress['completed'])}")
    print(f"  Failed (all time): {len(progress['failed'])}")
    print(f"  Processed this run: {stats['processed']}")
    print(f"  Failed this run: {stats['failed']}")
    print(f"  {_print_progress_bar(len(progress['completed']), total_files)}")

    if builder:
        try:
            kg_stats = await builder.get_statistics()
            print(f"\n  Knowledge Graph:")
            print(f"    Entities: {kg_stats.total_entities}")
            print(f"    Relations: {kg_stats.total_relations}")
        except Exception as e:
            print(f"\n  (Could not fetch KG stats: {e})")

    print("=" * 60)

    # 提示
    if progress["failed"]:
        timeout_count = sum(1 for info in progress["failed"].values()
                          if isinstance(info, dict) and info.get("type") == "timeout")
        if timeout_count > 0:
            print(f"\nTip: {timeout_count} files failed due to timeout.")
            print("     Run with --retry-timeout to retry them")
            print("     Or use --timeout 900 to increase timeout")
        else:
            print("\nTip: Run with --retry-failed to retry failed files")

    if _interrupted:
        print("\n已安全退出，下次运行将从中断处继续。")


if __name__ == "__main__":
    asyncio.run(main())
