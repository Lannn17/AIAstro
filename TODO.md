# AIAstro — 待办事项

> 只记录未完成的内容。完成后移入 CHANGELOG.md，从此处删除。

---

## Stub 页面（路由已建，功能未实现）

- 🔨 合盘 Synastry（`/synastry`）— 已开发,待优化
- 🚧 推运 Progressions（`/progressions`）
- 🚧 太阳回归 Solar Return（`/solar-return`）- 3.27排期开发
- 🚧 方向法 Directions（`/directions`）

---

## 候选功能（待排期）
 # 重要
- 0. 本命盘分析的prompt格式优化 - flag
- 1. 推盘逻辑优化: 增加星盘计算层,差异化确定事件权重赋值 - checking
- ✅ ~~2. 开放注册功能,其他权限均与访客功能一致但允许注册用户保存自己输入的星盘在自己账号中.同时设置管理员账号,确保管理员可以读取所有用户保存上传的数据.~~
- 3. Mainland China地区端口设置配相应的国内版软件
- 4. 不确定分钟(但确定小时)的情况,调盘界面里不好选择.是否可以在校正之前先告诉用户在不确定的时间范围之内其本命盘配置变动的可能范围 
- 5. 本命盘标签优化:用户不理解这些标签具体是什么意思.设计为支持用户点击标签查看概念,如群星3宫意味着什么,等.
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

- 📋 二次推运实现
- 📋 太阳回归实现 -- prepare for developing
    回归地点的三种形式:优先默认开发当前所在地
    使用太阳回归盘和本命盘的叠加形式
- 📋 校正系统 v1.3+（更多技法、评分权重调优）
- 📋 RAG 质量持续优化（基于 analytics 数据反馈）
- 📋 行星解读缓存策略优化

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
- 2. 本命盘四交点无分析
- 3. 缓存标签出现后就无法再知道这段分析的生成模型了 需要将缓存标签和模型标签修复为不互斥 即可以共同显示两个标签
- 4. mobile UI本命盘行星界面行星名字未对齐
- ✅ ~~5. 注册用户密码没必要设置128位,改为最高16位~~
- ✅ ~~6. 注册后第一次进入界面时行运页面有两个星盘(一个未保存),去掉未保存星盘逻辑~~
- ✅ ~~注册用户保存的星盘直接存入主数据库,无需管理员核审 -- 此处应和访客逻辑相同,需要管理员核审~~
- 8. 检查和render的部署,为什么还在持续deploy
- ✅ ~~9. 本命盘标签简析存在为空的情况 未匹配return null,如何更好解决?~~ *(疑似解决)
- 10. 本命盘标签解析的静态映射完善:当前在解释群星的时候只是笼统说"多颗行星",需要结合用户实际的本命盘把具体是哪些行星填入 --群星解析已详细补充,其他tag依然存在该问题;同样是群星水瓶座,部分用户有具体行星的补充,部分用户依然是多颗行星的笼统描述
- ✅ ~~11. 群星xx座映射还是会出现英文 --fixing~~ 
- 12. 标签解读无缓存,重新加载后内容丢失,需要同样缓存该内容
- 13. 注册用户保存第二张以上星盘侧边栏未显示


## 非重要待优化项
- 侧边栏点击已保存星盘后,信息填入栏里仍然是上一张星盘的信息
- 本命盘页面UI优化(输入出生信息和显示星盘两个页面不要同时出现)


## Code Review
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
    建议拆分为：
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
    # 第一次定义（format_chart_summary 附近）
    _SIGN_ELEMENT = {"Aries": "火", "Leo": "火", ...}
    _SIGN_MODALITY = {"Aries": "开创", ...}

    # 第二次定义（analyze_planets 附近）
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
- 
