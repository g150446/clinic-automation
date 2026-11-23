# clinic-automation

クリニック業務の自動化用スクリプト集。

## fetch_lolipop_mail.py

ロリポップの IMAP 受信トレイから、指定日（日本時間）に受信したメールまたは添付 PDF を保存します。

```sh
python3 fetch_lolipop_mail.py 2026-11-20            # ./mail/2026-11-20/*.eml
python3 fetch_lolipop_mail.py 2026-11-20 --pdf-only # ./mail/2026-11-20/pdf/*.pdf
```

認証情報はスクリプトと同じ場所の `info.txt`（`--credentials` で変更可）から読み込みます。
`info.txt.example` をコピーして作成してください（1行目: メールアドレス、2行目: パスワード）。

## read_pdf_with_gemini.py

OpenRouter 経由のモデルで PDF を全文文字起こしし、標準出力に出力します。

```sh
export OPENROUTER_API_KEY=...
python3 read_pdf_with_gemini.py path/to/file.pdf [--model MODEL_ID]
```

## 注意

`info.txt`・`mail/`・PDF・メールファイルは認証情報や患者情報を含むため `.gitignore` で除外しています。
