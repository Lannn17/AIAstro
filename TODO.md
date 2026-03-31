# AIAstro — 待办事项

> 只记录未完成的内容。完成后移入 CHANGELOG.md，从此处删除。

---

## 手动增加了debug路由 需要review --0327

## Stub 页面（路由已建，功能未实现）

- 🔨 合盘 Synastry（`/synastry`）— 已开发,待优化UI和logic
- ✅ ~~太阳回归 Solar Return（`/solar-return`）— 实现完成，测试通过~~
- 🚧 方向法 Directions（`/directions`）
- 🚧 推运 Progressions（`/progressions`）

---

## 候选功能（待排期）
 # 重要
- 0. 本命盘分析的prompt格式优化 -- flag
    - 同一类解释里出现明显矛盾的内容时,二次rag检索并解释矛盾
    - 调用多次后AI解释详细程度明显下降,需要设计一套rule进一步规范输出,比如强制超过多少字数?
- 1. 推盘逻辑优化: 增加星盘计算层,差异化确定事件权重赋值 - checking
- ✅ ~~2. 开放注册功能,其他权限均与访客功能一致但允许注册用户保存自己输入的星盘在自己账号中.同时设置管理员账号,确保管理员可以读取所有用户保存上传的数据.~~
- 3. ✅ ~~Mainland China地区端口设置配相应的国内版软件 - 3.31排期~~ 代码已完成，待配置 API key：
  - [ ] `astrology_api/.env` 添加 `DEEPSEEK_API_KEY=...`（本地）
  - [ ] `frontend/.env` 创建并添加 `VITE_AMAP_KEY=...`（本地）
  - [ ] HuggingFace Spaces → Settings → **Secrets** 添加 `DEEPSEEK_API_KEY`（生产）
  - [ ] HuggingFace Spaces → Settings → **Variables** 添加 `VITE_AMAP_KEY`（生产，构建时注入）
- 4. 不确定分钟(但确定小时)的情况,调盘界面里不好选择.是否可以在校正之前先告诉用户在不确定的时间范围之内其本命盘配置变动的可能范围 
- ✅ ~~本命盘标签优化:用户不理解这些标签具体是什么意思.设计为支持用户点击标签查看概念,如群星3宫意味着什么,等.~~
- 6. 合盘列表关系维度全部显示并打分,将得分按从高到低排序并生成相应分析,解释得分高的关系为什么更可能形成以及为什么更难形成得分低的关系.合盘tag一并加入自由向AI提问对话的入口.
- 7. 合盘界面前端UI升级,双人行星相位列表分类描述,不要以长文字列表形式呈现,增强用户可读性和可理解性.(当前显示的原始数据列表可以折叠做成一个按钮,用户点击后可展开具体查看)
- 8. 同理本命盘界面关于人生主题的部分也应该显示全部领域并给出比例参考

# 次要
- 1. 允许用户输入职业身份,使AI输出的分析结果更具体
- 2. 增加验证数据集检验优化当前推盘模型算法
    - Step1 先导入10条数据
- 3. 增设用户反馈/打分功能,允许用户针对生成的分析内容的某个部分进行打分,校准或更新补充现实情况
- 4. 推盘step2&3的问卷不够合理,较难进行选择,需要优化
- 5. 合盘算法优化


- 📋 校正系统 v1.3+（更多技法、评分权重调优）
- 📋 RAG 质量持续优化（基于 analytics 数据反馈）
    - planet_sign & Aspect demands最高但Hit低, 可能AI已有相关储备常识,无需引用重复信息.增强:更具体的专业分析 - 3.31数据
- 📋 行星解读缓存策略优化(?)

---

## 代码清理（待决策）

> 以下为代码审查中发现的疑似冗余代码，暂未删除，待确认后处理。

- 📋 **遗留构建脚本**：`build_gemini_index.py`、`build_gemini_demo_index.py` — 早期用于构建 FAISS 索引，当前已切换至 Qdrant，可能已无用
- 📋 **stub 功能路由**：`progression_router.py`、`return_router.py`、`direction_router.py` — 对应前端 stub 页面，后端路由已注册但前端未接入，等待功能实现或决定是否保留
- 📋 **text_search.py 中未被导入的函数**：`get_sign_interpretation()`、`get_transit_interpretation()`、`get_natal_chart_interpretations()` — 当前无任何地方导入使用，可考虑删除
- 📋 **磁盘缓存模块** `app/core/cache.py` — 仅被 stub 功能路由间接使用，若 stub 路由移除则整个模块变为死代码
- 📋 **`/api/interpret` GET 端点**（`interpret_router.py`）— 使用旧版 TF-IDF 搜索，非 RAG，前端可能未调用

---

## 已知问题
- ✅ ~~1. 校对分析RAG分析遗留问题(引用未拆分,未出现RAG引用分析模块) -- 所有设置AI分析的端口服务都必须接入rag的分析接口~~
- 2. 本命盘四交点无分析 -- flag
- 3. 缓存标签出现后就无法再知道这段分析的生成模型了 需要将缓存标签和模型标签修复为不互斥 即可以共同显示两个标签
- 4. mobile UI本命盘行星界面行星名字未对齐
- ✅ ~~5. 注册用户密码没必要设置128位,改为最高16位~~
- ✅ ~~6. 注册后第一次进入界面时行运页面有两个星盘(一个未保存),去掉未保存星盘逻辑~~
- ✅ ~~注册用户保存的星盘直接存入主数据库,无需管理员核审 -- 此处应和访客逻辑相同,需要管理员核审~~
- 8. ~~检查和render的部署,为什么还在持续deploy - 已delete service~~
- ✅ ~~9. 本命盘标签简析存在为空的情况 未匹配return null,如何更好解决?~~ *(疑似解决)
- 10. 本命盘标签解析的静态映射完善:当前在解释群星的时候只是笼统说"多颗行星",需要结合用户实际的本命盘把具体是哪些行星填入 --群星解析已详细补充,其他tag依然存在该问题;同样是群星水瓶座,部分用户有具体行星的补充,部分用户依然是多颗行星的笼统描述
- ✅ ~~11. 群星xx座映射还是会出现英文 --fixing~~ 
- 12. 标签解读无缓存,重新加载后内容丢失,需要同样缓存该内容(?)
- 13. 注册用户保存第二张以上星盘侧边栏未显示
- 14. 检查当前是否有限制AI输出字数的字段
- 15. solar return有些用户自动生成的报告里分数异常,只有3or2 -- flag
- 16. 重新写一次readme.md
- 17. 太阳回归当前生效盘+可选年份 -- flag


## 非重要待优化项
- 侧边栏点击已保存星盘后,信息填入栏里仍然是上一张星盘的信息
- 本命盘页面UI优化(输入出生信息和显示星盘两个页面不要同时出现)


## Code Review
- 整体代码优化: 拆分大文件 -- flag
- 当前管理员使用.env明文写入密码,注册用户使用hash编码,逻辑不统一: 考虑管理员密码也进行hash
- 管理员uid=none,依赖uid的数据库操作可能报错: 考虑给管理员编码一个uid,或者管理员整条数据也编入数据库
- 加上注册防刷功能, rate limit: 初阶段构想是只开放20个注册账号(管理员除外),判断此构想如何
- 彻底去掉访客功能,访客访问要求访客先进行注册:现有is_guest名字全部改为is_approved.管理员审批功能保留.
- 多语言支持: 把所有硬编码转为使用独立翻译文件(e.g. i18n.py /locales目录存放翻译文件)
- interpret.py内代码拆分(检讨)
- 调用Ai次数限制: 目前考虑是每个调用接口只允许生成一次,结果存入该注册用户db,之后调用如果没有新信息就全部直接命中缓存,不额外消耗调用次数.管理员无限制
- 合盘缓存逻辑重构(现有逻辑混乱)
- interpret_chat错误处理打印完整trackback,其他路由只返回错误信息: 统一使用logging
- 合盘用了 MD5 做缓存键,和_log_analytics 里用的是 SHA256不一致: 分析并确定最终方案
- rag.py文件拆分 -- flag
    拆分为：
    text
    app/
    ├── rag/
    │   ├── __init__.py          # 导出公共接口
    │   ├── client.py            # Gemini 客户端 + fallback
    │   ├── retrieval.py         # retrieve(), _load(), Qdrant
    │   ├── prompts.py           # 所有 system prompts + prompt 构建
    │   ├── chart_summary.py     # format_chart_summary + 占星常量
    │   ├── chat.py              # chat_with_chart, summarize_messages
    │   ├── transit.py           # analyze_transits, analyze_active_transits_full
    │   ├── synastry.py          # analyze_synastry + schema
    │   ├── rectification.py     # analyze_rectification, generate_asc_quiz, calc_confidence
    │   ├── planets.py           # analyze_planets, _compute_chart_facts
    │   └── analytics.py         # classify_query
    2. 占星常量重复定义

    python
    ### 第一次定义（format_chart_summary 附近）
    _SIGN_ELEMENT = {"Aries": "火", "Leo": "火", ...}
    _SIGN_MODALITY = {"Aries": "开创", ...}

    ### 第二次定义（analyze_planets 附近）
    _SIGN_ELEMENT = {"Aries": "火", "Leo": "火", ...}   # ← 完全重复！
    _SIGN_MODE = {"Aries": "本始", ...}                  # ← 命名不同，且"开创"变成了"本始"
    "开创" vs "本始" — 这两个不一致，哪个是对的？

    3. classify_query 确认每次调 Gemini

    python
    def classify_query(query: str) -> str:
        resp = client.models.generate_content(...)  # ← 每次聊天额外 1 次 API 调用
    建议改成规则/关键词匹配：

    python
    def classify_query(query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["太阳在", "月亮在", "水星在"]):
            return "planet_sign"
        if any(w in q for w in ["第1宫", "第2宫", "宫位"]):
            return "planet_house"
        if any(w in q for w in ["合相", "四分", "三分", "对冲"]):
            return "aspect"
        if any(w in q for w in ["感情", "事业", "财运", "健康"]):
            return "life_area"
        if any(w in q for w in ["性格", "心理", "行为"]):
            return "psychological"
        if any(w in q for w in ["运势", "预测", "什么时候"]):
            return "prediction"
        return "other"
    4. _SYSTEM_PROMPT_RAG 和 _SYSTEM_PROMPT_INTERPRET 似乎已废弃

    python
    _SYSTEM_PROMPT_RAG = """..."""        # 还在用吗？
    _SYSTEM_PROMPT_INTERPRET = """..."""   # 还在用吗？
    _SYSTEM_PROMPT = _SYSTEM_PROMPT_RAG   # "兼容旧代码"
    _SYSTEM_PROMPT_UNIFIED = """..."""     # ← 当前实际在用
    如果只用 _SYSTEM_PROMPT_UNIFIED，其他三个可以删掉。

    5. generate() 函数可能已废弃

    generate() 使用的是旧版 _SYSTEM_PROMPT，而新代码都用 rag_generate() + _SYSTEM_PROMPT_UNIFIED。确认是否还有调用方。

    6. _MAIN_PLANETS vs _CORE_PLANETS 内容一样

    python
    _MAIN_PLANETS = {"Sun", "Moon", "Mercury", ...}  # format_chart_summary 用
    _CORE_PLANETS = {"sun", "moon", "mercury", ...}   # _compute_chart_facts 用
    内容一样但大小写不同，容易出 bug。应该统一。
- rag.py中system_prompt有旧代码名称疑似废弃,检查并删除,有关联的去掉关联直接使用新名字.
- classify_query考虑改成规则匹配减少AI调用次数
- 当前prompt清单, 考虑把所有prompt集成在一个单独文档里:
System Prompts（4 个，仅 1 个在用）
###	变量名	状态	用在哪
S1	_SYSTEM_PROMPT_RAG	⚪ 可能废弃	被 _SYSTEM_PROMPT 引用
S2	_SYSTEM_PROMPT_INTERPRET	⚪ 可能废弃	没找到调用方
S3	_SYSTEM_PROMPT	⚪ 可能废弃	仅 generate() 使用
S4	_SYSTEM_PROMPT_UNIFIED	🟢 在用	几乎所有业务函数
业务 Prompts（14 个）
###	所在函数	用途	状态
P1	classify_query()	问题分类（7 标签之一）	🟢 在用，建议改成规则匹配
P2	generate()	旧版 RAG 生成	⚪ 可能废弃（被 rag_generate 替代？）
P3	summarize_messages()	对话历史压缩摘要	🟢 在用
P4	chat_with_chart() — 普通模式	星盘对话（无行运）	🟢 在用
P5	chat_with_chart() — 行运模式	星盘对话（含行运上下文）	🟢 在用
P6	analyze_transits()	单次行运综合解读	🟢 在用
P7	analyze_active_transits_full() — 有新行运	逐相位解读 + overall	🟢 在用
P8	analyze_active_transits_full() — 全缓存	仅生成 overall	🟢 在用
P9	analyze_rectification()	出生时间校对 AI 解读	🟢 在用
P10	generate_asc_quiz()	上升星座鉴别问卷生成	🟢 在用
P11	calc_confidence()	候选时间置信度评估	🟢 在用
P12	analyze_planets() — 主 prompt	逐行星解读 + overall	🟢 在用（最长的 prompt）
P13	analyze_planets() — retry	补充遗漏行星的解读	🟢 在用
P14	analyze_synastry()	合盘六维分析	🟢 在用
总计
text
System Prompts:  4 个（建议清理为 1 个）
业务 Prompts:   14 个（建议清理掉 P1、P2，实际需维护 12 个）
──────────────────
总计:           18 个 → 清理后 13 个
建议修改优先级
优先级	Prompt	原因
🔴 先删/改	S1、S2、S3、P1、P2	废弃或应改成规则，减少干扰
🟠 重点优化	S4（_SYSTEM_PROMPT_UNIFIED）	影响所有输出质量的根基
🟠 重点优化	P12（analyze_planets）	最长、最复杂、用户最常用
🟠 重点优化	P14（analyze_synastry）	合盘解读核心
🟡 次优先	P7/P8（行运分析）	行运解读质量
🟡 次优先	P4/P5（对话）	对话体验
🟢 最后	P3、P6、P9-P11、P13	功能性 prompt，影响面小

- security.py安全隐患问题
###	问题	严重程度	建议
1	默认凭据无生产保护	🔴 严重	启动时校验 / 拒绝默认值
2	明文密码常驻内存	🔴 严重	预哈希后只保留 hash
3	SHA-256 null byte 截断	🟠 中等	使用 base64 编码
4	30 天无 refresh/revoke	🟠 中等	缩短有效期 + refresh token
5	uid claim 无类型校验	🟠 中等	添加 isinstance 检查
6	is_admin 仅基于用户名	🟠 中等	用 token claim 标识来源
7	密码长度检查不一致	🟡 轻微	抽取公共函数
8	缺少安全日志	🟡 轻微	添加 logging
9	bcrypt rounds 隐式	🟡 轻微	显式声明
10	语言混合	🟡 轻微	统一处理

- test_api.py是否还在使用
- 多个目录下都存在.env的问题

- embedding逻辑完善(rag chunking etc.)
🔴 严重问题
1. 文本分块按固定字符数切割，会截断词语和句子
python
CHUNK_SIZE = 600
OVERLAP    = 100

def chunk_text(text: str, source: str) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"text": chunk, "source": source, "start": start})
        start += CHUNK_SIZE - OVERLAP
    return chunks
问题：

固定 600 字符切割，完全不考虑词、句、段落边界
一个词可能被从中间切断："星座的特征是..." → "星座的特" + "征是..."
中文、葡萄牙文、英文的信息密度差异很大，600 字符对中文可能太多，对英文可能太少
截断的文本会严重影响 embedding 质量和检索准确性
建议： 按句子/段落边界切割：

python
import re

def chunk_text(text: str, source: str, max_size: int = 600, overlap: int = 100) -> list[dict]:
    """按段落和句子边界智能切割文本"""
    # 先按段落分割
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""
    current_start = 0

    for para in paragraphs:
        # 如果单个段落就超长，按句子进一步分割
        if len(para) > max_size:
            sentences = re.split(r'(?<=[.!?。！？\n])\s*', para)
            for sent in sentences:
                if len(current_chunk) + len(sent) + 1 > max_size and current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "source": source,
                        "start": current_start,
                    })
                    # 回退 overlap 量的文本
                    current_start += len(current_chunk) - overlap
                    current_chunk = current_chunk[-overlap:] if overlap else ""
                current_chunk += sent + " "
        elif len(current_chunk) + len(para) + 2 > max_size and current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "source": source,
                "start": current_start,
            })
            current_start += len(current_chunk) - overlap
            current_chunk = current_chunk[-overlap:] if overlap else ""
            current_chunk += para + "\n\n"
        else:
            current_chunk += para + "\n\n"

    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "source": source,
            "start": current_start,
        })

    return chunks
2. 没有任何错误处理，任何一步失败都会丢失所有进度
python
def main():
    chunks = load_all_chunks()           # 如果这里失败...
    # ...
    model = SentenceTransformer(MODEL_NAME)  # 下载失败？
    vectors = model.encode(...)          # OOM？中途断电？
    index.add(vectors)
    faiss.write_index(index, str(INDEX_FILE))  # 磁盘满了？
问题：

如果 encode 到一半 OOM，之前几十分钟的计算全部丢失
如果模型下载中断，没有重试机制
如果磁盘写入失败，可能留下损坏的半成品文件
建议： 添加分步缓存和错误处理：

python
import sys

def main():
    # Step 1: Chunking (带缓存)
    print("=== Step 1: Loading and chunking ===")
    if CHUNKS_FILE.exists():
        print(f"Reusing existing {CHUNKS_FILE}")
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    else:
        chunks = load_all_chunks()
        if not chunks:
            print("ERROR: No chunks generated. Check data/processed_texts/")
            sys.exit(1)
        with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)

    # Step 2: Encoding (带缓存)
    vectors_cache = INDEX_DIR / "vectors.npy"
    if vectors_cache.exists():
        print(f"Reusing cached vectors from {vectors_cache}")
        vectors = np.load(vectors_cache)
    else:
        print(f"\n=== Step 2: Loading model: {MODEL_NAME} ===")
        try:
            model = SentenceTransformer(MODEL_NAME)
        except Exception as e:
            print(f"ERROR: Failed to load model: {e}")
            sys.exit(1)

        texts = [f"passage: {c['text']}" for c in chunks]
        vectors = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=True,
            convert_to_numpy=True,
        ).astype(np.float32)
        np.save(vectors_cache, vectors)

    # Step 3: Build index (原子写入)
    print(f"\n=== Step 3: Building FAISS index ===")
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    tmp_index = INDEX_DIR / "index.faiss.tmp"
    faiss.write_index(index, str(tmp_index))
    tmp_index.rename(INDEX_FILE)  # 原子替换，避免损坏
    print(f"Index saved: {INDEX_FILE}  (dim={dim}, total={index.ntotal})")
🟠 中等问题
3. CHUNK_SIZE 和 OVERLAP 未考虑模型的 token 限制
python
CHUNK_SIZE = 600   # 字符数
OVERLAP    = 100
问题： E5-small 的最大序列长度是 512 tokens。600 个字符在英文中大约 120-150 tokens，但在中文中可能达到 300-600 tokens（每个汉字通常是 1-2 个 token）。对于中文文本，600 字符可能超出模型容量，超出部分会被静默截断，导致信息丢失。

建议： 基于 token 数而非字符数进行分块：

python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
MAX_TOKENS = 480  # 留一些余量给 "passage: " 前缀

def chunk_text_by_tokens(text: str, source: str) -> list[dict]:
    sentences = re.split(r'(?<=[.!?。！？\n])\s*', text)
    chunks = []
    current_tokens = []
    current_text = ""
    start = 0

    for sent in sentences:
        sent_tokens = tokenizer.encode(sent, add_special_tokens=False)
        if len(current_tokens) + len(sent_tokens) > MAX_TOKENS and current_text:
            chunks.append({"text": current_text.strip(), "source": source, "start": start})
            start += len(current_text)
            current_tokens = []
            current_text = ""
        current_tokens.extend(sent_tokens)
        current_text += sent + " "

    if current_text.strip():
        chunks.append({"text": current_text.strip(), "source": source, "start": start})

    return chunks
4. IndexFlatIP 对大数据集无扩展性
python
index = faiss.IndexFlatIP(dim)
问题： IndexFlatIP 是暴力搜索，时间复杂度 O(n)。当前数据量小时没问题，但如果文本量增长到几十万 chunks，查询延迟会线性增长。

建议： 预留切换到近似索引的能力：

python
def build_index(vectors: np.ndarray) -> faiss.Index:
    dim = vectors.shape[1]
    n = vectors.shape[0]

    if n < 10_000:
        # 小数据集：暴力搜索足够
        print(f"Using IndexFlatIP (n={n} < 10k)")
        index = faiss.IndexFlatIP(dim)
    else:
        # 大数据集：IVF 近似搜索
        nlist = min(int(np.sqrt(n)), 256)
        print(f"Using IndexIVFFlat (n={n}, nlist={nlist})")
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(vectors)
        index.nprobe = min(nlist // 4, 32)

    index.add(vectors)
    return index
5. model_info.json 信息不足，缺少可复现性关键数据
python
with open(MODEL_INFO_FILE, "w") as f:
    json.dump({
        "model": MODEL_NAME,
        "dim": dim,
        "total": index.ntotal,
        "prefix": "query: "
    }, f)
问题： 缺少构建时间、chunk 参数、数据源信息等，无法判断索引是否过时或如何复现。

建议：

python
import datetime

model_info = {
    "model": MODEL_NAME,
    "dim": dim,
    "total": index.ntotal,
    "query_prefix": "query: ",
    "document_prefix": "passage: ",
    "chunk_size": CHUNK_SIZE,
    "chunk_overlap": OVERLAP,
    "index_type": "IndexFlatIP",
    "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source_files": [f.name for f in sorted(TEXTS_DIR.glob("*.txt")) if f.name not in SKIP],
    "faiss_version": faiss.__version__ if hasattr(faiss, '__version__') else "unknown",
}

with open(MODEL_INFO_FILE, "w", encoding="utf-8") as f:
    json.dump(model_info, f, ensure_ascii=False, indent=2)
6. 文件名打印时的编码处理方式奇怪
python
print(f"  {f.name[:60].encode('ascii', errors='replace').decode()}: {len(chunks)} chunks")
问题： 把非 ASCII 字符替换成 ?，对于中文/葡文文件名毫无可读性。

建议： 现代终端都支持 UTF-8，直接打印：

python
print(f"  {f.name}: {len(chunks)} chunks")
如果确实担心终端编码问题：

python
try:
    print(f"  {f.name}: {len(chunks)} chunks")
except UnicodeEncodeError:
    print(f"  {f.name!r}: {len(chunks)} chunks")
🟡 轻微问题 / 改进建议
7. SKIP 集合硬编码，不灵活
python
SKIP = {"exemplo_interpretacoes.txt"}
建议： 支持配置或模式匹配：

python
SKIP_PATTERNS = {"exemplo_*", "test_*", "README*"}

import fnmatch

def should_skip(filename: str) -> bool:
    return any(fnmatch.fnmatch(filename, pat) for pat in SKIP_PATTERNS)
8. 没有输入数据验证
python
def load_all_chunks() -> list[dict]:
    files = sorted(TEXTS_DIR.glob("*.txt"))
    print(f"Found {len(files)} text files")
问题： 如果 TEXTS_DIR 不存在或为空，程序会静默返回空列表，后续步骤在空数据上继续运行。

建议：

python
def load_all_chunks() -> list[dict]:
    if not TEXTS_DIR.exists():
        raise FileNotFoundError(
            f"Text directory not found: {TEXTS_DIR}\n"
            f"Run data preprocessing first."
        )

    files = sorted(TEXTS_DIR.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt files found in {TEXTS_DIR}")

    print(f"Found {len(files)} text files")
    # ...
9. 缺少内存预估
问题： 对于大量文本，用户无法预知是否有足够内存。

建议： 添加预估信息：

python
def main():
    chunks = load_all_chunks()
    
    estimated_memory_mb = len(chunks) * 384 * 4 / (1024 * 1024)  # dim=384, float32
    print(f"Estimated memory for vectors: {estimated_memory_mb:.1f} MB")
10. 缺少命令行参数支持
全部配置硬编码，不方便调试和实验。

建议：

python
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Build FAISS index with E5 model")
    parser.add_argument("--texts-dir", type=pathlib.Path, default=TEXTS_DIR)
    parser.add_argument("--index-dir", type=pathlib.Path, default=INDEX_DIR)
    parser.add_argument("--chunk-size", type=int, default=600)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--force", action="store_true", help="Rebuild even if cache exists")
    return parser.parse_args()
📊 问题汇总
###	问题	严重程度	类别
1	固定字符数切割截断词句	🔴 严重	检索质量
2	无错误处理，无断点恢复	🔴 严重	健壮性
3	未考虑模型 512 token 限制	🟠 中等	正确性
4	FlatIP 无扩展性	🟠 中等	可扩展性
5	model_info 信息不足	🟠 中等	可复现性
6	文件名编码处理不当	🟠 中等	可读性
7	SKIP 硬编码	🟡 轻微	灵活性
8	无输入数据验证	🟡 轻微	健壮性
9	缺少内存预估	🟡 轻微	用户体验
10	无命令行参数	🟡 轻微	可用性

- main.py使用状况(硬编码version?)
- migrate_to_qdrant.py使用状况
- astrology_api中的readme.md使用状况
- requirements.lock作用?和.txt区别
- runtime.txt
- 