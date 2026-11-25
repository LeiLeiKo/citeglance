"""Client text. Chinese source labels are also the default locale."""

import re


INTERFACE_LANGUAGES = {"zh": "简体中文", "en": "English", "ja": "日本語"}

TEXT = {
    "CiteGlance · 文献雷达": ("CiteGlance", "CiteGlance · 論文レーダー"),
    "界面语言": ("Interface language", "表示言語"),
    "已载入本机论文库": ("Local library loaded", "ローカルの論文ライブラリを読み込みました"),
    "论文库": ("Library", "論文ライブラリ"),
    "检索频道": ("Search channel", "検索チャンネル"),
    "全部频道": ("All channels", "すべてのチャンネル"),
    "检索新论文": ("Find new papers", "新着論文を検索"),
    "检索历史": ("Search history", "検索履歴"),
    "收藏": ("Favorites", "お気に入り"),
    "论文": ("Papers", "論文"),
    "标题": ("Title", "タイトル"),
    "发表日期": ("Published", "公開日"),
    "频道": ("Channel", "チャンネル"),
    "收藏论文": ("Add to favorites", "お気に入りに追加"),
    "取消收藏": ("Remove favorite", "お気に入りから削除"),
    "打开来源": ("Open source", "掲載ページを開く"),
    "翻译摘要": ("Translate abstract", "要旨を翻訳"),
    "频道与屏蔽词": ("Channels & filters", "チャンネルと除外語"),
    "新增频道": ("New channel", "チャンネルを追加"),
    "还没有频道。填写频道名称和两组检索词，即可保存第一个频道。": (
        "No channels yet. Enter a name and two groups of search terms to save your first channel.",
        "チャンネルがありません。名前と2グループの検索語を入力し、最初のチャンネルを保存してください。",
    ),
    "删除所选频道": ("Delete selected channel", "選択したチャンネルを削除"),
    "每行一个词组。A、B 两组都需至少命中一项。": (
        "Enter one phrase per line. At least one phrase from each group must match.",
        "1行に1フレーズを入力します。A・B両グループで1件以上の一致が必要です。",
    ),
    "A 组 · 对象或场景": ("Group A · Object or context", "グループA · 対象や場面"),
    "B 组 · 现象、方法或技术": ("Group B · Phenomenon, method, or technology", "グループB · 現象、手法、技術"),
    "领域限定 · 可选，任一项命中": ("Scope · Optional, any match", "分野の絞り込み · 任意、いずれかに一致"),
    "仅此频道的屏蔽词": ("Channel exclusions", "このチャンネルの除外語"),
    "保存频道": ("Save channel", "チャンネルを保存"),
    "全局屏蔽词": ("Global exclusions", "全チャンネルの除外語"),
    "标题或摘要命中时，从所有频道排除。每行一个词组。": (
        "Exclude a paper from all channels if its title or abstract matches. One phrase per line.",
        "タイトルまたは要旨に含まれる論文をすべてのチャンネルから除外します。1行に1フレーズを入力します。",
    ),
    "保存全局屏蔽词": ("Save global exclusions", "全チャンネルの除外語を保存"),
    "API 与设置": ("API & settings", "APIと設定"),
    "定时检索": ("Schedule", "定期検索"),
    "启用定时检索": ("Enable scheduled searches", "定期検索を有効にする"),
    "客户端打开时，会按设定频率检索全部频道，结果存入检索历史。": (
        "While the client is open, it searches all channels at the chosen interval and saves the results in Search history.",
        "クライアントを開いている間、設定した間隔ですべてのチャンネルを検索し、結果を検索履歴に保存します。",
    ),
    "检索间隔": ("Search interval", "検索間隔"),
    "间隔单位": ("Interval unit", "間隔の単位"),
    "分钟": ("Minutes", "分"),
    "小时": ("Hours", "時間"),
    "天": ("Days", "日"),
    "保存定时设置": ("Save schedule", "スケジュールを保存"),
    "已保存定时检索设置": ("Search schedule saved", "定期検索の設定を保存しました"),
    "定时检索已暂停。": ("Scheduled searches are paused.", "定期検索は停止中です。"),
    "定时检索等待设置：{reason}": ("Scheduled search is waiting for setup ({reason})", "設定が必要なため定期検索を保留しています（{reason}）"),
    "正在自动检索全部频道。": ("Scheduled search is running for all channels.", "すべてのチャンネルを定期検索中です。"),
    "等待当前操作结束后自动检索。": ("Scheduled search is waiting for the current operation to finish.", "現在の処理が終わると定期検索を開始します。"),
    "已到检索时间，正在等待启动。": ("A scheduled search is due.", "定期検索の実行時刻になりました。"),
    "下一次检索 · {when}": ("Next search · {when}", "次回の検索 · {when}"),
    "上次检索启动 · {when}": ("Last search started · {when}", "前回の検索開始 · {when}"),
    "检索间隔需为 1–365 的整数。": (
        "Enter a whole number from 1 to 365 for the search interval.",
        "検索間隔は1〜365の整数で入力してください。",
    ),
    "无法保存定时设置": ("Could not save the schedule", "スケジュールを保存できませんでした"),
    "正在通过 {provider} 自动检索……": ("Running a scheduled search with {provider}…", "{provider}で定期検索を実行中…"),
    "自动检索 · {provider} · {count} 篇符合条件 · {requests} 次请求": (
        "Scheduled search · {provider} · Matches {count} · Requests {requests}",
        "定期検索 · {provider} · 条件に一致した論文{count}件 · リクエスト{requests}回",
    ),
    "自动检索未完成（{reason}）": ("Scheduled search incomplete ({reason})", "定期検索を完了できませんでした（{reason}）"),
    "云端部署": ("Cloud deployment", "クラウド展開"),
    "服务器连接": ("Server connection", "サーバー接続"),
    "服务器 IP 或域名": ("Server IP or hostname", "サーバーのIPまたはホスト名"),
    "SSH 用户": ("SSH user", "SSHユーザー"),
    "SSH 端口": ("SSH port", "SSHポート"),
    "SSH 私钥文件（可选）": ("SSH private key (optional)", "SSH秘密鍵（任意）"),
    "选择私钥": ("Browse for key", "秘密鍵を選択"),
    "选择 SSH 私钥文件": ("Select the SSH private key file", "SSH秘密鍵ファイルを選択"),
    "首次 SSH 连接": ("First SSH connection", "初回SSH接続"),
    "使用已安装 Docker Compose 的 Linux 服务器。首次连接时，请与服务器提供商的记录核对 SSH 指纹。": (
        "Use a Linux server with Docker Compose. On first connection, compare the SSH fingerprint with the one from your server provider.",
        "Docker Composeが入ったLinuxサーバーを使用します。初回接続時はSSH指紋をサーバー提供元の情報と照合してください。",
    ),
    "Telegram 私聊 ID": ("Telegram private chat ID", "Telegramの個別チャットID"),
    "Telegram 与检索": ("Telegram and search", "Telegramと検索"),
    "云端间隔（分钟）": ("Cloud interval (minutes)", "クラウド検索間隔（分）"),
    "云端请求上限／24 小时": ("Requests per 24 hours", "24時間のリクエスト上限"),
    "记住云端密钥（Windows 加密）": ("Remember cloud keys (Windows encryption)", "クラウド用キーを保存（Windowsで暗号化）"),
    "检索 Key 留空可用客户端已保存的 Semantic Scholar Key。首次部署前，先在 Telegram 给 Bot 发 /start。": (
        "Leave the search key blank to reuse the saved Semantic Scholar key. Before deployment, send /start to the bot in Telegram.",
        "検索用キー欄が空の場合は、保存済みのSemantic Scholarキーを使用します。展開前にTelegramでボットに/startを送ってください。",
    ),
    "检测服务器": ("Check server", "サーバーを確認"),
    "部署或更新": ("Deploy or update", "展開・更新"),
    "查看云端状态": ("View status", "稼働状況を表示"),
    "查看云端日志": ("View logs", "ログを表示"),
    "获取私聊 ID": ("Get chat ID", "チャットIDを取得"),
    "已填写 Telegram 私聊 ID。": ("Telegram private chat ID filled in.", "Telegramの個別チャットIDを入力しました。"),
    "无法打开 SSH": ("Could not open SSH", "SSHを開けませんでした"),
    "无法获取私聊 ID": ("Could not get the chat ID", "チャットIDを取得できませんでした"),
    "正在读取 Telegram 私聊 ID……": ("Reading the Telegram chat ID…", "TelegramのチャットIDを取得中…"),
    "无法执行云端操作": ("Could not run the cloud operation", "クラウド操作を実行できませんでした"),
    "正在连接服务器，请稍候……": ("Connecting to the server…", "サーバーに接続中です…"),
    "已提交云端部署。请在 Telegram 发送 /status 验证。": (
        "Deployment submitted. Send /status in Telegram to verify.", "展開を実行しました。Telegramで/statusを送信して確認してください。",
    ),
    "云端操作已完成。": ("Cloud operation completed.", "クラウド操作が完了しました。"),
    "云端操作失败，请查看日志。": ("The cloud operation failed. Check the logs.", "クラウド操作に失敗しました。ログを確認してください。"),
    "请输入有效的服务器 IP 或域名。": ("Enter a valid server IP or hostname.", "有効なサーバーのIPアドレスまたはホスト名を入力してください。"),
    "请输入有效的 SSH 用户名。": ("Enter a valid SSH username.", "有効なSSHユーザー名を入力してください。"),
    "SSH 端口需为 1–65535 的整数。": ("Enter an SSH port from 1 to 65535.", "SSHポートは1〜65535で入力してください。"),
    "找不到指定的 SSH 私钥文件。": ("The SSH private key file was not found.", "指定されたSSH秘密鍵ファイルが見つかりません。"),
    "找不到 OpenSSH 客户端。请启用 Windows 的 OpenSSH Client。": (
        "OpenSSH was not found. Enable the OpenSSH Client optional feature in Windows.",
        "OpenSSHが見つかりません。WindowsのOpenSSH Clientオプション機能を有効にしてください。",
    ),
    "请在终端运行 SSH，确认服务器指纹并完成首次连接。": (
        "Open SSH in your terminal, check the server fingerprint, and connect once.",
        "ターミナルからSSHを起動し、サーバーの指紋を確認して初回接続してください。",
    ),
    "请填写有效的 Telegram Bot Token。": ("Enter a valid Telegram bot token.", "有効なTelegramボットトークンを入力してください。"),
    "请填写 Semantic Scholar API Key，或先在客户端保存该密钥。": (
        "Enter a Semantic Scholar API key here or save it in client settings.",
        "Semantic ScholarのAPIキーを入力するか、クライアントの設定で保存してください。",
    ),
    "请输入数字格式的 Telegram 私聊 ID。": ("Enter the numeric Telegram chat ID.", "Telegramの数値チャットIDを入力してください。"),
    "检索间隔需为 1–525600 分钟。": ("Enter a search interval from 1 to 525600 minutes.", "検索間隔は1〜525600分で入力してください。"),
    "每日请求上限需为 1–10000 的整数。": ("Enter a request limit from 1 to 10000.", "リクエスト上限は1〜10000で入力してください。"),
    "请配置至少一个频道，并让每日及每轮额度覆盖全部频道。": (
        "Configure at least one channel and allow one request per channel in both budgets.",
        "チャンネルを1件以上設定し、24時間と1回の両上限で各チャンネルに1リクエスト分を確保してください。",
    ),
    "当前客户端缺少云端部署文件，请使用完整新版安装包。": (
        "Deployment files are missing. Use the complete updated package.",
        "展開ファイルが見つかりません。最新版の完全なパッケージを使用してください。",
    ),
    "这个 Bot 已被其它实例使用，请手动填写现有私聊 ID。": (
        "Another instance uses this bot. Enter the existing private chat ID.",
        "別のインスタンスがこのボットを使用中です。既存の個別チャットIDを手入力してください。",
    ),
    "Telegram 未返回有效的私聊记录。": ("Telegram did not return valid chat records.", "Telegramから有効なチャットの記録が返されませんでした。"),
    "请先在 Telegram 私聊机器人发送 /start，再获取私聊 ID。多个私聊时请手动填写。": (
        "Send /start to the bot first, then get the chat ID. If there are several chats, enter yours manually.",
        "先にTelegramでボットへ/startを送ってください。個別チャットが複数ある場合はIDを手入力してください。",
    ),
    "服务器操作超时。请先查看状态和日志，再决定是否重试。": (
        "The server operation timed out. Check status and logs before retrying.",
        "サーバー操作がタイムアウトしました。再試行の前に稼働状況とログを確認してください。",
    ),
    "SSH 主机指纹未确认或已变化。请核对服务器指纹后再连接。": (
        "The SSH fingerprint is unknown or changed. Check it before connecting.",
        "SSH指紋が未確認か変更されています。サーバーの指紋を照合してから接続してください。",
    ),
    "SSH 密钥登录失败。请确认服务器已添加公钥，需口令的私钥可先加载到 SSH Agent。": (
        "SSH key login failed. Check the server's public key or load the private key into SSH Agent.",
        "SSH鍵でログインできませんでした。公開鍵の登録を確認し、必要なら秘密鍵をSSH Agentに読み込んでください。",
    ),
    "论文检索": ("Paper search", "論文検索"),
    "检索来源": ("Search provider", "検索サービス"),
    "检索 API Key": ("Search API key", "検索用APIキー"),
    "清除当前检索来源保存的密钥": ("Clear this provider’s saved key", "この検索サービスの保存済みキーを削除"),
    "检索最近几天": ("Lookback (days)", "検索対象の日数"),
    "每轮请求上限": ("Request limit per run", "1回の検索リクエスト上限"),
    "自定义 JSON 接口": ("Custom JSON endpoint", "カスタムJSONエンドポイント"),
    "按接口文档填写请求和返回字段映射。": (
        "Configure the request and response fields using the API documentation.",
        "APIの仕様書に従って、リクエストとレスポンスの項目を設定します。",
    ),
    "摘要翻译": ("Abstract translation", "要旨翻訳"),
    "翻译服务": ("Translation service", "翻訳サービス"),
    "目标语言": ("Target language", "翻訳先の言語"),
    "完整接口地址": ("Full endpoint URL", "エンドポイントURL"),
    "模型（OpenAI 兼容）": ("OpenAI-compatible model", "OpenAI互換モデル"),
    "翻译 API Key": ("Translation API key", "翻訳用APIキー"),
    "清除当前翻译服务保存的密钥": ("Clear this translation service’s saved key", "この翻訳サービスの保存済みキーを削除"),
    "记住本次输入的密钥（Windows 加密）": ("Remember keys entered here (Windows encryption)", "入力したキーを保存（Windowsで暗号化）"),
    "密钥框留空时沿用当前服务的已有密钥。翻译在点击「翻译摘要」后请求。": (
        "Leave a key field blank to use the saved key. Translation starts when you click Translate abstract.",
        "キー欄を空欄にすると保存済みのキーを使用します。「要旨を翻訳」をクリックすると翻訳を開始します。",
    ),
    "保存设置": ("Save settings", "設定を保存"),
    "自定义 JSON": ("Custom JSON", "カスタムJSON"),
    "关闭": ("Off", "オフ"),
    "OpenAI 兼容": ("OpenAI-compatible", "OpenAI互換"),
    "简体中文": ("Simplified Chinese", "簡体字中国語"),
    "日语": ("Japanese", "日本語"),
    "英语": ("English", "英語"),
    "编辑频道 {number}": ("Edit channel {number}", "チャンネル{number}を編集"),
    "频道文件已在其他窗口修改。请重新打开客户端后再编辑。": (
        "The channel file changed in another window. Reopen the client before editing.",
        "別のウィンドウでチャンネルファイルが更新されました。クライアントを開き直してから編集してください。",
    ),
    "无法保存频道": ("Could not save channels", "チャンネルを保存できませんでした"),
    "已保存频道 {number}": ("Channel {number} saved", "チャンネル{number}を保存しました"),
    "删除频道": ("Delete channel", "チャンネルを削除"),
    "删除所选频道？": ("Delete the selected channel?", "選択したチャンネルを削除しますか？"),
    "已删除频道": ("Channel deleted", "チャンネルを削除しました"),
    "已保存全局屏蔽词": ("Global exclusions saved", "全チャンネルの除外語を保存しました"),
    "检索天数请输入 1–365，每轮请求上限请输入 1–200。": (
        "Enter 1–365 for lookback days and 1–200 for the request limit.",
        "検索対象の日数は1〜365、リクエスト上限は1〜200で入力してください。",
    ),
    "API Key 应是单行且不含空格。": (
        "Enter the API key on one line without spaces.", "APIキーは空白を含めず1行で入力してください。",
    ),
    "无法保存设置": ("Could not save settings", "設定を保存できませんでした"),
    "已保存设置": ("Settings saved", "設定を保存しました"),
    "本次检索": ("Current search", "今回の検索結果"),
    "{view} · {count} 篇": ("{view} · {count}", "{view} · {count}件"),
    "选择频道并检索，或从历史中打开一篇论文。": (
        "Select a channel to search, or open a paper from your history.",
        "検索するチャンネルを選ぶか、履歴から論文を開いてください。",
    ),
    "日期未知": ("Date unknown", "公開日不明"),
    "OpenAlex 索引关键词": ("OpenAlex index keywords", "OpenAlexの索引キーワード"),
    "来源提供的关键词": ("Source keywords", "掲載元のキーワード"),
    "来源关键词": ("Source keywords", "掲載元のキーワード"),
    "该来源未随这条记录提供关键词。": (
        "The source did not include keywords for this record.", "掲載元のこのレコードにはキーワードがありません。",
    ),
    "学科分类": ("Subject areas", "研究分野"),
    "命中的检索词": ("Matched search terms", "一致した検索語"),
    "频道 {number} · {term_a} × {term_b}": ("Channel {number} · {term_a} × {term_b}", "チャンネル{number} · {term_a} × {term_b}"),
    "原文摘要": ("Original abstract", "原文要旨"),
    "该来源未提供摘要。": ("The source did not provide an abstract.", "掲載元から要旨は提供されていません。"),
    "摘要译文 · {language}": ("Abstract translation · {language}", "要旨の訳文 · {language}"),
    "请先在「频道与屏蔽词」添加一个频道。": (
        "Add a channel in Channels & filters first.", "先に「チャンネルと除外語」でチャンネルを追加してください。",
    ),
    "无法开始检索": ("Could not start the search", "検索を開始できませんでした"),
    "{provider} 返回 {count} 篇符合条件的论文 · {requests} 次请求": (
        "{provider} · Matches {count} · Requests {requests}",
        "{provider} · 条件に一致した論文{count}件 · リクエスト{requests}回",
    ),
    "频道 {number}未完成（{reason}）": ("Channel {number} incomplete ({reason})", "チャンネル{number}は未完了（{reason}）"),
    "正在通过 {provider} 检索……": ("Searching {provider}…", "{provider}で検索中…"),
    "请先在「API 与设置」选择翻译服务。": (
        "Choose a translation service under API & settings.", "「APIと設定」で翻訳サービスを選択してください。",
    ),
    "已显示保存的译文。": ("Showing the saved translation.", "保存済みの訳文を表示しています。"),
    "无法读取翻译密钥": ("Could not read the translation key", "翻訳用APIキーを読み込めませんでした"),
    "已保存{language}译文。": ("{language} translation saved.", "{language}の訳文を保存しました。"),
    "正在使用 {provider} 翻译摘要……": ("Translating the abstract with {provider}…", "{provider}で要旨を翻訳中…"),
    "操作中断（{kind}）": ("Operation interrupted ({kind})", "操作を中断しました（{kind}）"),
    "操作未完成": ("Operation incomplete", "操作を完了できませんでした"),
    "确定": ("OK", "OK"),
    "取消": ("Cancel", "キャンセル"),
    "无法启动 CiteGlance": ("Could not start CiteGlance", "CiteGlanceを起動できませんでした"),
    "无法保存界面语言": ("Could not save the interface language", "表示言語を保存できませんでした"),
    "无法解密保存的密钥，请在设置中重新输入。": (
        "The saved key could not be decrypted. Enter it again in Settings.",
        "保存済みのキーを復号できません。設定でもう一度入力してください。",
    ),
    "Windows 无法保存加密密钥。可以取消记住密钥后再试。": (
        "Windows could not save the encrypted key. Turn off key storage and try again.",
        "Windowsが暗号化したキーを保存できませんでした。キーの保存をオフにしてもう一度お試しください。",
    ),
    "频道文件需要包含 channels 数组。": ("The channel file must contain a channels array.", "チャンネルファイルにはchannels配列が必要です。"),
    "next_channel_id 需要是正整数。": ("next_channel_id must be a positive integer.", "next_channel_idには正の整数を指定してください。"),
    "每个频道需使用唯一且大于零的数字 ID。": (
        "Each channel must have a unique positive numeric ID.", "各チャンネルには重複しない正の数値IDを指定してください。",
    ),
    "频道 {number} 缺少名称。": ("Channel {number} needs a name.", "チャンネル{number}の名前を入力してください。"),
    "频道 {number} 的 {group} 包含无效词组。": (
        "Channel {number} has an invalid phrase in {group}.", "チャンネル{number}の{group}に無効なフレーズがあります。",
    ),
    "频道 {number} 的 A、B 组各需要至少一个词组。": (
        "Channel {number} needs at least one phrase in each of groups A and B.",
        "チャンネル{number}のグループA、Bにはそれぞれ1フレーズ以上が必要です。",
    ),
    "全局屏蔽词列表包含无效词组。": (
        "The global exclusions contain an invalid phrase.", "全チャンネルの除外語に無効なフレーズがあります。",
    ),
    "{provider} 网络连接失败": ("Could not connect to {provider}", "{provider}に接続できませんでした"),
    "{provider} 返回了无法解析的结果": ("Could not read the response from {provider}", "{provider}からの応答を読み取れませんでした"),
    "已用完本次运行的 {budget} 次请求预算": ("The {budget}-request limit for this run was reached", "この検索は{budget}回のリクエスト上限に達しました"),
    "Semantic Scholar 返回的检索结果缺少 data": (
        "The Semantic Scholar response is missing the data field", "Semantic Scholarの検索結果にdata項目がありません",
    ),
    "已达请求预算": ("Request limit reached", "リクエスト上限に達しました"),
    "检索返回重复的分页标记": ("The search returned a repeated pagination token", "検索結果のページトークンが重複しています"),
    "请输入完整 HTTPS 端点。本机服务可以用 HTTP。参数请填在配置的 params 中。": (
        "Enter the full HTTPS endpoint. Local services may use HTTP. Put request parameters under params.",
        "完全なHTTPS URLを入力してください。ローカルサービスではHTTPを使用できます。パラメータはparamsに指定してください。",
    ),
    "自定义配置需要一个 JSON 对象。": ("The custom configuration must be a JSON object.", "カスタム設定にはJSONオブジェクトが必要です。"),
    "自定义请求方法可选 GET 或 POST。": ("Choose GET or POST for a custom request.", "カスタムリクエストにはGETまたはPOSTを選択してください。"),
    "params、body、auth 和 map 需要是 JSON 对象。": (
        "params, body, auth, and map must be JSON objects.", "params、body、auth、mapはJSONオブジェクトで指定してください。",
    ),
    "items 和 next 需要是 JSON 字段路径。": (
        "items and next must be JSON field paths.", "itemsとnextにはJSONの項目パスを指定してください。",
    ),
    "auth 的 location、name 和 prefix 需要是字符串。": (
        "The auth location, name, and prefix must be strings.", "authのlocation、name、prefixには文字列を指定してください。",
    ),
    "认证位置可选 header、query、body 或 none。": (
        "Authentication location can be header, query, body, or none.", "認証の場所はheader、query、body、noneから選択してください。",
    ),
    "JSON 请求体认证需要使用 POST。": ("Auth in the JSON request body requires POST.", "JSONリクエスト本文で認証するにはPOSTが必要です。"),
    "请填写合法的认证字段名称，例如 Authorization。": (
        "Enter a valid authentication field name, such as Authorization.", "Authorizationなど、有効な認証項目名を入力してください。",
    ),
    "认证前缀需要写在一行。": ("The authentication prefix must fit on one line.", "認証プレフィックスは1行で指定してください。"),
    "请在 map 中配置 title 对应的路径。": ("Set a path for title in map.", "mapでtitleの対応するパスを設定してください。"),
    "map 的字段路径需要是字符串。": ("Field paths in map must be strings.", "mapの項目パスには文字列を指定してください。"),
    "query_style 可选 boolean、keywords 或 semantic。": (
        "query_style can be boolean, keywords, or semantic.", "query_styleはboolean、keywords、semanticから選択してください。",
    ),
    "已到本轮请求预算": ("Request limit reached for this run", "今回のリクエスト上限に達しました"),
    "{provider} 要求较长的限流等待，本轮检索已暂停": (
        "{provider} requested a longer wait. This search was paused.",
        "{provider}から長い待機時間が指定されたため、今回の検索を一時停止しました。",
    ),
    "{provider} 的返回结果缺少论文列表，请检查设置或返回字段路径": (
        "{provider} did not return a paper list. Check the settings or response path.",
        "{provider}の応答に論文リストがありません。設定または応答の項目パスを確認してください。",
    ),
    "请在设置中输入 Semantic Scholar API Key。": (
        "Enter your Semantic Scholar API key in Settings.", "設定でSemantic ScholarのAPIキーを入力してください。",
    ),
    "请填写 DeepL API Key。": ("Enter your DeepL API key.", "DeepLのAPIキーを入力してください。"),
    "请填写翻译模型的名称。": ("Enter the translation model name.", "翻訳に使うモデル名を入力してください。"),
    "请先在设置中选择翻译服务。": (
        "Choose a translation service in Settings.", "設定で翻訳サービスを選択してください。",
    ),
    "{provider} 没有返回可显示的译文": (
        "{provider} did not return a translation to display", "{provider}から表示可能な訳文が返されませんでした",
    ),
    "{provider} HTTP {code}": ("{provider} HTTP {code}", "{provider} HTTP {code}"),
    "频道名称": ("Channel name", "チャンネル名"),
    "请输入整数。": ("Enter whole numbers.", "整数を入力してください。"),
    "JSON 格式错误（第 {line} 行，第 {column} 列）": (
        "Invalid JSON (line {line}, column {column})", "JSONの形式が正しくありません（{line}行目、{column}列目）",
    ),
}


ERROR_TEMPLATES = (
    "频道 {number} 缺少名称。",
    "频道 {number} 的 {group} 包含无效词组。",
    "频道 {number} 的 A、B 组各需要至少一个词组。",
    "{provider} 网络连接失败",
    "{provider} 返回了无法解析的结果",
    "已用完本次运行的 {budget} 次请求预算",
    "{provider} 要求较长的限流等待，本轮检索已暂停",
    "{provider} 的返回结果缺少论文列表，请检查设置或返回字段路径",
    "{provider} 没有返回可显示的译文",
    "{provider} HTTP {code}",
    "操作中断（{kind}）",
)
ERROR_PATTERNS = tuple(
    (re.compile(re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+?)", re.escape(template))), template)
    for template in ERROR_TEMPLATES
)


def translate(locale, key, **values):
    options = TEXT.get(key)
    index = {"en": 0, "ja": 1}.get(locale)
    text = options[index] if options and index is not None else key
    return text.format(**values) if values else text


def translate_error(language, error):
    text = str(error)
    if text in TEXT:
        return translate(language, text)
    for pattern, template in ERROR_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            values = match.groupdict()
            if "provider" in values:
                values["provider"] = translate(language, values["provider"])
            return translate(language, template, **values)
    return text
