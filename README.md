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

## fax_watcher.py（FAX 監視の常駐スクリプト）

1分ごとに受信トレイを確認し、PDF が添付された新着メール（FAX）を見つけたら次を行います。

1. PDF を `fax/YYYY-MM-DD/` に保存
2. LLM（OpenRouter）で全文を文字起こしし、同じ名前の `.md` に保存
3. 文字起こしを LLM で要約し、Slack の #FAX チャンネルに投稿

- 初めて起動したときは、その時点を起点にします（過去のメールは処理しません）。読み取り位置は `fax/state.json` に保存します。
- メールは既読にしません（読み取り専用で開きます）。
- 処理に失敗したメールは次の周回でやり直します。同じメールが3回続けて失敗したら、#FAX に失敗を知らせて次へ進みます。

```sh
cp .env.example .env   # OPENROUTER_API_KEY / SLACK_BOT_TOKEN / SLACK_CHANNEL_ID を記入
python3 fax_watcher.py --once   # 1回だけ確認
python3 fax_watcher.py          # 常駐（Ctrl+C で終了）
```

### Slack の準備（初回のみ）

1. https://api.slack.com/apps で「Create New App」→「From a manifest」を選び、次を貼り付けます。

   ```yaml
   display_information:
     name: FAX 通知
   features:
     bot_user:
       display_name: fax-bot
   oauth_config:
     scopes:
       bot: [chat:write]
   settings:
     org_deploy_enabled: false
     socket_mode_enabled: false
   ```

2. 「Install to Workspace」でインストールし、「OAuth & Permissions」の Bot User OAuth Token（`xoxb-…`）を `.env` の `SLACK_BOT_TOKEN` に設定します。
3. #FAX で `/invite @fax-bot` を実行します。チャンネル名を右クリック →「リンクをコピー」で得られる URL の末尾の `C…` を `SLACK_CHANNEL_ID` に設定します。

要約には患者名などが含まれることがあるため、#FAX はプライベートチャンネルにすることをおすすめします。

### launchd で常駐させる（macOS）

```sh
cp launchd/jp.clinic.fax-watcher.plist.example ~/Library/LaunchAgents/jp.clinic.fax-watcher.plist
# plist の /path/to/clinic-automation と python3 のパスを書き換える
mkdir -p fax
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/jp.clinic.fax-watcher.plist
launchctl print gui/$(id -u)/jp.clinic.fax-watcher | grep state   # 動作確認
tail -f fax/watcher.log                                           # ログ
launchctl bootout gui/$(id -u)/jp.clinic.fax-watcher              # 停止
```

## 注意

`info.txt`・`.env`・`mail/`・`fax/`・PDF・メールファイルは認証情報や患者情報を含むため `.gitignore` で除外しています。
