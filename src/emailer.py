"""
SMTP 邮件发送模块（可选）。
通过 SMTP 发送每日新闻摘要到指定邮箱，支持 Markdown + HTML 双格式。
"""

import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP, SMTP_SSL, SMTPException
from typing import Optional

from .config import SmtpConfig

logger = logging.getLogger("news_digest.emailer")


class EmailError(Exception):
    """邮件发送失败。"""
    pass


class Emailer:
    """SMTP 邮件发送器。

    使用标准库 smtplib 和 email.mime，零额外依赖。
    发送多部分邮件：纯文本 Markdown + 简单 HTML。
    """

    def __init__(self, config: SmtpConfig):
        self.config = config

    def send(
        self,
        subject: str,
        markdown_body: str,
    ) -> bool:
        """发送邮件。

        Args:
            subject: 邮件主题。
            markdown_body: Markdown 格式的邮件正文。

        Returns:
            True 表示发送成功。

        Raises:
            EmailError: 发送失败。
        """
        html_body = _markdown_to_html(markdown_body)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.user
        msg["To"] = ", ".join(self.config.to)

        # 纯文本部分（保留原始 Markdown）
        msg.attach(MIMEText(markdown_body, "plain", "utf-8"))
        # HTML 部分
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        smtp: Optional[SMTP] = None
        try:
            # 根据端口选择 SSL 或 STARTTLS
            if self.config.port == 465:
                smtp = SMTP_SSL(self.config.host, self.config.port, timeout=30)
            else:
                smtp = SMTP(self.config.host, self.config.port, timeout=30)
                smtp.ehlo()
                if self.config.port == 587:
                    smtp.starttls()
                    smtp.ehlo()

            smtp.login(self.config.user, self.config.password)
            smtp.sendmail(self.config.user, self.config.to, msg.as_string())

            logger.info(f"  邮件已发送至: {', '.join(self.config.to)}")
            return True

        except SMTPException as e:
            raise EmailError(f"SMTP 错误: {e}") from e
        finally:
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass

    def send_or_warn(
        self,
        subject: str,
        markdown_body: str,
    ) -> None:
        """发送邮件，失败时仅记录警告（不阻塞主流程）。"""
        try:
            self.send(subject, markdown_body)
        except EmailError as e:
            logger.warning(f"  邮件发送失败（不影响日报生成）: {e}")


def _markdown_to_html(md: str) -> str:
    """将 Markdown 转换为简单 HTML（用于邮件 HTML 正文）。

    这是一个极简转换器，仅处理标题、粗体、链接和段落。
    """
    lines = md.split("\n")
    html_lines = []
    in_paragraph = False

    for line in lines:
        # 标题
        if line.startswith("#### "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append(f"<h4>{_inline_html(line[5:])}</h4>")
        elif line.startswith("### "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append(f"<h3>{_inline_html(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append(f"<h2>{_inline_html(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append(f"<h1>{_inline_html(line[2:])}</h1>")
        elif line.startswith("---"):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append("<hr>")
        elif line.startswith("- ") or line.startswith("* "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append(f"<li>{_inline_html(line[2:])}</li>")
        elif line.startswith("> "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append(f"<blockquote>{_inline_html(line[2:])}</blockquote>")
        elif line.strip() == "":
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
        else:
            if not in_paragraph:
                html_lines.append("<p>")
                in_paragraph = True
            html_lines.append(_inline_html(line))
            html_lines.append("<br>")

    if in_paragraph:
        html_lines.append("</p>")

    body = "\n".join(html_lines)

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; line-height: 1.8; max-width: 720px; margin: 0 auto; padding: 20px; color: #333; }}
  h1 {{ color: #1a1a1a; border-bottom: 2px solid #4A90D9; padding-bottom: 8px; }}
  h2 {{ color: #2c3e50; margin-top: 32px; }}
  h3 {{ color: #34495e; }}
  a {{ color: #4A90D9; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  blockquote {{ border-left: 4px solid #4A90D9; padding-left: 16px; color: #666; margin-left: 0; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 24px 0; }}
  li {{ margin-bottom: 4px; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _inline_html(text: str) -> str:
    """处理行内的 Markdown 标记（粗体、斜体、链接）。"""
    # 链接 [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # 粗体 **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # 斜体 *text*（注意避免和粗体冲突）
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text
