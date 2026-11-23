#!/usr/bin/env python3
"""ロリポップの受信トレイから指定日（日本時間）のメールや添付 PDF を保存する。"""

import argparse
from datetime import date, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
import imaplib
from pathlib import Path
import re
import ssl
import sys
from tempfile import NamedTemporaryFile


HOST = "imap.lolipop.jp"
PORT = 993
JST = timezone(timedelta(hours=9))
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
INTERNAL_DATE = re.compile(rb'\bINTERNALDATE "([^"]+)"')


def read_credentials(path):
    with path.open(encoding="utf-8-sig") as file:
        address = file.readline().strip()
        password = file.readline().rstrip("\r\n")
    if not address or not password:
        raise ValueError("認証ファイルには1行目にメールアドレス、2行目にパスワードが必要です。")
    return address, password


def imap_date(day):
    return f"{day.day:02d}-{MONTHS[day.month - 1]}-{day.year:04d}"


def imap_data(response, error):
    status, data = response
    if status != "OK" or not data or data[0] is None:
        raise ValueError(error)
    return data


def save_file(path, content):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary_path = Path(file.name)
        try:
            file.write(content)
            file.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def pdf_filename(filename):
    basename = re.split(r"[/\\]", filename)[-1]
    if basename.lower().endswith(".pdf"):
        basename = basename[:-4]
    basename = re.sub(r'[\x00-\x1f\x7f:]', "_", basename).strip(" .")
    # 識別子を付けてもファイル名が長くなりすぎないようにする。
    basename = basename.encode("utf-8", errors="replace")[:180].decode("utf-8", errors="ignore")
    return f"{basename or 'attachment'}.pdf"


def save_pdfs(output, message_id, message):
    count = 0
    email = BytesParser(policy=policy.default).parsebytes(message)
    for part_number, part in enumerate(email.walk(), start=1):
        if part.is_multipart():
            continue
        filename = part.get_filename() or ""
        if part.get_content_type() != "application/pdf" and not filename.lower().endswith(".pdf"):
            continue
        content = part.get_payload(decode=True)
        if not content:
            raise ValueError(f"メール {message_id} の添付 {part_number} を読み取れませんでした。")
        save_file(output / f"{message_id}-{part_number}-{pdf_filename(filename)}", content)
        count += 1
    return count


def fetch_messages(client, day, output, since, before, pdf_only=False):
    imap_data(client.select("INBOX", readonly=True), "受信トレイを開けませんでした。")
    _, uid_validity = client.response("UIDVALIDITY")
    if not uid_validity or not uid_validity[0] or not uid_validity[0].isdigit():
        raise ValueError("受信トレイの UIDVALIDITY を取得できませんでした。")
    mailbox_id = uid_validity[0].decode("ascii")

    # IMAP 検索はタイムゾーンを無視するため、広めに検索してから日本時間で絞る。
    rows = imap_data(
        client.uid("SEARCH", None, "SINCE", since, "BEFORE", before),
        "対象日のメールを検索できませんでした。",
    )
    message_count = 0
    pdf_count = 0
    for uid in rows[0].split():
        if not uid.isdigit():
            raise ValueError("メールの UID が不正です。")
        metadata = imap_data(
            client.uid("FETCH", uid, "(INTERNALDATE)"),
            "メールの受信日時を取得できませんでした。",
        )
        match = INTERNAL_DATE.search(metadata[0])
        if match is None:
            raise ValueError("メールの受信日時を読み取れませんでした。")
        received = parsedate_to_datetime(match[1].decode("ascii").replace("-", " ", 2))
        if received.tzinfo is None:
            raise ValueError("メールの受信日時にタイムゾーンがありません。")
        if received.astimezone(JST).date() != day:
            continue

        parts = imap_data(
            client.uid("FETCH", uid, "(BODY.PEEK[])"),
            "メールの本文を取得できませんでした。",
        )
        message = next((part[1] for part in parts if isinstance(part, tuple)), None)
        if message is None:
            raise ValueError("メールの本文がサーバーから返りませんでした。")
        message_id = f"{mailbox_id}-{uid.decode('ascii')}"
        if pdf_only:
            pdf_count += save_pdfs(output, message_id, message)
        else:
            save_file(output / f"{message_id}.eml", message)
        message_count += 1
    return message_count, pdf_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", metavar="YYYY-MM-DD", help="受信日（日本時間）")
    parser.add_argument(
        "--credentials", type=Path,
        default=Path(__file__).resolve().with_name("info.txt"),
        help="認証ファイル（既定値はスクリプトと同じ場所の info.txt）",
    )
    parser.add_argument("--pdf-only", action="store_true", help="添付 PDF のみ保存する")
    parser.add_argument("--output", type=Path, help="保存先（既定値は ./mail/YYYY-MM-DD、PDF の場合はその中の pdf）")
    args = parser.parse_args()
    try:
        day = date.fromisoformat(args.date)
        if day.isoformat() != args.date:
            raise ValueError
        since = imap_date(day - timedelta(days=2))
        before = imap_date(day + timedelta(days=2))
    except (ValueError, OverflowError):
        parser.error("日付は YYYY-MM-DD 形式で指定してください。")

    output = args.output
    if output is None:
        output = Path("mail") / day.isoformat()
        if args.pdf_only:
            output /= "pdf"
    try:
        address, password = read_credentials(args.credentials)
        with imaplib.IMAP4_SSL(HOST, PORT, ssl_context=ssl.create_default_context(),
                               timeout=30) as client:
            try:
                client.login(address, password)
            except imaplib.IMAP4.abort:
                raise
            except imaplib.IMAP4.error:
                raise ValueError("IMAP の認証に失敗しました。info.txt の内容を確認してください。") from None
            message_count, pdf_count = fetch_messages(client, day, output, since, before, args.pdf_only)
    except (imaplib.IMAP4.error, UnicodeError):
        print("IMAP の通信またはデータの読み取りに失敗しました。", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"取得エラー: {exc}", file=sys.stderr)
        return 1

    if args.pdf_only:
        print(f"{day} の対象メール {message_count} 件、保存した PDF {pdf_count} 件。保存先 {output}")
    elif message_count:
        print(f"{day} のメール {message_count} 件を {output} に保存しました。")
    else:
        print(f"{day} に受信したメールは 0 件です。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
