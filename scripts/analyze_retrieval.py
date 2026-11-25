"""用 data/eval/questions.jsonl 檢驗檢索：資安相關 vs 無關問題，最相近那塊的距離怎麼分布？
哪些文件「吸」走太多無關問題（hub）？哪些主題、問法、語言讓距離變小或變大？

只做檢索（轉向量加查資料庫），不呼叫 Claude，不花額度。

用法（容器內，專案根目錄）：
  docker compose exec backend python scripts/analyze_retrieval.py
輸出：終端機的統計 + data/eval/results.csv（每一題的前 3 名）
"""
import asyncio
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np                                    # noqa: E402
from sqlalchemy import select                         # noqa: E402
from app.agent.RAG.embeding import embed_texts       # noqa: E402
from app.base import SessionLocal, engine             # noqa: E402
from app.models import Chunks                         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "data" / "eval" / "questions.jsonl"
RESULTS = ROOT / "data" / "eval" / "results.csv"
BATCH = 64


def title(content: str) -> str:
    return content.split("\n", 1)[0]


def q(a, p):
    return float(np.percentile(a, p))


async def main():
    rows = [json.loads(l) for l in open(QUESTIONS, encoding="utf-8")]
    print(f"題目 {len(rows)} 題，開始向量化（每批 {BATCH}）…")
    t0 = time.time()
    vecs = []
    for i in range(0, len(rows), BATCH):
        vecs += await embed_texts([r["question"] for r in rows[i:i + BATCH]])
        print(f"  向量化 {min(i + BATCH, len(rows))}/{len(rows)}｜{time.time() - t0:.0f} 秒", flush=True)

    print("檢索中…")
    async with SessionLocal() as s:
        for r, v in zip(rows, vecs):
            d = Chunks.vector.cosine_distance(v)
            top = (await s.execute(select(Chunks.content, d.label("d")).order_by(d).limit(3))).all()
            r["top"] = [(title(t.content), float(t.d)) for t in top]
            r["d1"] = r["top"][0][1]
            r["t1"] = r["top"][0][0]
    await engine.dispose()

    with open(RESULTS, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["id", "class", "subtype", "topic", "lang", "question", "d1", "title1", "d2", "title2", "d3", "title3"])
        for r in rows:
            w.writerow([r["id"], r["class"], r["subtype"], r["topic"], r["lang"], r["question"]] +
                       [x for t, d in r["top"] for x in (round(d, 4), t)][0:0] +
                       [round(r["top"][0][1], 4), r["top"][0][0], round(r["top"][1][1], 4), r["top"][1][0], round(r["top"][2][1], 4), r["top"][2][0]])

    by_sub = defaultdict(list)
    for r in rows:
        by_sub[r["subtype"]].append(r["d1"])
    sec = np.array([r["d1"] for r in rows if r["class"] == "security"])
    unr = np.array([r["d1"] for r in rows if r["class"] == "unrelated"])

    print("\n" + "=" * 70 + "\n【A】最相近那一塊的距離（越小越像）")
    print(f"{'子類':14s}{'題數':>5s}{'平均':>8s}{'P10':>8s}{'P50':>8s}{'P90':>8s}")
    for sub in ["in_scope", "out_of_scope", "tech", "life"]:
        a = np.array(by_sub[sub])
        print(f"{sub:14s}{len(a):5d}{a.mean():8.3f}{q(a, 10):8.3f}{q(a, 50):8.3f}{q(a, 90):8.3f}")

    # AUC：隨機抽一個無關、一個資安，無關的距離比較大的機率
    allv = np.concatenate([sec, unr])
    ranks = allv.argsort().argsort() + 1
    auc = (ranks[len(sec):].sum() - len(unr) * (len(unr) + 1) / 2) / (len(sec) * len(unr))
    print(f"\n【B】用「最近距離」區分資安 vs 無關：AUC = {auc:.3f}（1.0 = 完全分開，0.5 = 等於亂猜）")
    best = max(np.arange(0.25, 0.80, 0.005), key=lambda th: ((sec <= th).mean() + (unr > th).mean()) / 2)
    for th in (0.45, 0.50, 0.55, round(float(best), 3)):
        print(f"  門檻 {th:.3f}：資安題放行 {(sec <= th).mean() * 100:5.1f}%｜無關題擋下 {(unr > th).mean() * 100:5.1f}%" + ("   ← 平衡正確率最高" if th == round(float(best), 3) else ""))
    th = float(best)
    print(f"  以 {th:.3f} 為門檻，各子類放行率：" + "、".join(f"{k} {np.mean(np.array(v) <= th) * 100:.0f}%" for k, v in by_sub.items()))

    print("\n" + "=" * 70 + "\n【C】哪些文件「吸」走最多無關問題（無關題的第 1 名）")
    hub = Counter(r["t1"] for r in rows if r["class"] == "unrelated")
    for t, n in hub.most_common(12):
        print(f"  {n:4d} 題 ({n / len(unr) * 100:4.1f}%) | {t}")
    print(f"  無關題共命中 {len(hub)} 份不同文件；前 5 名佔 {sum(n for _, n in hub.most_common(5)) / len(unr) * 100:.0f}%")
    hub_s = Counter(r["t1"] for r in rows if r["class"] == "security")
    print("  對照：資安題的第 1 名分布（前 8）")
    for t, n in hub_s.most_common(8):
        print(f"  {n:4d} 題 | {t}")

    print("\n" + "=" * 70 + "\n【D】主題的影響（每個主題 6 題，取平均距離）")
    topic = defaultdict(list)
    for r in rows:
        topic[(r["subtype"], r["topic"])].append(r)
    def mean_d(rs): return float(np.mean([x["d1"] for x in rs]))
    for sub, label, rev in [("in_scope", "資安範圍內：距離最大的 8 個主題（檢索最不準）", True),
                            ("in_scope", "資安範圍內：距離最小的 6 個主題（最準）", False),
                            ("out_of_scope", "資安但範圍外：距離最小的 8 個（最容易被誤認為有資料）", False),
                            ("tech", "無關（技術類）：距離最小的 8 個（最容易騙過門檻）", False),
                            ("life", "無關（生活類）：距離最小的 6 個", False)]:
        items = sorted(((mean_d(rs), t, rs) for (s, t), rs in topic.items() if s == sub), reverse=rev)
        n = 6 if "6 個" in label else 8
        print(f"\n  {label}")
        for m, t, rs in items[:n]:
            top = Counter(x["t1"] for x in rs).most_common(1)[0][0]
            print(f"    {m:.3f} | {t}  → {top}")

    print("\n" + "=" * 70 + "\n【E】語言與問法的影響")
    for cls in ("security", "unrelated"):
        zh = [r["d1"] for r in rows if r["class"] == cls and r["lang"] == "zh"]
        en = [r["d1"] for r in rows if r["class"] == cls and r["lang"] == "en"]
        print(f"  {cls:10s} 中文平均 {np.mean(zh):.3f}（{len(zh)} 題）｜英文平均 {np.mean(en):.3f}（{len(en)} 題）")
    for sub in ("in_scope", "out_of_scope"):
        zh = [r["d1"] for r in rows if r["subtype"] == sub and r["lang"] == "zh"]
        en = [r["d1"] for r in rows if r["subtype"] == sub and r["lang"] == "en"]
        print(f"  {sub:13s} 中文平均 {np.mean(zh):.3f}｜英文平均 {np.mean(en):.3f}")
    tpl = defaultdict(list)
    for r in rows:
        if r["class"] == "security" and r["lang"] == "zh":
            tpl[r["template"]].append(r["d1"])
    SEC_ZH = ["{t}是什麼？", "{t}怎麼運作？", "{t}有哪些常見的手法？", "如何預防{t}？", "請說明{t}的防護措施", "攻擊者如何利用{t}？",
              "{t}有什麼風險？", "我該怎麼偵測{t}？", "能不能簡單解釋{t}？", "{t}跟一般的做法有什麼差別？", "幫我分析一下{t}", "{t}的實際例子有哪些？"]
    print("  資安中文題：各問法的平均距離（由小到大）")
    for k, v in sorted(tpl.items(), key=lambda kv: np.mean(kv[1])):
        print(f"    {np.mean(v):.3f} | {SEC_ZH[k]}（{len(v)} 題）")

    print(f"\n已輸出每題結果：{RESULTS}")


asyncio.run(main())
