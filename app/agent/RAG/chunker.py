import json
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
# 專案根目錄：本檔在 app/agent/RAG/chunker.py，往上三層就是專案根（容器裡是 /app）
# LIMIT = 1500   # 單位：字元
# SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

class Chunker:
    """把一份語料（每筆是一篇文件）切成多塊，並保留 metadata 與文件標題。
    chunk_size / chunk_overlap 的單位是「字元」（langchain 預設用 len()，不是 token）。
    使用方式：先設 obj.full_data = 語料 list[dict]，再呼叫 executings()。
    """
    def __init__(self,
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 separotors: list =  ["\n\n", "\n", ". ", " ", ""],
                 split_target_key: str = "text",
                 doc_id_key: str = "id",
                 metadata_keys: list = ["id", "block", "source", "title",
                                         "section", "url", "license", "retrieved_at"],
                 title_key: str = "title",
                 add_title: bool = True,   # 評測時可關掉，比較「有／沒有標題前綴」的差異

    ):
        # 1. 初始化切分器
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            # 優先按段落、換行、句號切分，盡量不破壞完整句子
            separators=separotors
        )
        self.split_target_key: str = split_target_key
        self.doc_id_key: str = doc_id_key
        self.metadata_keys: list = metadata_keys
        self.title_key: str = title_key
        self.add_title: bool = add_title

    def _add_title(self, chunk: str, title: str) -> str:
        """從文章中間切出來的塊開頭沒有標題，embedding 就不知道它屬於哪份文件，所以補上。
        開關關閉、沒有標題、或這一塊本來就以標題開頭（通常是第 1 塊）時，原樣回傳。
        """
        if not self.add_title or not title or chunk.startswith(title):
            return chunk
        return f"{title}\n{chunk}"

    def executing(self, per: dict) -> dict:
        """切一篇文件：回傳 list[dict]，每個 dict 是一塊（metadata + doc_id + chunk_index + 文字）。"""
        # 依 separators 順序遞迴切分，每塊約 chunk_size 字元、相鄰塊重疊 chunk_overlap 字元
        chunked_data = self.splitter.split_text(per[self.split_target_key])
        base_meta_data = {meta_key: per.get(meta_key, "") for meta_key in self.metadata_keys}
        title = per.get(self.title_key, "")
        package = []
        for chunk_index, chunk in enumerate(chunked_data):
            chunk = self._add_title(chunk, title)
            body = {
                **base_meta_data,
                "doc_id": per[self.doc_id_key],
                "chunk_index": chunk_index+1,
                self.split_target_key: chunk
            }
            package.append(body)
        return package
    
    def executings(self) -> list[dict]:
        """切整份語料：對 self.full_data 的每篇文件呼叫 executing，回傳「每篇的切片清單」組成的 list。"""
        package = []
        for per in self.full_data:
            chunked_data = self.executing(per = per)
            package.append(chunked_data)
        return package

def pipeline(**objs: dict) -> dict[list]:
    # 依序處理每一份語料，回傳 {名稱: 該份語料切好的結果}
    results = {name: obj.executings() for name, obj in objs.items()}
    return results

def data_combiner(file_name_space: list[str]) -> dict:
    """依檔名清單讀入 data/corpus/ 下的 jsonl，回傳 {檔名: 該檔所有文件(list[dict])}。"""
    path_base = "data/corpus/{}"
    files = [get_data(path_base.format(file_name)) for file_name in file_name_space]
    files_dict = dict(zip(file_name_space, files))
    return files_dict

def get_data(path: str) -> list[dict]:
    """讀一個 jsonl 檔：一行一筆 JSON，回傳 list[dict]。"""
    with open(path, encoding='utf-8') as fp:
        datas = []
        for d in fp:
            d = json.loads(d)
            datas.append(d)
        return datas

def fetch_text_from_json(data: dict[list], split_target_key: str = "text") -> dict[str]:
    """把 pipeline 的巢狀結果 {語料: [文件: [塊]]} 三層攤平，只取每塊的 text，回傳 list[str]。
    （embedding 模型只吃字串清單，metadata 不需要送進去）
    注意：split_target_key 參數目前沒有生效，下面寫死了 "text"。
    """
    texts = []
    for d1 in data.values():
        for d2 in d1:
            for chunk in d2:
                text = chunk["text"]
                texts.append(text)
    return texts


# if __name__ == "__main__":

    








# if __name__ == "__main__":
#     data = get_data("data/corpus/attack.jsonl")

#     for d in data:
#         chunker_ = Chunker(
#                         raw_data=d,
#                         chunk_size=1000,
#                         chunk_overlap=200,
#                         separotors=["\n\n", "\n", ". ", " "], 
#                         add_start_index=False
#                    )
#         chunked_data = chunker_.executing(
#                                     split_target_key="text", 
#                                     doc_id_key="id",
#                                     metadata_keys=[
#                                         "id",
#                                         "block",
#                                         "source",
#                                         "title",
#                                         "section",
#                                         "url",
#                                         "license",
#                                         "retrieved_at",
#                                     ]
#                                 )
#     print(chunked_data)
        

    # print(Chunker(data,chunk_size=1000,chunk_overlap=200, separotors=["\n\n", "\n", ". ", " "], add_start_index=False))
        




    


    # @classmethod
    # def chunk(self):
    #     def split_text(text, seps):
    #         if len(text) <= LIMIT:
    #             return [text]
    #         if not seps:
    #             return [text[i:i + LIMIT] for i in range(0, len(text), LIMIT)]

    #         sep, rest = seps[0], seps[1:]
    #         if sep not in text:
    #             return split_text(text, rest)

    #         pieces = text.split(sep)
    #         result = []
    #         current = ""
    #         for p in pieces:
    #             candidate = p if not current else current + sep + p
    #             if len(candidate) <= LIMIT:
    #                 current = candidate
    #             else:
    #                 if current:
    #                     result.append(current)
    #                 if len(p) > LIMIT:
    #                     result.extend(split_text(p, rest))
    #                     current = ""
    #                 else:
    #                     current = p
    #         if current:
    #             result.append(current)
    #         return result
    #     def chunk_record(rec):
    #         chunks = []
    #         for i, piece in enumerate(split_text(rec["text"], SEPARATORS)):
    #             chunk = {k: v for k, v in rec.items() if k != "text"}   # metadata 原樣複製
    #             chunk["doc_id"] = rec["id"]
    #             chunk["chunk_index"] = i
    #             chunk["text"] = piece
    #             chunks.append(chunk)
    #         return chunks

    #     # DATA 是「很多筆記錄的清單」，chunk_record 一次只吃一筆，所以要逐筆處理再收集起來
    #     all_chunks = []
    #     for rec in TackMitigationsChunker.DATA:
    #         all_chunks.extend(chunk_record(rec))
    #     return all_chunks


# if __name__ == "__main__":   # 只有直接執行這個檔案時才跑，被別的檔案 import 時不會印東西
#     chunks = TackMitigationsChunker.chunk()
#     print("文件數:", len(TackMitigationsChunker.DATA), "| 總塊數:", len(chunks))
#     print("最長一塊:", max(len(c["text"]) for c in chunks), "字元（上限", LIMIT, "）")
#     print("第一塊 metadata:", {k: v for k, v in chunks[0].items() if k != "text"})