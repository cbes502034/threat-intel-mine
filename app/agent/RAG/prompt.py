"""提示詞組裝：把「檢索到的片段」與「使用者問題」合成一段文字，交給 Claude。"""

def build_prompt(chunks, question):
    """chunks：片段文字的 list[str]；question：使用者問題。
    輸出格式（片段編號從 1 開始，答案裡的 [1][2] 就對應這個編號）：
        檢索資料 :
        [1]	片段一
        [2]	片段二

        使用者提問 :
        問題
    """
    retrieval = "檢索資料 :\n"
    for index, chunk in enumerate(chunks):
        index = f"[{index+1}]\t"        # enumerate 從 0 開始，+1 讓編號從 1 開始
        new_chunk = index + chunk
        retrieval = retrieval + new_chunk + "\n\n"
    question = "使用者提問 :\n" + question + "\n\n"
    prompts = retrieval + question
    return prompts
