"""
test_turso_vec.py — 验证 Turso 上 sqlite-vec 扩展是否可用
运行：venv/Scripts/python test_turso_vec.py
"""
import os, struct, base64, requests
from dotenv import load_dotenv

load_dotenv()

TURSO_URL   = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

if not TURSO_URL or not TURSO_TOKEN:
    raise RuntimeError("请在 .env 中设置 TURSO_DATABASE_URL 和 TURSO_AUTH_TOKEN")

api_url = TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline"
headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}


def turso_exec(sql, args=None):
    stmt = {"sql": sql}
    if args:
        stmt["args"] = args
    payload = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
    r = requests.post(api_url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    result = r.json()["results"][0]
    if result["type"] != "ok":
        raise RuntimeError(f"Turso error: {result}")
    return result["response"]["result"]


def vec_to_blob_arg(vector: list[float]) -> dict:
    """float32 列表 → Turso blob 参数"""
    b = struct.pack(f"{len(vector)}f", *vector)
    return {"type": "blob", "base64": base64.b64encode(b).decode()}


print("=== Step 1: 检查 sqlite-vec 版本 ===")
try:
    r = turso_exec("SELECT vec_version()")
    val = r["rows"][0][0]["value"]
    print(f"✅ sqlite-vec 可用，版本: {val}")
except Exception as e:
    print(f"❌ sqlite-vec 不可用: {e}")
    exit(1)

print("\n=== Step 2: 创建测试向量表 ===")
try:
    turso_exec("DROP TABLE IF EXISTS _vec_test")
    turso_exec("CREATE VIRTUAL TABLE _vec_test USING vec0(embedding float[4])")
    print("✅ vec0 虚拟表创建成功")
except Exception as e:
    print(f"❌ 创建失败: {e}")
    exit(1)

print("\n=== Step 3: 插入测试向量 ===")
try:
    v1 = vec_to_blob_arg([0.1, 0.2, 0.3, 0.4])
    turso_exec("INSERT INTO _vec_test(rowid, embedding) VALUES (1, ?)", [v1])
    v2 = vec_to_blob_arg([0.9, 0.8, 0.7, 0.6])
    turso_exec("INSERT INTO _vec_test(rowid, embedding) VALUES (2, ?)", [v2])
    print("✅ 向量插入成功")
except Exception as e:
    print(f"❌ 插入失败: {e}")
    exit(1)

print("\n=== Step 4: KNN 查询 ===")
try:
    query_vec = vec_to_blob_arg([0.1, 0.2, 0.3, 0.4])
    r = turso_exec(
        "SELECT rowid, distance FROM _vec_test WHERE embedding MATCH ? AND k = 2 ORDER BY distance",
        [query_vec],
    )
    rows = r["rows"]
    print(f"✅ KNN 查询成功，结果：")
    for row in rows:
        rowid = row[0]["value"]
        dist  = row[1]["value"]
        print(f"   rowid={rowid}, distance={dist}")
except Exception as e:
    print(f"❌ 查询失败: {e}")
    exit(1)

print("\n=== Step 5: 清理测试表 ===")
turso_exec("DROP TABLE IF EXISTS _vec_test")
print("✅ 清理完成")

print("\n🎉 所有测试通过，可以开始迁移！")
