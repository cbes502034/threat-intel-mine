import ollama
from app.agent.RAG.chunker import Chunker, data_combiner, pipeline, fetch_text_from_json
from time import time
from app.config import OLLAMA_URL

"""嵌入：讀語料 → 切片 → 轉成向量。build_index.py 與 services.py 都會用到這裡。"""

def get_chunked_data():
    """讀四份語料、各自切片，回傳攤平後的 list[str]（每個元素是一塊文字，共 537 塊）。"""
    raw_datas = data_combiner(["attack_mitigations.jsonl","attack.jsonl","cloudflare.jsonl","owasp.jsonl"])
    attack_mitigations_obj = Chunker()
    attack_obj = Chunker()
    cloudflare_obj = Chunker()
    owasp_obj = Chunker()
    # 四個 Chunker 與四份原始資料依序配對，把原始資料掛到 obj.full_data 讓它處理
    for  obj, (name, raw) in zip([attack_mitigations_obj, attack_obj, cloudflare_obj, owasp_obj], raw_datas.items()):
        obj.full_data = raw

    result = pipeline(
        attack_mitigations=attack_mitigations_obj,
        attack = attack_obj,
        cloudflare = cloudflare_obj,
        owasp = owasp_obj
    )
    result = fetch_text_from_json(result)   # 把巢狀結構壓平，只留每塊的 text
    return result

# chunked_data = get_chunked_data()
async def embed_texts(texts: get_chunked_data):
    """把一批文字（list[str]）送給 Ollama 的 bge-m3，回傳等長的向量清單（每個 1024 維）。
    建索引時傳一批切片，查詢時傳 [問題]。注意：問題與切片必須用同一個模型，距離才有意義。
    （參數的型別標註 get_chunked_data 其實不精確，實際型別是 list[str]）
    """
    client = ollama.AsyncClient(host=OLLAMA_URL)
    response = await client.embed(
        model = "bge-m3",
        input=texts
    )
    vectors = response["embeddings"]
    return vectors
