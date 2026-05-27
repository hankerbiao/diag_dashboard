import requests

response = requests.post(
    "http://10.17.150.235:8002/v1/embeddings",
    json={
        "input": "深度学习是机器学习的一个分支",
        "model": "qwen3-vl-embedding"
    }
)

result = response.json()
vector = result["data"][0]["embedding"]
print(f"向量维度: {len(vector)}")
print(f"向量前5位: {vector[:5]}")