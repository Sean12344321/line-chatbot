from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (MessageEvent, TextMessage, TextSendMessage,)
from scrap import search_amazon
import os, requests
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np

load_dotenv()

client = OpenAI()
line_bot_api = LineBotApi(os.getenv('LINE_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_SECRET'))
app = Flask(__name__)

@app.post("/")
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("電子簽章錯誤, 請檢查密鑰是否正確？")
        abort(400)
    return 'OK'

error_text = """
輸入格式錯誤！請依照以下格式重新輸入：
第一行是商品名稱（關鍵字）。
第二行是商品描述。
第三行是價格範圍（例如 "5000-10000"），這一行可以不填。

範例:
跑步機
想在家運動，找一台折疊式跑步機，噪音小又不占空間。
5000-10000
"""

search_text = "正在為您搜尋，請稍後……"
embedding_text = "正在尋找關係，請稍後……"

def short_url(url):
    try:
        api_url = "https://tinyurl.com/api-create.php"
        params = {"url": url}
        response = requests.get(api_url, params=params)
        if response.status_code == 200:
            return response.text
        else:
            return f"縮短失敗，HTTP 狀態碼: {response.status_code}"
    except Exception as e:
        return f"發生錯誤: {e}"

def call_openai(inputs):
    """
    inputs: list of strings (支持批次處理多個文字)
    """
    response = client.embeddings.create(
        input=inputs,
        model="text-embedding-ada-002"
    )
    embeddings = [data.embedding for data in response.data]
    return embeddings


def cosine_similarity(embedding1, embedding2):
    """計算兩個嵌入的餘弦相似度"""
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    return dot_product / (norm1 * norm2)

def find_top_k_similar(items, embeddings, target_embedding, top_k=3):
    """
    找到與目標嵌入最相近的前 K 個項目
    
    :param items: 原始的 items 列表
    :param embeddings: 嵌入的列表，與 items 順序一致
    :param target_embedding: 要比較的目標嵌入
    :param top_k: 要返回的相似項目數
    :return: 最相近的前 K 個 item["href"]
    """
    similarities = []
    for i, embedding in enumerate(embeddings[:-1]):  # 避免跟自己比較
        sim = cosine_similarity(embedding, target_embedding)
        similarities.append((sim, items[i]["href"]))
    
    # 按相似度排序，取前 K 項
    similarities = sorted(similarities, key=lambda x: x[0], reverse=True)
    return [href for _, href in similarities[:top_k]]


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    lines = event.message.text.split('\n')
    if len(lines) == 3:
        keyword, description, cost = lines
    elif len(lines) == 2:
        keyword, description = lines
        cost = "null"
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=error_text))
        return
    # 生成描述
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=search_text))
    items = search_amazon(keyword)
    if cost.find("-") != -1:
        min_cost, max_cost = map(int, cost.split('-'))
        items = [item for item in items if min_cost <= item["price"] <= max_cost]
    if len(items) == 0:
        line_bot_api.push_message(event.source.user_id, TextSendMessage(text="沒有找到符合的商品！"))
        return
    line_bot_api.push_message(event.source.user_id, TextSendMessage(text=embedding_text))
    batched_items = [item["name"] for item in items]
    batched_items.append(description)
    embeddings = call_openai(batched_items)
    target_embedding = embeddings[-1]
    top_3_hrefs = find_top_k_similar(items, embeddings, target_embedding, top_k=3)
    final_urls = ""
    for url in top_3_hrefs:
        final_urls += short_url(url) + "\n"
    line_bot_api.push_message(event.source.user_id, TextSendMessage(text=final_urls))
    print("回覆成功！")
    

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)