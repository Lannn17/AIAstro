# AIAstro — 待办事项

> 只记录未完成的内容。完成后移入 CHANGELOG.md，从此处删除。

---

## Stub 页面（路由已建，功能未实现）
- 🔨 合盘 Synastry（`/synastry`）— 已开发,待优化UI和logic
- 月亮推运 Progressions --排期4.6
核心概念
text
次限推运: 出生后第 N 天的星盘 = 人生第 N 年的内在状态
推运月亮: 约 2.5 年换一个星座，反映"人生情绪季节"

例: 用户今年 30 岁
  → 取出生后第 30 天的月亮位置
  → 该位置的星座/宫位 = 当前内心情绪主题
产品设计建议
1）情绪时间轴（核心交互）
text
┌──────────────────────────────────────────────────┐
│  🌙 你的情绪季节地图                                │
│                                                    │
│  ──●────────●────────●────────●────────●──        │
│   2020     2022     2024     2026     2028        │
│   ♋巨蟹    ♌狮子    ♌狮子    ♍处女    ♍处女        │
│   内在安全   自我表达   自我表达   务实整理  务实整理    │
│                       ↑                            │
│                    你在这里                          │
│                                                    │
│  📖 当前阶段: 推运月亮在狮子座第5宫                    │
│  "这是一个渴望被看见、需要创造性表达的阶段..."           │
└──────────────────────────────────────────────────┘
2）推运月亮与本命行星的相位事件
python
# 后端数据结构建议
progressed_moon_events = [
    {
        "date": "2025-03",
        "event": "推运月亮合本命金星",
        "aspect": "conjunction",
        "orb": 0.5,
        "theme": "relationships",
        "interpretation": "情感关系迎来柔软的新篇章...",
        "duration": "2025-01 ~ 2025-05",  # 推运相位持续时间长
    },
    {
        "date": "2025-09",
        "event": "推运月亮刑本命土星",
        "aspect": "square",
        "orb": 1.2,
        "theme": "emotional_pressure",
        "interpretation": "内心可能感受到责任与情感的张力...",
        "duration": "2025-07 ~ 2025-11",
    },
]
3）与太阳回归联动
text
💡 关键洞察: 推运月亮 + 太阳回归 = 内外呼应

太阳回归告诉你: "今年外在世界会发生什么"
月亮推运告诉你: "今年内心会经历什么"

产品上可以做:
┌────────────────────────────────────────┐
│  2025 年度双视角                         │
│                                        │
│  🔆 外在主题 (太阳回归)                   │
│  → 事业扩张、健康纪律、沟通重塑            │
│                                        │
│  🌙 内在主题 (月亮推运)                   │
│  → 自我表达的渴望、创造力觉醒              │
│                                        │
│  🔗 联动解读:                            │
│  "事业扩张的外在机遇，恰好呼应了内心        │
│   渴望被看见的情绪周期，今年是将内在         │
│   创造力转化为职业突破的最佳时机"           │
└────────────────────────────────────────┘
4）规则引擎设计思路
python
# 类似 solar_return.py 的架构

_PROG_MOON_SIGN_THEMES = {
    "Aries":   {"keywords": ["重新出发", "勇气", "独立"], "element": "fire"},
    "Taurus":  {"keywords": ["安定", "感官享受", "积累"], "element": "earth"},
    "Cancer":  {"keywords": ["归属感", "家庭", "情感安全"], "element": "water"},
    # ...
}

_PROG_MOON_HOUSE_THEMES = {
    "1":  "重新定义自我认同",
    "4":  "家庭与内在根基的重建",
    "5":  "创造力与自我表达的觉醒",
    "7":  "关系模式的深层转变",
    "10": "社会角色与使命感的情绪共振",
    # ...
}

def compute_progressed_moon(natal_data, current_age):
    """
    1. 计算推运月亮当前位置（星座/宫位/度数）
    2. 计算推运月亮与本命行星的相位
    3. 计算推运月亮换座时间表
    4. 生成情绪阶段解读
    """
    pass


---

- 每日运势
1）卡片信息层次
text
┌─────────────────────────────────────┐
│  📅 2025年6月15日 星期日               │
│                                     │
│  🌙 月亮在天蝎座                      │
│  今日情绪色彩: 深沉、洞察、转化          │
│                                     │
│  ⭐ 今日关键星象                       │
│  ┌─────────────────────────────┐    │
│  │ 金星三分木星 (精确)            │    │
│  │ 人际关系与社交中有愉悦的能量流动  │    │
│  └─────────────────────────────┘    │
│                                     │
│  🎯 对你的个人影响                     │
│  行运木星正经过你的第7宫               │
│  → 今天适合主动拓展社交圈              │
│                                     │
│  💡 今日一句                          │
│  "信任直觉带来的深层洞察"              │
│                                     │
│  ┌────────┐  ┌────────┐            │
│  │ 📤 分享  │  │ 📝 记录  │            │
│  └────────┘  └────────┘            │
└─────────────────────────────────────┘
2）信息架构
text
Layer 1: 通用层 (所有用户相同)
├── 当日月亮星座 + 情绪基调
├── 主要行星相位 (精确相位 orb < 1°)
└── 全局能量关键词

Layer 2: 个人化层 (基于本命盘)
├── 今日行运触发了你的哪个宫位
├── 行运行星与本命行星的相位
└── 个人化建议

后端架构:
# app/rag/daily_card.py

from datetime import date
from functools import lru_cache

@lru_cache(maxsize=1)  # 通用层每天只算一次
def compute_daily_universal(target_date: date) -> dict:
    """所有用户共享的当日星象"""
    return {
        "moon_sign": "Scorpio",
        "moon_phase": "waning_crescent",
        "major_aspects": [
            {"planet1": "venus", "planet2": "jupiter", 
             "aspect": "trine", "orb": 0.3,
             "keywords": ["social_harmony", "abundance"]},
        ],
        "void_of_course": {"start": "14:30", "end": "18:45"},
        "daily_keywords": ["洞察", "社交", "转化"],
    }

def compute_daily_personal(target_date: date, natal_data: dict) -> dict:
    """个人化的行运触发"""
    transits = get_current_transits(target_date)
    natal_planets = natal_data["planets"]
    
    personal_hits = []
    for transit in transits:
        for natal_key, natal_planet in natal_planets.items():
            aspect = check_aspect(transit["longitude"], 
                                   natal_planet["longitude"], orb=2.0)
            if aspect:
                personal_hits.append({
                    "transit_planet": transit["name"],
                    "natal_planet": natal_key,
                    "natal_house": natal_planet["house"],
                    "aspect": aspect,
                    "theme": infer_theme(transit, natal_key, aspect),
                })
    
    return {
        "personal_transits": personal_hits,
        "focus_house": most_activated_house(personal_hits),
        "energy_level": estimate_energy(personal_hits),
    }
策略:
┌─────────────────────────────────────────────┐
│  通用层: 每天凌晨定时任务预计算                   │
│  → 缓存到 Redis/DB，所有用户共享                │
│                                             │
│  个人层: 基于规则引擎实时计算                     │
│  → 纯 Python 计算，不调 LLM（毫秒级）           │
│                                             │
│  文案层: 模板 + 变量填充                        │
│  → 预写 100+ 模板，根据星象组合选择              │
│  → 只在"深度解读"时才调 LLM                     │
└─────────────────────────────────────────────┘
python
# 文案模板示例（不依赖 LLM）
_TRANSIT_TEMPLATES = {
    ("jupiter", "trine", "natal_venus"): [
        "社交与人际关系中有温暖的能量流动，适合主动联络重要的人",
        "今天的人际互动可能带来意想不到的愉悦与机遇",
    ],
    ("saturn", "square", "natal_moon"): [
        "情绪上可能感到些许沉重，给自己留出独处空间是明智的",
        "内心的责任感与情感需求之间需要找到平衡点",
    ],
}
5）社交裂变设计
text
分享卡片 → 生成精美图片 → 朋友看到 → 想知道自己的 → 注册

┌─────────────────────────┐
│  [精美背景图]              │
│                         │
│  🌙 6月15日 天蝎月亮       │
│  "信任直觉带来的深层洞察"   │
│                         │
│  ⭐ 金星三分木星            │
│  今日关键词: 社交·丰盛·洞察  │
│                         │
│  ── [App Logo] ──       │
│  扫码查看你的个人星运 →     │
└─────────────────────────┘
考虑增加其他内容

- 占星骰子 --pending

📚 历史记录:
  "你最近 10 次掷骰，金星出现了 4 次"
  → "近期你的核心关切似乎集中在价值与关系领域


## 候选功能（待排期）
 # 重要
- 0. **本命盘分析的prompt格式优化** -- IMPORTANT FLAG--4.2测试感觉输出很良好
    - 同一类解释里出现明显矛盾的内容时,二次rag检索并解释矛盾
    - 调用多次后AI解释详细程度明显下降,需要设计一套rule进一步规范输出,比如强制超过多少字数?
    '''
    Prompt 格式优化
Step 1: 矛盾检测与二次检索
python
# 方案：在 AI 输出后加一层 self-consistency check

class InterpretationPipeline:
    async def generate_with_consistency(self, chart_data, rag_context):
        # 第一轮：正常生成
        raw_output = await self.llm.generate(
            system_prompt=NATAL_SYSTEM_PROMPT,
            user_prompt=self._build_prompt(chart_data, rag_context)
        )
        
        # 第二轮：矛盾检测
        contradiction_check = await self.llm.generate(
            system_prompt=CONTRADICTION_DETECTOR_PROMPT,
            user_prompt=f"""
            以下是对同一张本命盘的多段分析，请识别其中是否存在明显矛盾：
            
            {raw_output}
            
            如果发现矛盾，请：
            1. 指出具体哪两段内容矛盾
            2. 说明矛盾的来源（例如：土星限制 vs 木星扩张作用于同一宫位）
            3. 给出整合解读（说明这种张力在实际生活中如何表现）
            
            如果没有矛盾，返回 "NO_CONTRADICTION"
            """
        )
        
        if "NO_CONTRADICTION" not in contradiction_check:
            # 二次 RAG 检索：针对矛盾点精准检索
            contradiction_topics = self._extract_topics(contradiction_check)
            additional_context = await self.rag.search(
                queries=contradiction_topics,
                top_k=3,
                filter={"type": "aspect_integration"}  # 专门检索"整合性"解读
            )
            
            # 第三轮：整合生成
            final_output = await self.llm.generate(
                system_prompt=INTEGRATION_PROMPT,
                user_prompt=f"""
                原始分析：{raw_output}
                矛盾点：{contradiction_check}
                补充参考资料：{additional_context}
                
                请重新整合以上内容，保留原始分析的有效部分，
                对矛盾点给出专业的整合解读。
                """
            )
            return final_output
        
        return raw_output
Step 2: 输出详细度规范
python
# 设计分层输出规范

OUTPUT_RULES = {
    "natal_planet_interpretation": {
        "min_chars": 200,      # 每颗行星解读最少200字
        "max_chars": 500,
        "required_sections": [
            "核心含义",          # 这颗行星在此星座/宫位的本质
            "具体表现",          # 在日常生活中如何体现
            "成长方向",          # 如何利用或平衡这个能量
        ],
        "forbidden_patterns": [
            r"总之.*",          # 禁止空洞总结
            r"需要注意.*平衡",   # 禁止万能废话
        ]
    },
    "natal_aspect_interpretation": {
        "min_chars": 150,
        "max_chars": 400,
        "required_sections": [
            "相位能量描述",
            "内在心理动力",
            "外在事件倾向",
        ]
    },
    "synastry_aspect": {
        "min_chars": 120,
        "max_chars": 350,
        "required_sections": [
            "互动模式",
            "可能的摩擦点",
            "关系建议",
        ]
    }
}

# 在 system prompt 中注入
def build_system_prompt(interpretation_type: str) -> str:
    rules = OUTPUT_RULES[interpretation_type]
    return f"""
    你是一位专业占星师。请严格遵循以下输出规范：
    
    【字数要求】每段解读 {rules['min_chars']}-{rules['max_chars']} 字
    【必含段落】每段解读必须包含以下部分，用加粗标题标注：
    {chr(10).join(f'  - **{s}**' for s in rules['required_sections'])}
    
    【禁止事项】
    - 不要使用空洞总结句
    - 不要给出不基于具体星盘配置的泛泛建议
    - 如果多次调用，每次输出的详细程度必须一致
    
    【质量标准】
    - 每个论点必须关联到具体的行星、星座或宫位
    - 使用"因为你的[行星]在[星座/宫位]，所以..."的论证结构
    """
Step 3: 多次调用质量一致性
python
# 问题根源：temperature 随机性 + token budget 不稳定
# 解决方案：锁定关键参数 + 输出后验证

class QualityGuard:
    def __init__(self):
        self.min_length_ratio = 0.7  # 输出不能低于预期长度的70%
    
    async def guarded_generate(self, prompt, expected_min_chars, max_retries=2):
        for attempt in range(max_retries + 1):
            response = await self.llm.generate(
                prompt=prompt,
                temperature=0.7,        # 固定，不要每次变
                max_tokens=2048,        # 给足空间
                presence_penalty=0.3,   # 鼓励多样性但不跑题
            )
            
            if len(response) >= expected_min_chars * self.min_length_ratio:
                return response
            
            # 不够详细，追加要求
            prompt += "\n\n【注意：你的回答过于简短，请展开详细论述每个要点。】"
        
        return response  # 最终兜底
        '''



- 1. 推盘逻辑优化
    - 增加星盘计算层,差异化确定事件权重赋值 - checking
    - 校正逻辑:用户确认的时间范围内如果本身就没有出现配置的变化,弹出提示
    - 推盘step2&3的问卷不够合理,较难进行选择,需要优化
- ✅ ~~3. Mainland China地区端口设置配相应的国内版软件 - ~~ 
- 4. 不确定分钟(但确定小时)的情况,调盘界面里不好选择.是否可以在校正之前先告诉用户在不确定的时间范围之内其本命盘配置变动的可能范围 
- 6. 合盘列表关系维度全部显示并打分,将得分按从高到低排序并生成相应分析,解释得分高的关系为什么更可能形成以及为什么更难形成得分低的关系.合盘tag一并加入自由向AI提问对话的入口.
- 7. 合盘界面前端UI升级,双人行星相位列表分类描述,不要以长文字列表形式呈现,增强用户可读性和可理解性.(当前显示的原始数据列表可以折叠做成一个按钮,用户点击后可展开具体查看)
- 8. 同理本命盘界面关于人生主题的部分也应该显示全部领域并给出比例参考
- ✅ ~~10. 设计用户留言反馈窗口,用户可提出意见,在TURSO中增加一张收集建议的表单~~
- 11. 增加用户使用引导和每个功能的用处等介绍
- 12. 新的每日小功能开发. 涉及整个主页UI修改

# 次要
- 1. 允许用户输入职业身份,使AI输出的分析结果更具体
- 2. 增加验证数据集检验优化当前推盘模型算法
    - Step1 先导入10条数据 --pending
- 3. 增设用户反馈/打分功能,允许用户针对生成的分析内容的某个部分进行打分,校准或更新补充现实情况 --打分评估功能合并在Prompt evaluate section
- 5. 合盘算法优化 --Need more details


- 📋 校正系统 v1.3+（更多技法、评分权重调优） --waiting for more dataset
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
- ✅ ~~本命盘四交点无分析 --二次测试失败 --~~
- ✅ ~~缓存标签出现后就无法再知道这段分析的生成模型了 需要将缓存标签和模型标签修复为S不互斥 即可以共同显示两个标签~~
- 4. mobile UI本命盘行星界面行星名字未对齐
- ✅ ~~5. 注册用户密码没必要设置128位,改为最高16位~~
- ✅ ~~6. 注册后第一次进入界面时行运页面有两个星盘(一个未保存),去掉未保存星盘逻辑~~
- ✅ ~~注册用户保存的星盘直接存入主数据库,无需管理员核审 -- 此处应和访客逻辑相同,需要管理员核审~~
- ✅ ~~检查和render的部署,为什么还在持续deploy~~ - 已delete service
- ✅ ~~9. 本命盘标签简析存在为空的情况 未匹配return null,如何更好解决?~~ *(疑似解决)
- ✅ ~~10. 本命盘标签解析的静态映射完善:当前在解释群星的时候只是笼统说"多颗行星",需要结合用户实际的本命盘把具体是哪些行星填入 --群星解析已详细补充,其他tag依然存在该问题;同样是群星水瓶座,部分用户有具体行星的补充,部分用户依然是多颗行星的笼统描述~~
- ✅ ~~11. 群星xx座映射还是会出现英文 --fixing~~ 
- ✅ ~~13. 注册用户保存第二张以上星盘侧边栏未显示~~
- ✅ ~~检查当前是否有限制AI输出字数的字段~~
- ✅ ~~solar return有些用户自动生成的报告里分数异常,只有3or2~~
- ✅ ~~重新写一次readme.md~~
- ✅ ~~太阳回归当前生效盘+可选年份~~
- ✅ ~~18. 行运优先显示最新发生的,并以标签形式突出展现.(生成行运时读取缓存,缓存中没有的条目打上最新的标签.)另外确认行运缓存逻辑,该轮行运结束后清空缓存.~~
- ✅ ~~19. 现在任何人都可以/admin访问rag分析报告,加一个权限,仅限管理员访问.~~
- ✅ ~~20. 完全去掉访客入口,所有用户必须注册才能使用~~
- 21. Prompt管理界面问题 --checking
    - 存在显示限制无法完全显示prompt全文
    - 当前每生成一次就记录为一版新的草稿,prompt本身根本没有任何变化.逻辑错误.
    - generate的prompt似乎无法测试,只能测试各个具体业务的prompt.优化对比逻辑
- ✅ ~~主页tag位置调整,把太阳回归放在行运之后,推运名称改为月亮推运,放在太阳回归之后~~
- ✅ ~~24. 增加checkbox:用户输入星盘信息时,在出生时间输出栏附近增加checkbox让用户确认是否可以肯定该出生时间精确到分钟,如果可以确认则打勾,并说明清楚该数据将会被收集用于训练模型进行出生时间校正,如果不确定则推荐用户去测试校正功能~~
- ✅ ~~25. 当前用/admin方式进入的查看rag分析的界面,访问方式修改,改为集成到管理员界面中的管理tag中.~~
- 26. 骰子有历史记录但是用户无法读取.接入数据库,增加查看按钮允许用户读取历史记录(24H前端储存逻辑依然适用)


## 非重要待优化项
- 侧边栏点击已保存星盘后,信息填入栏里仍然是上一张星盘的信息
- 本命盘页面UI优化(输入出生信息和显示星盘两个页面不要同时出现)


## Code Review
- 当前管理员使用.env明文写入密码,注册用户使用hash编码,逻辑不统一: 考虑管理员密码也进行hash
- 管理员uid=none,依赖uid的数据库操作可能报错: 考虑给管理员编码一个uid,或者管理员整条数据也编入数据库
- 加上注册防刷功能, rate limit: 初阶段构想是只开放20个注册账号(管理员除外),判断此构想如何
- 现有is_guest名字全部改为is_approved.管理员审批功能保留.
- 多语言支持: 把所有硬编码转为使用独立翻译文件(e.g. i18n.py /locales目录存放翻译文件)
- interpret.py内代码拆分(检讨)
- 调用Ai次数限制: 目前考虑是每个调用接口只允许生成一次,结果存入该注册用户db,之后调用如果没有新信息就全部直接命中缓存,不额外消耗调用次数.管理员无限制
- 合盘缓存逻辑重构(现有逻辑混乱)
- interpret_chat错误处理打印完整trackback,其他路由只返回错误信息: 统一使用logging
- 合盘用了 MD5 做缓存键,和_log_analytics 里用的是 SHA256不一致: 分析并确定最终方案
- ✅ ~~rag.py文件拆分~~（拆分为 app/rag/ 包，含 10 个子模块 + __init__.py re-export）
- ✅ ~~rag.py中system_prompt有旧代码名称疑似废弃，检查并删除~~（已删除 S1/S2/S3，generate() 改用 UNIFIED）
- ✅ ~~classify_query考虑改成规则匹配减少AI调用次数~~（已改为关键词规则匹配）

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

- embedding逻辑完善(rag chunking etc.) --排期4.3 flag
参考prompt:
# Task: Build an intelligent RAG chunking pipeline for astrology reference books

## Context

I have a collection of astrology reference books as `.txt` files in `data/processed_texts/`. 
These are primarily in **English and Portuguese**. I need you to build a robust chunking 
and indexing pipeline that maximizes RAG retrieval quality.

## Step 1: Analyze Every Text File's Structure

Before writing ANY chunking code, read every `.txt` file in `data/processed_texts/` 
(skip `exemplo_interpretacoes.txt`) and analyze each one's structure. For each file, identify:

1. **Language** (English or Portuguese)
2. **Heading/chapter patterns** — how does this specific file mark sections? Examples:
   - `Chapter 1: ...`, `CHAPTER ONE`, `Part II`
   - `Capítulo 3`, `CAPÍTULO III`, `Seção 2`
   - Markdown `## Heading`, numbered `1.2.3`, ALL CAPS lines
   - Zodiac sign names as headers (`ARIES`, `Áries`, `Touro`)
   - Planet names as headers (`The Sun`, `O Sol`)
   - House numbers (`First House`, `Casa 1`)
3. **Paragraph separation** — double newlines? Single newlines? Indentation?
4. **Special structures** — bullet lists, tables, numbered lists, aspect descriptions,
   degree meanings, delineation blocks (e.g., "Sun in Aries: ...")
5. **Abbreviations used** — e.g., `Asc.`, `Desc.`, `conj.`, `opp.`, `sq.`, `p.`, `vol.`
6. **Average paragraph length and density**

Output your analysis as a structured summary for each file before proceeding.

## Step 2: Design Per-File or Per-Pattern Chunking Strategies

Based on your analysis, design chunking rules. Key principles:

- **Never cut mid-sentence.** Always break at sentence boundaries.
- **Never cut across section/chapter headings.** A chunk must belong to one section.
- **Preserve paragraph integrity** when possible — prefer breaking between paragraphs.
- **Handle abbreviations correctly** — `Dr.`, `Sr.`, `e.g.`, `i.e.`, `p.ex.`, `p.` (page), 
  astrological abbreviations like `Asc.` should NOT be treated as sentence endings.
- **Detect and preserve structured blocks** — if a file has delineation entries like 
  "Sun in Aries: [interpretation text]", each entry should ideally be one chunk or stay intact.
- **Prepend section context** — each chunk should carry its section/chapter title as metadata,
  AND optionally prepend a brief context header to the chunk text itself, e.g.:
  `[Source: western_astrology.txt | Chapter: The Twelve Houses | Section: Fifth House]`

## Step 3: Implement Parent-Child Chunking Architecture

Build a two-tier chunking system:

- **Parent chunks** (~1500-2000 chars): larger context blocks, returned to the LLM
- **Child chunks** (~400-600 chars): smaller retrieval units, used for vector search
- Each child records its `parent_id`
- At retrieval time: search children → return their parent texts to LLM

## Step 4: Build the Index

Using model `intfloat/multilingual-e5-small`:
- Encode all **child chunks** with `"passage: "` prefix
- Build a FAISS `IndexFlatIP` index (vectors are normalized → cosine similarity)
- Also tokenize all child chunks for **BM25** (use nltk stopwords for en/pt, 
  preserve astrology terms as a whitelist — generate this whitelist by extracting 
  domain terms you find in the actual texts)

## Step 5: Output Files

Save to `data/enhanced_index/`:
- `parents.json` — all parent chunks with metadata
- `children.json` — all child chunks with `parent_id` and metadata
- `children.faiss` — FAISS index of child embeddings
- `bm25_tokens.json` — tokenized corpus for BM25
- `model_info.json` — model name, dim, counts, prefixes
- `chunking_report.json` — your analysis from Step 1 + stats per file 
  (number of sections detected, parents, children, avg chunk sizes)

## Constraints

- Python 3.11+
- Dependencies available: `sentence-transformers`, `faiss-cpu`, `numpy`, `nltk`, `rank_bm25`
- The pipeline must be runnable as: `cd astrology_api && python build_enhanced_index.py`
- All code in a single file is fine, but separate a `chunking.py` module if it exceeds 300 lines
- Add detailed logging so I can verify the chunking quality
- If any file has a structure you can't confidently parse, log a warning and fall back 
  to conservative paragraph-based chunking

## Quality Checks

After building, run a self-test:
- Print 3 random parent chunks and their children for manual inspection
- Print chunk size distribution (min, max, mean, median, p95) for both parents and children
- Flag any chunks that are suspiciously short (<50 chars) or long (>3000 chars)
- Verify every child has a valid parent_id that exists in parents
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