"""
gen_genre_tags — 网文流派标签系统 Skill

从 StoryForge 移植，77条起点/纵横/晋江流派分类。
on_before_scene_write() 注入流派约束到 prompt_payload。

流派元数据：反模式(antiPatterns)、节奏策略(pacingStrategy)、典型结构(typicalStructure)
"""

from core.base_skill import BaseSkill

# ── 流派数据库 ───────────────────────────────────────────────────────────────
# Ported from StoryForge genre-metadata.ts + prompt-seeds-genre-packs.ts

GENRE_DB = {
  "玄幻": {
    "antiPatterns": [
      "退婚流废柴逆袭",
      "跳崖捡秘籍+戒指老爷爷",
      "拍卖行捡漏",
      "空洞打脸（无细节只说好强）",
      "反派降智衬托主角"
    ],
    "pacingStrategy": "情绪流优先：先立人设→做情绪→铺剧情。每10章小高潮，爽点从物理打脸升级为逻辑碾压和智力对决",
    "typicalStructure": "废材逆袭 → 奇遇不断 → 越级挑战 → 称霸一域 → 飞升上界",
    "worldRules": [
      "修炼等级体系",
      "功法/丹药/法宝",
      "宗门/家族/散修"
    ]
  },
  "修仙": {
    "antiPatterns": [
      "传统凡人流纯修仙（市场占比<5%）",
      "万年老怪夺舍失败",
      "废灵根其实是神级",
      "修炼=闭关打坐嗑药",
      "飞升=换地图重来"
    ],
    "pacingStrategy": "融合创新是唯一出路：赛博修仙/职场修仙/直播修仙。拒绝纯修炼升级，用幻想外壳装现实内核",
    "typicalStructure": "炼气 → 筑基 → 金丹 → 元婴 → 化神 → 飞升",
    "worldRules": [
      "灵根资质",
      "灵气浓度",
      "天劫",
      "长生追求"
    ]
  },
  "洪荒": {
    "antiPatterns": [
      "鸿钧合道万能解释",
      "圣人满地走不值钱",
      "先天灵宝路边捡",
      "量劫=换个地图打怪"
    ],
    "pacingStrategy": "神话事件驱动+量劫为大节点。拒绝鸿钧万能论，重在博弈和因果，圣人必须有限制",
    "typicalStructure": "穿越洪荒 → 拜师/立教 → 量劫博弈 → 证道成圣",
    "worldRules": [
      "先天/后天灵宝",
      "天道/大道规则",
      "圣人/准圣体系"
    ]
  },
  "武侠": {
    "antiPatterns": [
      "跳崖捡秘籍",
      "内力=万能能量无上限",
      "正邪二元脸谱化",
      "武林大会排名战"
    ],
    "pacingStrategy": "恩怨情仇驱动+武功层次渐升。拒绝数值化，重在意境和代价。融合新元素如盗墓/悬疑/职场",
    "typicalStructure": "灭门/奇遇 → 拜师学艺 → 江湖恩怨 → 复仇/归隐",
    "worldRules": [
      "内功/外功体系",
      "门派正邪",
      "朝廷/江湖关系"
    ]
  },
  "都市": {
    "antiPatterns": [
      "兵王回归",
      "歪嘴战神神医下山",
      "霸总虐恋带球跑",
      "主角赚钱=炒股炒房",
      "系统万能许愿机"
    ],
    "pacingStrategy": "都市脑洞异能赛道爆发：摆烂式逆袭+发疯式打脸。绑定现实痛点（职场PUA/35岁危机/租房压力）",
    "typicalStructure": "身份揭晓 → 商战崛起 → 红颜知己 → 商业帝国",
    "worldRules": [
      "现代都市",
      "商业规则",
      "势力分布"
    ]
  },
  "校园": {
    "antiPatterns": [
      "学霸校霸全员单箭头恋爱脑",
      "考试全靠作弊无人发现",
      "校园霸凌被主角一拳解决"
    ],
    "pacingStrategy": "日常+成长事件交替。拒绝恋爱脑全员单箭头，重在人物弧光和真实校园感",
    "typicalStructure": "入学/转学 → 日常 → 危机/竞赛 → 毕业/成长",
    "worldRules": [
      "校园规则",
      "师生/同学关系",
      "考试/升学体系"
    ]
  },
  "重生": {
    "antiPatterns": [
      "全知全能毫无挫折",
      "炒股炒房赚钱流",
      "抄歌抄书抄电影",
      "前世记忆=无敌攻略本"
    ],
    "pacingStrategy": "先知优势逐步释放+每个优势带来新麻烦。拒绝炒股炒房，爽点来自智性对抗而非先知全知",
    "typicalStructure": "死亡 → 重生回关键节点 → 改变命运 → 新的代价",
    "worldRules": [
      "前世记忆",
      "命运/蝴蝶效应",
      "时间线限制"
    ]
  },
  "系统流": {
    "antiPatterns": [
      "开局无敌系统万能许愿",
      "系统任务和主线两张皮",
      "系统只给奖励不给惩罚",
      "系统代替主角思考"
    ],
    "pacingStrategy": "系统+职业深度绑定（法医/考古/制瓷）。系统增加限制而非消除限制，与世界观深度融合",
    "typicalStructure": "绑定系统 → 新手任务 → 惩罚机制 → 系统真相",
    "worldRules": [
      "任务/奖励/惩罚机制",
      "系统等级/权限",
      "系统目的"
    ]
  },
  "末世": {
    "antiPatterns": [
      "主角永远不缺物资",
      "丧尸无脑弱智排队送",
      "一人建起末日帝国",
      "觉醒=全系异能无代价"
    ],
    "pacingStrategy": "生存危机层层加码+资源越来越稀缺。觉醒能力必须有代价，拒绝一人建起末日帝国",
    "typicalStructure": "灾难爆发 → 逃生/觉醒 → 基地建设 → 势力争霸",
    "worldRules": [
      "丧尸/变异体规则",
      "物资/幸存者分布",
      "觉醒/进化体系"
    ]
  },
  "废土": {
    "antiPatterns": [
      "高科技随便修不用解释",
      "核辐射=超能力批发",
      "一人重建文明"
    ],
    "pacingStrategy": "探索→发现→危机→升级装备循环推进。科技修复需要真实知识储备，拒绝凭空修高科技",
    "typicalStructure": "避难所出发 → 废土探索 → 势力接触 → 文明重建",
    "worldRules": [
      "辐射/污染规则",
      "残余科技",
      "变异生态"
    ]
  },
  "进化": {
    "antiPatterns": [
      "进化=全属性提升无副作用",
      "一次进化解决所有问题",
      "进化方向单一化"
    ],
    "pacingStrategy": "每次进化伴随形态/心智改变。进化不是全面buff而是代价与收益的抉择，拒绝单向强化",
    "typicalStructure": "环境异变 → 个体觉醒 → 种族进化 → 新物种文明",
    "worldRules": [
      "进化树/分支",
      "基因锁",
      "物种竞争"
    ]
  },
  "科幻": {
    "antiPatterns": [
      "黑科技无代价无副作用",
      "科学原理凭空捏造",
      "外星文明=人类翻版"
    ],
    "pacingStrategy": "科技设定渐进展开不信息轰炸。用科学思维推演剧情而非凭空造黑科技。硬核科幻需有真实学科依据",
    "typicalStructure": "未来设定 → 冲突/危机 → 技术探索 → 文明抉择",
    "worldRules": [
      "科技树",
      "未来社会形态",
      "物理规则"
    ]
  },
  "赛博朋克": {
    "antiPatterns": [
      "义体=超能力无副作用",
      "大公司=纯恶无理由",
      "黑客=万能钥匙秒破一切"
    ],
    "pacingStrategy": "高科技低生活的对比张力+阴谋层层剥开。义体改造伴随人性流失，拒绝义体=超能力",
    "typicalStructure": "街头任务 → 发现阴谋 → 对抗巨企 → 颠覆/妥协",
    "worldRules": [
      "义体/网络技术",
      "企业/帮派势力",
      "赛博空间规则"
    ]
  },
  "星际": {
    "antiPatterns": [
      "星际战争=星球排队被灭",
      "外星文明只有好坏二元",
      "人类永远是宇宙中心"
    ],
    "pacingStrategy": "宇宙尺度文明博弈+接触逐步升级。每个文明有独立逻辑，拒绝人类中心主义",
    "typicalStructure": "走出母星 → 星系探索 → 文明交锋 → 银河格局重塑",
    "worldRules": [
      "超光速规则",
      "文明等级",
      "星系政治"
    ]
  },
  "悬疑": {
    "antiPatterns": [
      "凶手是路人甲毫无铺垫",
      "侦探灵光一闪全解",
      "降智警察衬托主角"
    ],
    "pacingStrategy": "规则怪谈：强设定+快节奏+智斗。每章留绝境钩子，拒绝侦探灵光一闪",
    "typicalStructure": "案件发生 → 线索收集 → 推理排除 → 反转 → 真凶",
    "worldRules": [
      "案件逻辑",
      "人物动机",
      "时间线"
    ]
  },
  "灵异": {
    "antiPatterns": [
      "鬼=只会吓人不讲逻辑",
      "道士万能一张符全解",
      "恐怖感=突然跳出来吓人"
    ],
    "pacingStrategy": "恐怖感逐步升级+规则从模糊到清晰。鬼/灵有独立逻辑，拒绝道士万能一张符全解",
    "typicalStructure": "遭遇异常 → 探索规则 → 对抗/化解 → 真相揭示",
    "worldRules": [
      "鬼/灵的规则",
      "阴阳两界",
      "克制手段与代价"
    ]
  },
  "盗墓": {
    "antiPatterns": [
      "墓里全是宝贝没危险",
      "主角自带考古百科全知",
      "机关=永远能被破解"
    ],
    "pacingStrategy": "下墓→发现→危险→脱险循环推进。每墓一大关有独立文明背景。拒绝墓里全是宝贝没危险",
    "typicalStructure": "获取线索 → 组队下墓 → 机关/生物 → 墓主真相",
    "worldRules": [
      "风水/机关体系",
      "倒斗行规",
      "古墓文明"
    ]
  },
  "克苏鲁": {
    "antiPatterns": [
      "san值归零=发疯（简化处理）",
      "古神可以被主角打败",
      "恐怖=触手+黏液堆砌"
    ],
    "pacingStrategy": "认知缓慢崩塌+正常与疯狂的边界模糊。拒绝san值归零=发疯的简化处理，重在不可名状",
    "typicalStructure": "接触异常 → 调查 → 认知坍塌 → 不可名状的真相",
    "worldRules": [
      "san值/理智",
      "旧神/外神体系",
      "不可名状的知识"
    ]
  },
  "历史": {
    "antiPatterns": [
      "现代价值观强加古人",
      "发明大全穿越者（造肥皂/火药/玻璃）",
      "把古人写成傻子降智衬托",
      "抄唐诗宋词碾压古代文人"
    ],
    "pacingStrategy": "考据流是出路：无系统无金手指，靠专业知识在真实历史规则里博弈。拒绝抄诗/造肥皂/降智古人",
    "typicalStructure": "穿越/重生 → 立足 → 参与历史 → 改变格局",
    "worldRules": [
      "真实历史框架",
      "制度/官制",
      "经济/技术条件"
    ]
  },
  "种田": {
    "antiPatterns": [
      "种什么一夜暴富",
      "技术碾压=全知全能",
      "零挫折平推发展"
    ],
    "pacingStrategy": "缓慢积累+四季交替节奏。技术升级需要时间和投入，拒绝种什么一夜暴富",
    "typicalStructure": "获得土地/空间 → 开垦建设 → 收成/扩张 → 势力形成",
    "worldRules": [
      "农业/手工业规则",
      "季节/气候",
      "领地/声望体系"
    ]
  },
  "言情": {
    "antiPatterns": [
      "误会三章不解开",
      "失忆+替身文学+带球跑",
      "男二永远备胎无自我",
      "霸总虐恋"
    ],
    "pacingStrategy": "无CP/女性悬疑崛起，追更率超甜宠文30%。女主不恋爱不卑微，智商在线独立解决问题",
    "typicalStructure": "相遇 → 误会/冲突 → 感情升温 → 危机 → 和解/HE",
    "worldRules": [
      "人际关系网",
      "社会阶层",
      "时代背景"
    ]
  },
  "总裁": {
    "antiPatterns": [
      "总裁对全世界冷只对女主暖",
      "契约婚姻变真爱",
      "女主傻白甜靠男主拯救"
    ],
    "pacingStrategy": "情感转折点密集+人物弧光清晰。拒绝傻白甜+霸总虐恋，女主也必须有独立事业线",
    "typicalStructure": "契约/偶遇 → 互相试探 → 误会/危机 → 追妻/和解",
    "worldRules": [
      "商业/豪门规则",
      "家族关系",
      "契约/法律约束"
    ]
  },
  "宫斗": {
    "antiPatterns": [
      "降智对手排队送人头",
      "皇帝独宠一人",
      "靠运气上位无代价"
    ],
    "pacingStrategy": "步步为营+每级晋升都付出血的代价。联盟和背叛基于利益而非脸谱化善恶",
    "typicalStructure": "入宫 → 立足 → 争宠/联盟 → 宫变/上位 → 权倾后宫",
    "worldRules": [
      "后宫制度/位份",
      "家族势力",
      "前朝后宫关联"
    ]
  },
  "快穿": {
    "antiPatterns": [
      "每个世界套路完全相同",
      "系统发任务无目的",
      "主角在每个世界都无敌"
    ],
    "pacingStrategy": "世界难度递增+任务与主角本体关联逐渐揭晓。拒绝每世界换皮重来，要有贯穿全篇的真相线",
    "typicalStructure": "绑定系统 → 世界1 → 任务完成 → 世界N → 系统真相",
    "worldRules": [
      "穿越规则",
      "任务/积分体系",
      "世界之间的关联"
    ]
  },
  "轻小说": {
    "antiPatterns": [
      "对话冗长无推进全靠水",
      "开后宫毫无逻辑",
      "主角=读者投影无个性"
    ],
    "pacingStrategy": "快节奏对话+场景切换+日常与事件交替。对话必须有推进，拒绝水字数",
    "typicalStructure": "日常 → 事件 → 成长 → 关系进展 → 新日常",
    "worldRules": [
      "学院/异世界",
      "能力等级",
      "人际圈"
    ]
  },
  "游戏": {
    "antiPatterns": [
      "主角数值无限膨胀",
      "游戏只有主角在玩",
      "全服第一装备靠运气捡"
    ],
    "pacingStrategy": "虚拟现实+电竞职业化。升级节奏与装备/技能解锁同步，拒绝数值膨胀",
    "typicalStructure": "进入游戏 → 职业选择 → 副本攻略 → 公会/国战 → 游戏真相",
    "worldRules": [
      "游戏系统规则",
      "职业体系",
      "经济系统"
    ]
  },
  "竞技": {
    "antiPatterns": [
      "主角永远碾压无对手",
      "比赛=报比分无过程",
      "天才光环掩盖所有努力"
    ],
    "pacingStrategy": "训练→比赛→失败→突破→再战循环。重在竞技过程和策略博弈，拒绝主角永远碾压",
    "typicalStructure": "入门 → 天赋展露 → 关键比赛 → 职业生涯巅峰",
    "worldRules": [
      "项目规则",
      "职业体系",
      "训练/伤病"
    ]
  },
  "军事": {
    "antiPatterns": [
      "主角光环一人灭全军",
      "敌军无脑排队送人头",
      "战争=主角个人秀"
    ],
    "pacingStrategy": "战役递进从局部到全局。战略和后勤同样重要，拒绝主角光环一人灭全军",
    "typicalStructure": "参军/入伍 → 战斗成长 → 独立指挥 → 战略级博弈",
    "worldRules": [
      "军队体系/军衔",
      "武器装备",
      "战略/战术"
    ]
  },
  "无限流": {
    "antiPatterns": [
      "副本之间无关联",
      "能力获取无代价",
      "主神=纯工具人无动机"
    ],
    "pacingStrategy": "副本难度递增+能力成长与代价同步+各副本关联逐渐揭晓。拒绝副本拼凑和主神纯工具人",
    "typicalStructure": "进入空间 → 副本1 → 能力获取 → 副本N → 真相揭露",
    "worldRules": [
      "主神/系统规则",
      "副本机制",
      "兑换体系"
    ]
  },
  "规则怪谈": {
    "antiPatterns": [
      "规则矛盾被读者发现",
      "靠运气破局",
      "怪谈纯恐怖无逻辑",
      "主角莫名知道所有规则"
    ],
    "pacingStrategy": "开局抛致命规则→放两条矛盾规则制造冲突→留绝境钩子。智斗驱动，每章至少一次规则解读或触犯",
    "typicalStructure": "进入怪谈空间 → 解读规则 → 触犯/规避 → 破局 → 下一关（难度递增+规则关联逐渐揭晓）",
    "worldRules": [
      "规则=天道碎片/上古筛选机制",
      "违反即死无例外",
      "破译规则=获得资源",
      "怪谈之间有隐藏关联"
    ]
  },
  "发疯文": {
    "antiPatterns": [
      "发疯=乱写无逻辑",
      "主角无来由发疯",
      "缺乏情感内核",
      "单纯破坏不建设"
    ],
    "pacingStrategy": "压抑积累→触发点爆发→发疯破局→打碎规则建立新秩序。爽感来自对不合理规则的破坏",
    "typicalStructure": "被规则压制 → 积累压抑 → 触发事件 → 发疯爆发 → 打碎旧规则 → 建立新秩序",
    "worldRules": [
      "主角拒绝内卷不合作",
      "发疯是清醒的抵抗而非失控",
      "每次发疯都有情感触发点",
      "破坏旧规则的同时必须建立新规则"
    ]
  },
  "家族修仙": {
    "antiPatterns": [
      "个人英雄主义",
      "家族=背景板",
      "代际忽略",
      "单主角打怪升级"
    ],
    "pacingStrategy": "群像叙事+资源经营+代际接力。每一代人都有出生成长牺牲，前赴后继薪尽火传",
    "typicalStructure": "家族立足 → 资源争夺 → 代际接力 → 血脉崛起 → 长生仙族（群像，非单人）",
    "worldRules": [
      "血缘纽带=唯一可信任关系",
      "灵脉/丹药/灵田经营是核心驱动力",
      "修真路径相克需用人命试错",
      "魔道大行互相吞噬补全道基"
    ]
  }
}

DEFAULT_GENRE = "玄幻"


class GenGenreTagsSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "流派标签系统"
        self.current_genre = DEFAULT_GENRE

    def on_init(self) -> None:
        # Try to read genre from config
        import json
        config_path = self.context.workspace._config_path if hasattr(self.context.workspace, "_config_path") else None
        if config_path is None:
            from pathlib import Path
            cfg = Path(__file__).parent.parent.parent / "config.json"
            if cfg.exists():
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_genre = data.get("genre", DEFAULT_GENRE)

        self.context.set_shared("genre_config", {
            "current": self.current_genre,
            "available": list(GENRE_DB.keys()),
        })
        print(f"  [✓] {self.name} 已就绪（流派: {self.current_genre}, 共{len(GENRE_DB)}种）")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """注入流派约束到 prompt。如果 genre_knowledge 已注入，跳过。"""
        if self.context.get_shared("unified_genre_injected"):
            return prompt_payload  # genre_knowledge.py already handles this
        genre = self.context.get_shared("genre_config", {}).get("current", self.current_genre)
        meta = GENRE_DB.get(genre, GENRE_DB[DEFAULT_GENRE])

        genre_block = f"""
[系统流派约束 · {genre}]
- 避免套路: {', '.join(meta['antiPatterns'])}
- 节奏要求: {meta['pacingStrategy']}
- 世界规则: {', '.join(meta['worldRules'])}
"""
        prompt_payload.append(genre_block)
        return prompt_payload

    def set_genre(self, genre: str):
        """切换流派"""
        if genre in GENRE_DB:
            self.current_genre = genre
            self.context.set_shared("genre_config", {"current": genre, "available": list(GENRE_DB.keys())})
            print(f"  [✓] 流派切换为: {genre}")
        else:
            print(f"  [⚠️] 未知流派: {genre}，可用: {list(GENRE_DB.keys())}")
