"""下載並整理知識庫來源。只做「資料準備」，不做切片與 embedding。

輸出（都在 data/ 底下）：
  raw/      原始下載檔（體積大，之後 git init 時要排除）
  corpus/   給 RAG 用的文件（JSONL，每行一份文件）＋ LICENSES.md

執行：python scripts/build_knowledge.py
"""
import base64
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CORPUS = ROOT / "data" / "corpus"
for d in (RAW, CORPUS):
    d.mkdir(parents=True, exist_ok=True)

TODAY = date.today().isoformat()
HEADERS = {"User-Agent": "threat-intel-mine-kb-builder"}


def fetch(url: str, dest: Path | None = None) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if dest:
        dest.write_bytes(data)
    return data


def write_jsonl(path: Path, docs: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


# ───────────── MITRE ATT&CK（區塊：攻擊行為）─────────────
ATTACK_URL = ("https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
              "master/enterprise-attack/enterprise-attack.json")
# 只取「從外部就看得到」的戰術；進入內部後的行為（提權、橫向移動…）不收
ATTACK_TACTICS = {"reconnaissance", "resource-development", "initial-access", "command-and-control"}


def clean_attack_text(text: str) -> str:
    text = re.sub(r"\(Citation:[^)]*\)", "", text)          # 去掉引用標記
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)    # [文字](連結) → 文字
    text = re.sub(r"</?code>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def build_attack() -> list[dict]:
    raw = RAW / "enterprise-attack.json"
    fetch(ATTACK_URL, raw)
    data = json.loads(raw.read_text(encoding="utf-8"))
    docs = []
    for o in data["objects"]:
        if o["type"] != "attack-pattern" or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        tactics = [p["phase_name"] for p in o.get("kill_chain_phases", [])
                   if p.get("kill_chain_name") == "mitre-attack"]
        if not ATTACK_TACTICS.intersection(tactics):
            continue
        ref = next((r for r in o.get("external_references", [])
                    if r.get("source_name") == "mitre-attack"), None)
        if not ref:
            continue
        title = f"{ref['external_id']} {o['name']}"
        body = clean_attack_text(o.get("description", ""))
        docs.append({
            "id": f"attack:{ref['external_id']}",
            "block": "攻擊行為",
            "source": "MITRE ATT&CK",
            "title": title,
            "section": ", ".join(sorted(ATTACK_TACTICS.intersection(tactics))),
            "url": ref.get("url"),
            "license": "MITRE ATT&CK 授權（須保留版權聲明與授權文字，見 LICENSES.md）",
            "retrieved_at": TODAY,
            "text": f"{title}\nTactics: {', '.join(tactics)}\n\n{body}",
        })
    return docs


def build_attack_mitigations() -> list[dict]:
    """ATT&CK 的緩解措施（M 開頭）：只取「對應到上面已選手法」的那些，每個措施一份文件。"""
    data = json.loads((RAW / "enterprise-attack.json").read_text(encoding="utf-8"))
    objs = {o["id"]: o for o in data["objects"]}

    selected = {}  # stix id -> (外部編號, 名稱)
    for o in data["objects"]:
        if o["type"] != "attack-pattern" or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        tactics = {p["phase_name"] for p in o.get("kill_chain_phases", [])
                   if p.get("kill_chain_name") == "mitre-attack"}
        ref = next((r for r in o.get("external_references", [])
                    if r.get("source_name") == "mitre-attack"), None)
        if ref and ATTACK_TACTICS & tactics:
            selected[o["id"]] = (ref["external_id"], o["name"])

    by_mitigation: dict[str, list] = {}
    for o in data["objects"]:
        if o["type"] != "relationship" or o.get("relationship_type") != "mitigates":
            continue
        if o["target_ref"] not in selected:
            continue
        m = objs.get(o["source_ref"])
        if m and m["type"] == "course-of-action" and not m.get("revoked") and not m.get("x_mitre_deprecated"):
            by_mitigation.setdefault(m["id"], []).append(
                (selected[o["target_ref"]], clean_attack_text(o.get("description", ""))))

    docs = []
    for mid, items in by_mitigation.items():
        m = objs[mid]
        ref = next((r for r in m.get("external_references", [])
                    if r.get("source_name") == "mitre-attack"), None)
        if not ref:
            continue
        lines = [f"- {tid} {tname}: {desc}" if desc else f"- {tid} {tname}"
                 for (tid, tname), desc in sorted(items)]
        title = f"{ref['external_id']} {m['name']}"
        docs.append({
            "id": f"attack-mitigation:{ref['external_id']}",
            "block": "處置與防護",
            "source": "MITRE ATT&CK（緩解措施）",
            "title": title,
            "section": "",
            "url": ref.get("url"),
            "license": "MITRE ATT&CK 授權（須保留版權聲明與授權文字，見 LICENSES.md）",
            "retrieved_at": TODAY,
            "text": (f"{title}\n\n{clean_attack_text(m.get('description', ''))}\n\n"
                     "Mitigates these techniques:\n" + "\n".join(lines)),
        })
    return docs


# ───────────── OWASP（區塊：網域與 DNS 風險）─────────────
OWASP_URL = ("https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/"
             "cheatsheets/Subdomain_Takeover_Prevention_Cheat_Sheet.md")


def build_owasp() -> list[dict]:
    raw = RAW / "owasp_subdomain_takeover.md"
    text = fetch(OWASP_URL, raw).decode("utf-8")
    m = re.search(r"^#\s+(.+)$", text, re.M)
    title = m.group(1).strip() if m else "Subdomain Takeover Prevention Cheat Sheet"
    return [{
        "id": "owasp:subdomain-takeover-prevention",
        "block": "網域與 DNS 風險",
        "source": "OWASP Cheat Sheet Series",
        "title": title,
        "section": "",
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Subdomain_Takeover_Prevention_Cheat_Sheet.html",
        "license": "CC BY-SA 4.0（須標示出處，衍生作品同授權）",
        "retrieved_at": TODAY,
        "text": text.strip(),
    }]


# ───────────── Cloudflare 文件（區塊：匿名與共享基礎設施、處置與防護）─────────────
CF_RAW = "https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/"
CF_SITE = "https://developers.cloudflare.com/"
CF_FILES = [
    ("src/content/docs/fundamentals/security/protect-your-origin-server.mdx",
     "fundamentals/security/protect-your-origin-server/", "處置與防護"),
    ("src/content/docs/fundamentals/concepts/cloudflare-ip-addresses.mdx",
     "fundamentals/concepts/cloudflare-ip-addresses/", "匿名與共享基礎設施"),
    ("src/content/docs/fundamentals/concepts/how-cloudflare-works.mdx",
     "fundamentals/concepts/how-cloudflare-works/", "匿名與共享基礎設施"),
    ("src/content/docs/dns/proxy-status/index.mdx",
     "dns/proxy-status/", "匿名與共享基礎設施"),
]


def clean_mdx(text: str) -> tuple[str, str]:
    title = ""
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if fm:
        t = re.search(r"^title:\s*(.+)$", fm.group(1), re.M)
        if t:
            title = t.group(1).strip().strip("\"'")
        text = text[fm.end():]
    text = re.sub(r"^import .*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text.strip()


def build_cloudflare() -> list[dict]:
    docs = []
    for path, site_path, block in CF_FILES:
        raw = RAW / ("cloudflare_" + path.replace("/", "_"))
        text = fetch(CF_RAW + path, raw).decode("utf-8")
        title, body = clean_mdx(text)
        docs.append({
            "id": "cloudflare:" + site_path.strip("/"),
            "block": block,
            "source": "Cloudflare Docs",
            "title": title or site_path,
            "section": "",
            "url": CF_SITE + site_path,
            "license": "CC BY 4.0（須標示出處）",
            "retrieved_at": TODAY,
            "text": body,
        })
    return docs


# ───────────── 授權說明 ─────────────
def build_licenses() -> None:
    req = urllib.request.Request(
        "https://api.github.com/repos/mitre-attack/attack-stix-data/license", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        lic = json.load(r)
    attack_license = base64.b64decode(lic["content"]).decode("utf-8", "replace")
    (CORPUS / "LICENSES.md").write_text(
        "# 知識庫來源與授權\n\n"
        "| 來源 | 授權 | 備註 |\n|---|---|---|\n"
        "| MITRE ATT&CK | MITRE 授權（見下） | 複製時須保留版權聲明與授權文字 |\n"
        "| OWASP Cheat Sheet Series | CC BY-SA 4.0 | 須標示出處；衍生作品同授權 |\n"
        "| Cloudflare Docs | CC BY 4.0 | 須標示出處 |\n\n"
        "## MITRE ATT&CK 授權原文\n\n```\n" + attack_license + "\n```\n",
        encoding="utf-8")


def stats(name: str, docs: list[dict]) -> None:
    chars = sum(len(d["text"]) for d in docs)
    print(f"{name:12s} 文件數 {len(docs):4d} | 字元 {chars:8d} | 約 {chars // 4:7d} tokens（英文以 4 字元 ≈ 1 token 估）")


if __name__ == "__main__":
    attack = build_attack()
    write_jsonl(CORPUS / "attack.jsonl", attack)
    mitigations = build_attack_mitigations()
    write_jsonl(CORPUS / "attack_mitigations.jsonl", mitigations)
    owasp = build_owasp()
    write_jsonl(CORPUS / "owasp.jsonl", owasp)
    cf = build_cloudflare()
    write_jsonl(CORPUS / "cloudflare.jsonl", cf)
    build_licenses()
    stats("ATT&CK", attack)
    stats("ATT&CK 緩解", mitigations)
    stats("OWASP", owasp)
    stats("Cloudflare", cf)
