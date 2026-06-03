#!/usr/bin/env python3
"""
Daily Global News Digest — GitHub Pages 版 CLI 入口。

用法:
    python main.py --html              # 生成 Markdown + HTML（GitHub Pages 用）
    python main.py                     # 仅生成 Markdown
    python main.py --category Technology Politics  # 仅指定分类
"""

import argparse
import io
import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime

# 修复 Windows 控制台 emoji 编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 将项目根目录加入 sys.path，确保 src 模块可导入
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from src.config import Config, ConfigError
from src.pipeline import Pipeline


def setup_logging(log_dir: str = "logs") -> logging.Logger:
    """配置双通道日志：文件（轮转）+ 控制台。"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("news_digest")
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 文件 handler：5MB 轮转，保留 5 个备份
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "digest.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # 控制台 handler：INFO 以上
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s: %(message)s"
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def main():
    parser = argparse.ArgumentParser(
        description="📰 Daily Global News Digest — GitHub Pages 版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --html       # 生成 Markdown + HTML 网页
  python main.py              # 仅生成 Markdown
  python main.py --category Technology --html  # 仅科技类 + HTML
        """,
    )
    parser.add_argument(
        "--config", default="config.json",
        help="config.json 配置文件路径 (默认: config.json)"
    )
    parser.add_argument(
        "--env", default=".env",
        help=".env 环境变量文件路径 (默认: .env)"
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="覆盖配置中的输出目录"
    )
    parser.add_argument(
        "--category", nargs="*", choices=["Technology", "Politics", "Economy", "Travel"],
        help="仅处理指定的新闻分类（默认: 全部分类）"
    )
    parser.add_argument(
        "--html", action="store_true",
        help="生成 HTML 网页文件（GitHub Pages 部署用）"
    )
    args = parser.parse_args()

    # ── 设置日志 ──
    logger = setup_logging()

    # ── 加载配置 ──
    print("📰 Daily Global News Digest — GitHub Pages")
    print("=" * 60)

    try:
        config = Config.from_files(args.config, args.env)
    except ConfigError as e:
        logger.error(f"配置错误: {e}")
        print(f"\n❌ 配置错误:\n{e}")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        print(f"\n❌ 文件未找到: {e}")
        print("请确保 config.json 和 .env 文件存在于项目目录中。")
        print("复制 .env.example 为 .env 并填入你的 API Key。")
        sys.exit(1)

    # 覆盖配置
    if args.output_dir:
        config.output_dir = args.output_dir

    # ── 运行流水线 ──
    try:
        pipeline = Pipeline(config)
        output_path = pipeline.run(
            categories=args.category or None,
            send_email=False,  # GitHub Pages 模式不发邮件
            output_html=args.html,
        )
        print(f"\n✅ 日报已生成: {output_path}")
    except RuntimeError as e:
        logger.error(f"运行失败: {e}")
        print(f"\n❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"未预期的错误: {e}")
        print(f"\n❌ 发生未预期的错误: {e}")
        print("详情请查看 logs/digest.log")
        sys.exit(1)


if __name__ == "__main__":
    main()
