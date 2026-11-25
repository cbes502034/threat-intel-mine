"""產生檢索評測用的問題集：資安相關 vs 無關，輸出 data/eval/questions.jsonl。

做法：每個「主題」配上多種問法（中文為主、約三成英文），每個主題固定抽 6 個問法，
這樣每個主題的題數相同，之後才能比較「哪些主題或問法讓檢索偏向某些文件」。

分類（class）：
  security  = 資安相關
      in_scope     知識庫範圍內（ATT&CK 偵察、資源開發、初始入侵、C2、緩解措施、子網域接管、Cloudflare DNS）
      out_of_scope 資安相關，但知識庫沒收（入侵後處置、鑑識、其他戰術、其他漏洞類型…）
  unrelated = 與資安無關
      life         生活、學習、興趣等
      tech         一般資訊技術（刻意挑比較貼近的，測試門檻會不會被騙）

用法：python scripts/make_eval_questions.py
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "eval" / "questions.jsonl"
PER_TOPIC = 6
EN_RATIO = 0.3
random.seed(20261124)

# ───────── 主題：(中文, 英文) ─────────
IN_SCOPE = [
    ("網路釣魚", "phishing"), ("魚叉式釣魚", "spearphishing"), ("釣魚簡訊", "smishing"), ("語音釣魚", "vishing"),
    ("惡意附件", "malicious attachments"), ("惡意連結", "malicious links"), ("偽造網域", "look-alike domains"),
    ("網域註冊濫用", "domain registration abuse"), ("購買網域", "acquiring domains"),
    ("取得攻擊基礎設施", "acquiring attack infrastructure"), ("入侵他人的基礎設施", "compromising third-party infrastructure"),
    ("雲端伺服器濫用", "abusing cloud servers"), ("無伺服器服務濫用", "serverless abuse"),
    ("命令與控制", "command and control"), ("C2 通道", "C2 channels"), ("DNS 隧道", "DNS tunneling"),
    ("多層代理", "multi-hop proxies"), ("隱藏攻擊基礎設施", "hiding attack infrastructure"), ("網域前置", "domain fronting"),
    ("資料編碼", "data encoding"), ("加密通訊通道", "encrypted communication channels"), ("非標準連接埠", "non-standard ports"),
    ("遠端存取工具", "remote access tools"), ("蒐集受害者主機資訊", "gathering victim host information"),
    ("蒐集受害者身分資訊", "gathering victim identity information"), ("蒐集受害者網路資訊", "gathering victim network information"),
    ("主動掃描", "active scanning"), ("搜尋公開網站與資料庫", "searching open websites and databases"),
    ("蒐集帳號憑證", "harvesting credentials"), ("社交工程", "social engineering"), ("供應鏈入侵", "supply chain compromise"),
    ("硬體供應鏈", "hardware supply chain"), ("路過式下載", "drive-by compromise"), ("可信關係濫用", "trusted relationship abuse"),
    ("有效帳號濫用", "valid account abuse"), ("利用對外開放的應用程式漏洞", "exploiting public-facing applications"),
    ("外部遠端服務", "external remote services"), ("內容注入", "content injection"),
    ("子網域接管", "subdomain takeover"), ("懸空 DNS 記錄", "dangling DNS records"), ("CNAME 記錄", "CNAME records"),
    ("DNS 代理狀態", "DNS proxy status"), ("Cloudflare 橘色雲朵", "the Cloudflare orange cloud"),
    ("來源伺服器 IP 保護", "origin server IP protection"), ("DNS-only 記錄", "DNS-only records"),
    ("Cloudflare IP 範圍", "Cloudflare IP ranges"), ("多因素驗證", "multi-factor authentication"),
    ("密碼政策", "password policies"), ("網路分段", "network segmentation"), ("網路流量過濾", "network traffic filtering"),
    ("網路入侵防護", "network intrusion prevention"), ("限制網頁內容", "restricting web-based content"),
    ("使用者教育訓練", "user security training"), ("軟體更新", "software updates"), ("弱點掃描", "vulnerability scanning"),
    ("防毒軟體", "antivirus software"), ("TLS 流量檢查", "SSL/TLS inspection"), ("特權帳號管理", "privileged account management"),
    ("應用程式隔離", "application isolation"), ("限制軟體安裝", "limiting software installation"),
    ("稽核與日誌", "auditing and logging"), ("加密敏感資訊", "encrypting sensitive information"),
    ("帳號使用政策", "account use policies"), ("作業系統組態強化", "operating system hardening"),
]
OUT_OF_SCOPE = [
    ("入侵後的處置", "post-compromise response"), ("數位鑑識", "digital forensics"), ("勒索軟體", "ransomware"),
    ("SQL 注入", "SQL injection"), ("跨站腳本攻擊", "cross-site scripting"), ("跨站請求偽造", "CSRF"),
    ("緩衝區溢位", "buffer overflows"), ("零時差漏洞", "zero-day vulnerabilities"), ("DDoS 攻擊", "DDoS attacks"),
    ("殭屍網路", "botnets"), ("蜜罐", "honeypots"), ("惡意程式逆向工程", "malware reverse engineering"),
    ("滲透測試", "penetration testing"), ("紅隊演練", "red team exercises"), ("SIEM 日誌分析", "SIEM log analysis"),
    ("端點偵測與回應", "endpoint detection and response"), ("零信任架構", "zero trust architecture"),
    ("資料外洩", "data exfiltration"), ("橫向移動", "lateral movement"), ("權限提升", "privilege escalation"),
    ("持久化機制", "persistence mechanisms"), ("防禦規避", "defense evasion"), ("密碼雜湊破解", "password hash cracking"),
    ("憑證傾印", "credential dumping"), ("事件通報流程", "incident reporting procedures"), ("備份與災難復原", "backup and disaster recovery"),
    ("資安法規遵循", "security compliance"), ("個資保護法規", "data protection regulations"), ("資安稽核", "security audits"),
    ("威脅獵捕", "threat hunting"), ("加密演算法", "encryption algorithms"), ("數位簽章", "digital signatures"),
    ("區塊鏈安全", "blockchain security"), ("物聯網安全", "IoT security"), ("行動裝置安全", "mobile device security"),
    ("雲端安全", "cloud security"), ("容器安全", "container security"), ("API 安全", "API security"),
    ("無線網路安全", "Wi-Fi security"), ("VPN 安全", "VPN security"), ("Tor 網路", "the Tor network"), ("暗網", "the dark web"),
    ("內部威脅", "insider threats"), ("社群媒體詐騙", "social media scams"), ("身份盜用", "identity theft"),
    ("木馬程式", "trojans"), ("電腦蠕蟲", "computer worms"), ("rootkit", "rootkits"), ("鍵盤記錄器", "keyloggers"),
    ("挖礦惡意程式", "cryptojacking"),
]
LIFE = [
    ("煮泡麵", "cooking instant noodles"), ("做蛋糕", "baking a cake"), ("沖煮咖啡", "brewing coffee"), ("減重", "losing weight"),
    ("跑步訓練", "running training"), ("學吉他", "learning guitar"), ("養貓", "keeping a cat"), ("養狗", "keeping a dog"),
    ("種植盆栽", "growing houseplants"), ("旅遊規劃", "trip planning"), ("日本自由行", "traveling in Japan"), ("買房", "buying a house"),
    ("股票投資", "stock investing"), ("定期定額基金", "index fund investing"), ("學英文", "learning English"), ("學日文", "learning Japanese"),
    ("寫履歷", "writing a resume"), ("租房子", "renting an apartment"), ("看電影", "watching movies"), ("推薦小說", "novel recommendations"),
    ("打籃球", "playing basketball"), ("游泳", "swimming"), ("瑜伽", "yoga"), ("露營", "camping"), ("釣魚", "fishing"),
    ("攝影", "photography"), ("繪畫", "drawing"), ("烘焙麵包", "baking bread"), ("素食", "a vegetarian diet"), ("睡眠品質", "sleep quality"),
    ("感冒", "the common cold"), ("頭痛", "headaches"), ("天氣預報", "weather forecasts"), ("颱風", "typhoons"), ("地震", "earthquakes"),
    ("太陽系", "the solar system"), ("恐龍", "dinosaurs"), ("世界史", "world history"), ("台灣歷史", "Taiwanese history"),
    ("微積分", "calculus"), ("機率", "probability"), ("化學反應", "chemical reactions"), ("電動車", "electric cars"),
    ("買二手車", "buying a used car"), ("機車保養", "motorcycle maintenance"), ("洗衣服", "doing laundry"), ("整理房間", "organizing a room"),
    ("婚禮籌備", "wedding planning"), ("育兒", "parenting"), ("大學申請", "college applications"), ("論文寫作", "thesis writing"),
    ("創業", "starting a business"), ("行銷文案", "copywriting"), ("咖啡館推薦", "cafe recommendations"), ("電玩遊戲", "video games"),
    ("下棋", "playing chess"), ("魔術", "magic tricks"), ("園藝", "gardening"), ("台北美食", "Taipei food"), ("夜市", "night markets"),
    ("高鐵", "high-speed rail"), ("捷運", "metro systems"),
]
TECH = [
    ("Python 迴圈", "Python loops"), ("安裝 Linux", "installing Linux"), ("設定家用路由器", "configuring a home router"),
    ("HTTP 協定", "the HTTP protocol"), ("網頁排版", "web page layout"), ("資料庫索引", "database indexes"), ("Git 分支", "Git branches"),
    ("Docker 容器", "Docker containers"), ("雲端運算", "cloud computing"), ("CDN 網頁加速", "CDN web acceleration"),
    ("註冊網域名稱", "registering a domain name"), ("設定 DNS 解析", "configuring DNS resolution"), ("網站託管", "web hosting"),
    ("負載平衡", "load balancing"), ("REST API 設計", "REST API design"), ("機器學習", "machine learning"), ("神經網路", "neural networks"),
    ("作業系統", "operating systems"), ("記憶體管理", "memory management"), ("軟體測試", "software testing"),
    ("程式除錯", "debugging code"), ("SQL 查詢", "SQL queries"), ("Excel 公式", "Excel formulas"), ("網路速度", "internet speed"),
    ("組裝電腦", "building a PC"),
]

# ───────── 問法 ─────────
SEC_ZH = ["{t}是什麼？", "{t}怎麼運作？", "{t}有哪些常見的手法？", "如何預防{t}？", "請說明{t}的防護措施", "攻擊者如何利用{t}？",
          "{t}有什麼風險？", "我該怎麼偵測{t}？", "能不能簡單解釋{t}？", "{t}跟一般的做法有什麼差別？", "幫我分析一下{t}", "{t}的實際例子有哪些？"]
SEC_EN = ["What is {t}?", "How does {t} work?", "What are common techniques related to {t}?", "How can I prevent {t}?",
          "What defenses exist against {t}?", "How do attackers abuse {t}?", "What are the risks of {t}?", "How do I detect {t}?",
          "Can you explain {t} simply?", "How is {t} different from the usual approach?", "Help me analyze {t}", "What are real examples of {t}?"]
GEN_ZH = ["{t}是什麼？", "請教我{t}", "{t}要注意什麼？", "怎麼學{t}？", "有什麼{t}的推薦？", "{t}的步驟是什麼？",
          "幫我規劃{t}", "{t}有哪些種類？", "{t}的優缺點是什麼？", "能簡單解釋{t}嗎？", "{t}一般要花多少錢？", "新手該怎麼開始{t}？"]
GEN_EN = ["What is {t}?", "Teach me about {t}", "What should I watch out for with {t}?", "How do I learn {t}?",
          "Any recommendations for {t}?", "What are the steps for {t}?", "Help me plan {t}", "What kinds of {t} are there?",
          "What are the pros and cons of {t}?", "Can you explain {t} briefly?", "How much does {t} usually cost?",
          "How should a beginner start with {t}?"]

GROUPS = [
    ("security", "in_scope", IN_SCOPE, SEC_ZH, SEC_EN),
    ("security", "out_of_scope", OUT_OF_SCOPE, SEC_ZH, SEC_EN),
    ("unrelated", "life", LIFE, GEN_ZH, GEN_EN),
    ("unrelated", "tech", TECH, GEN_ZH, GEN_EN),
]

rows = []
for cls, sub, topics, zh_t, en_t in GROUPS:
    for zh, en in topics:
        for ti in random.sample(range(len(zh_t)), PER_TOPIC):
            is_en = random.random() < EN_RATIO
            q = (en_t if is_en else zh_t)[ti].format(t=en if is_en else zh)
            rows.append({"class": cls, "subtype": sub, "topic": zh, "topic_en": en, "template": ti,
                         "lang": "en" if is_en else "zh", "question": q})

random.shuffle(rows)
for i, r in enumerate(rows, 1):
    r["id"] = i
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fp:
    for r in rows:
        fp.write(json.dumps(r, ensure_ascii=False) + "\n")

from collections import Counter
print("共", len(rows), "題 →", OUT)
print("分類:", dict(Counter(r["class"] for r in rows)))
print("子類:", dict(Counter(r["subtype"] for r in rows)))
print("語言:", dict(Counter(r["lang"] for r in rows)))
print("題目重複數:", len(rows) - len({r["question"] for r in rows}))
for r in rows[:6]:
    print("  ", r["class"], r["subtype"], "|", r["question"])
