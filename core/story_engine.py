"""
Novel-Claude — 故事结构引擎 (Story Engine)

题材 × 风格 → 27B 可执行的写作约束

原则:
  - 题材决定故事引擎（升级链、冲突模式、反派体系）
  - 风格决定叙事模式（情绪曲线、节奏、视角、对话占比）
  - 输出 ≤5 条实战约束，零 Dramatica 术语
  - 所有模式来源于万订作者访谈/起点编辑/社区共识，不编造

数据来源:
  - 起点编辑青狐: 题材边界感理论
  - 万订作者白蘸糖: 情节循环公式
  - 知乎网文创作方法论: 骨肉血模型
  - xs91/什么值得买/CSDN 网文专栏: 爽文结构拆解
  - POLARIS 2026: 人类参照锚定
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ══════════════════════════════════════════════════════════════════════
# 题材 → 故事引擎
# ══════════════════════════════════════════════════════════════════════

@dataclass
class GenreEngine:
    """题材的故事引擎参数"""
    genre: str
    upgrade_chain: str      # 升级链 — 主角通过什么变强
    conflict_pattern: str   # 冲突模式 — 矛盾如何逐层放大
    antagonist_system: str  # 反派体系 — 敌人从哪来，怎么升级
    core_appeal: str        # 核心爽点 — 读者为什么付费
    pace_reference: str     # 节奏参照 — 对标哪类万订作品

# 32 个题材的故事引擎（来源：编辑青狐、万订作者访谈、社区拆书）
GENRE_ENGINES: Dict[str, GenreEngine] = {
    # ── 幻想大类 ──
    "修仙": GenreEngine(
        genre="修仙",
        upgrade_chain="境界突破式 — 练气→筑基→金丹→元婴→化神→渡劫→大乘，每破境对应新地图和更强敌人",
        conflict_pattern="打了小的来老的→灭宗门引出皇朝→渡天劫引来上界关注→飞升后面对仙界势力",
        antagonist_system="同级竞争者→宗门宿敌→魔道巨头→天劫→上界天敌",
        core_appeal="弱者一步步站到世界之巅，每破一境全场震惊",
        pace_reference="《凡人修仙传》— 底层伪灵根→散修→飞升，节奏绵密，步步为营",
    ),
    "玄幻": GenreEngine(
        genre="玄幻",
        upgrade_chain="位面爬升式 — 大陆→王国→帝国→神界→万界，每次换地图战力翻倍",
        conflict_pattern="家族被灭→退婚羞辱→获得金手指→越级挑战→称霸大陆→飞升上界→诸天万界",
        antagonist_system="家族仇敌→宗门对手→王国势力→上界使者→诸天神魔",
        core_appeal="废材逆袭打脸，扮猪吃虎，越级碾压，全场震惊",
        pace_reference="《斗破苍穹》— 退婚→三年之约→中州→斗帝，高密度爽点",
    ),
    "洪荒": GenreEngine(
        genre="洪荒",
        upgrade_chain="先天跟脚+功德+法宝 — 跟脚决定起点，功德换天道认可，法宝决定战力天花板",
        conflict_pattern="量劫轮回→巫妖大战→封神大劫→西游量劫，每次大劫重塑天地秩序",
        antagonist_system="同辈大能→巫/妖对立阵营→天道圣人博弈→天道意志本身",
        core_appeal="洪荒神话重构，熟知的仙神在全新框架下博弈",
        pace_reference="《佛本是道》— 洪荒流鼻祖，天道圣人为棋手，众生为棋子",
    ),
    "家族修仙": GenreEngine(
        genre="家族修仙",
        upgrade_chain="家族血脉+资源经营 — 灵根决定个体上限，家族整体实力才是真正的战力",
        conflict_pattern="家族没落→内忧外患→获取传承→培养子弟→扩张领地→对抗宗门→跻身顶级世家",
        antagonist_system="同城敌对家族→宗门压榨→妖兽威胁→修仙界格局",
        core_appeal="一人得道 → 全族飞升，家族群像各有高光",
        pace_reference="《我们的家族没落了》— 献祭-赐福系统，暗黑地牢+领主种田",
    ),
    "星际": GenreEngine(
        genre="星际",
        upgrade_chain="文明跃迁式 — 行星文明→恒星文明→星系文明→宇宙文明，技术/资源/疆域三维升级",
        conflict_pattern="资源危机→发现新技术→文明碰撞→星际战争→统一星域→面对宇宙级威胁",
        antagonist_system="敌对舰队→异星文明→AI叛乱→宇宙灾难→高维存在",
        core_appeal="人类文明在星辰大海中崛起，技术碾压和舰队对决",
        pace_reference="星际种田+太空歌剧，技术爬升曲线驱动剧情",
    ),
    "末世": GenreEngine(
        genre="末世",
        upgrade_chain="三阶段跃迁 — 求生基建(1-30章)→扩张建城(31-90章)→秩序定义(91-150章)",
        conflict_pattern="天灾降临→资源匮乏→人性博弈→建立据点→统一势力→对抗灾变源头",
        antagonist_system="丧尸/变异兽→敌对幸存者势力→灾变源头→幕后操控者",
        core_appeal="废墟中重建文明，从被动求生到主动定义规则",
        pace_reference="《天灾求生》— 签到系统+基建可视化+体系化防御质变",
    ),
    "废土": GenreEngine(
        genre="废土",
        upgrade_chain="资源驱动式 — 废品→零件→装备→载具→基地，所有升级绑定实物资源",
        conflict_pattern="辐射区求生→拾荒贸易→组建车队→占领据点→军阀混战→重建秩序",
        antagonist_system="变异生物→掠夺者帮派→军阀→旧世界残余势力→环境本身",
        core_appeal="废土美学+硬核生存+资源套利（旧世界遗物=新世界权力）",
        pace_reference="《辐射》式废土 — 拾荒、改装、交易、生存",
    ),
    "进化": GenreEngine(
        genre="进化",
        upgrade_chain="基因/血脉解锁式 — 基础进化→定向突变→血脉觉醒→物种跃迁→究极形态",
        conflict_pattern="全球异变→获得初始能力→猎杀进化→遭遇更强进化者→争夺进化资源→面对进化终点",
        antagonist_system="变异生物→同级进化者→顶级掠食者→进化规则的幕后设计者",
        core_appeal="血腥的生物链爬升，每次进化获得新形态和新能力",
        pace_reference="基因锁/血脉浓度百分比量化，每次解锁新能力对应新地图",
    ),
    "科幻": GenreEngine(
        genre="科幻",
        upgrade_chain="技术革命式 — 理论突破→原型验证→小批量产→大规模应用→改变文明形态",
        conflict_pattern="发现异常现象→提出新理论→被主流打压→验证成功→技术军备竞赛→伦理危机→文明抉择",
        antagonist_system="学术保守派→技术竞争对手→技术失控→外星文明→技术奇点",
        core_appeal="用科学逻辑解决看似无解的问题，硬核推演的魅力",
        pace_reference="《三体》式硬科幻 — 技术推演严谨，文明尺度叙事",
    ),

    # ── 历史/现实大类 ──
    "历史": GenreEngine(
        genre="历史",
        upgrade_chain="权力/声望/地盘三维升级 — 县令→太守→州牧→诸侯→王→帝，军/政/经同步攀升",
        conflict_pattern="穿越觉醒→利用先知建立初始班底→地方争霸→逐鹿中原→统一天下→治理盛世",
        antagonist_system="地方豪强→割据诸侯→外族入侵→门阀世家→历史惯性本身",
        core_appeal="改写历史，领先时代半步的改良和争霸",
        pace_reference="《覆汉》— 县令→诸侯→争霸，渐进式+英雄气贯穿",
    ),
    "军事": GenreEngine(
        genre="军事",
        upgrade_chain="军衔+装备+战法 — 从单兵战术到战役指挥到战略决策",
        conflict_pattern="边境冲突→局部战争→全面战争→世界格局重塑→新型战争形态",
        antagonist_system="敌方将领→军事同盟→军事技术的代差→战争本身的非理性",
        core_appeal="铁血战争+战术智斗+装备升级的军事浪漫",
        pace_reference="硬核军事文—真实装备参数+战役推演+后勤博弈",
    ),
    "都市": GenreEngine(
        genre="都市",
        upgrade_chain="财富/地位/身份三维跃迁 — 外卖员→老板→首富，实习生→主任→院长",
        conflict_pattern="意外获得能力/记忆→初次打脸→引来更强对手→建立商业帝国→面对隐秘势力→阶层跨越",
        antagonist_system="商业竞争对手→财阀集团→隐秘世家→国际势力",
        core_appeal="在现代规则下从底层爬到巅峰，金钱和权力碾压",
        pace_reference="战神/神医/赘婿流 — 每章打脸，身份反转密集",
    ),
    "总裁": GenreEngine(
        genre="总裁",
        upgrade_chain="感情阶段+地位对等 — 契约关系→误会期→真心期→修成正果→婚后甜蜜",
        conflict_pattern="契约婚姻/一夜情意外→同居摩擦→前女友/前男友搅局→家族反对→商业危机→最终守护",
        antagonist_system="白月光/前女友→恶毒女配→商业对手→封建家长",
        core_appeal="霸总从冷漠到宠溺的转变，女性从卑微到独立",
        pace_reference="总裁文—契约开篇，误会推动，追妻火葬场",
    ),
    "种田": GenreEngine(
        genre="种田",
        upgrade_chain="生产链条式 — 农耕→养殖→工坊→商贸→城镇→国度，每环节产出可见",
        conflict_pattern="获得土地/空间→解决温饱→发展副业→产品畅销→引来觊觎→守护产业→产业升级",
        antagonist_system="地痞流氓→同行竞争→贪官污吏→商业对手→天灾",
        core_appeal="看着产业一点点壮大，从无到有的成就感",
        pace_reference="《随身空间能召唤》— 空间即生产力，种田+基建+经营",
    ),
    "宫斗": GenreEngine(
        genre="宫斗",
        upgrade_chain="地位+恩宠+子嗣 — 宫女→选侍→嫔→妃→贵妃→皇后→太后",
        conflict_pattern="入宫→被欺负→展现智慧→获宠→被陷害→反击→步步为营→登临后位",
        antagonist_system="同级别妃嫔→贵妃→皇后→太后→前朝势力→皇帝猜忌",
        core_appeal="在权力最集中的后宫靠智慧活下来并登顶",
        pace_reference="宫斗文—每场交锋心理博弈为主，胜败在细节",
    ),

    # ── 悬疑/恐怖大类 ──
    "悬疑": GenreEngine(
        genre="悬疑",
        upgrade_chain="真相揭示层级 — 表象线索→深层阴谋→组织黑幕→世界真相→认知颠覆",
        conflict_pattern="发现异常→调查受阻→线索拼图→接近真相→被设计陷害→逆转翻盘→揭示终极真相",
        antagonist_system="直接嫌疑犯→幕后主使→隐秘组织→信息不对称本身",
        core_appeal="和主角一起拼图解谜，每次反转都重新理解故事",
        pace_reference="《诡秘之主》— 22条途径×10序列，信息差驱动升级",
    ),
    "克苏鲁": GenreEngine(
        genre="克苏鲁",
        upgrade_chain="序列/途径式 — 序列9→序列1→序列0，每次晋升获得新能力但更接近疯狂",
        conflict_pattern="接触超自然→获得非凡能力→发现隐秘存在→SAN值持续下降→在疯狂与力量间挣扎→直面旧神",
        antagonist_system="失控非凡者→隐秘组织→邪神信徒→旧日支配者→认知的边界",
        core_appeal="在不可名状的恐怖中保持人性，代价和力量的永恒博弈",
        pace_reference="《诡秘之主》— 扮演法救赎，22条途径各有疯狂风险",
    ),
    "灵异": GenreEngine(
        genre="灵异",
        upgrade_chain="灵能/法器/功德 — 阴阳眼→驱鬼术→法器→修为→天师→阴司秩序",
        conflict_pattern="遭遇灵异事件→调查根源→发现冤屈→对抗恶灵→揭露背后黑手→维护阴阳秩序",
        antagonist_system="孤魂野鬼→厉鬼→鬼王→阴司腐败→阴阳失衡",
        core_appeal="恐惧与正义交织，每解决一个灵异事件都是一次因果闭环",
        pace_reference="灵异文—单元剧制，每案因果闭环，最终串联大主线",
    ),
    "盗墓": GenreEngine(
        genre="盗墓",
        upgrade_chain="文物/知识/血脉 — 风水知识→摸金技术→古董鉴定→血脉觉醒→破解上古秘密",
        conflict_pattern="发现古墓线索→组队下墓→破解机关→遭遇粽子→获得文物→被组织盯上→揭开文明失落真相",
        antagonist_system="墓中机关→变异生物→盗墓同行→文物走私集团→守护古文明的神秘组织",
        core_appeal="古墓探险的惊险刺激，每个墓一个独立的副本挑战",
        pace_reference="《鬼吹灯》式—风水秘术+古墓机关+文明失落真相",
    ),
    "规则怪谈": GenreEngine(
        genre="规则怪谈",
        upgrade_chain="规则理解深度 — 发现规则→利用规则→修改规则→创造规则→成为规则本身",
        conflict_pattern="进入诡域→发现异常规则→同伴违反规则死亡→推理规则漏洞→破解通关→发现更大的规则体系",
        antagonist_system="规则本身→规则维护者→规则制定者→更高维度的规则游戏",
        core_appeal="智力碾压，用逻辑在看似无解的规则中找出生路",
        pace_reference="规则怪谈—每个诡域是一个独立规则体系，通关后能力继承",
    ),

    # ── 科技/现代大类 ──
    "赛博朋克": GenreEngine(
        genre="赛博朋克",
        upgrade_chain="义体/技术/组织 — 肉体改造→技术研发→黑客能力→组织级别→反抗资本/系统",
        conflict_pattern="底层求生→接受义体改造→发现技术阴谋→组建反抗力量→对抗超级财阀→揭示系统真相",
        antagonist_system="街头帮派→企业安保→财阀→AI系统→技术异化",
        core_appeal="高科技低生活的挣扎与反抗，义体改造和黑客对决",
        pace_reference="赛博朋克—义体改造+企业阴谋+底层反抗",
    ),

    # ── 游戏竞技大类 ──
    "游戏": GenreEngine(
        genre="游戏",
        upgrade_chain="等级/装备/副本 — 角色等级→装备品质→副本进度→公会排名→服务器第一→职业联赛",
        conflict_pattern="创建角色→发现隐藏职业/BUG→快速升级→公会战→服务器争霸→线下职业赛→虚拟与现实交融",
        antagonist_system="野外BOSS→敌对公会→工作室→游戏公司→虚拟世界的幕后存在",
        core_appeal="游戏里的成长可视化和竞技碾压的快感",
        pace_reference="游戏文—数值体系驱动，副本=关卡，竞技场=高潮",
    ),
    "竞技": GenreEngine(
        genre="竞技",
        upgrade_chain="技术/排名/赛事 — 业余→职业→国内联赛→世界赛→巅峰对决→传奇",
        conflict_pattern="天赋被发现→训练突破→首次参赛→遭遇挫折→技术蜕变→登顶夺冠→成为传奇",
        antagonist_system="同级选手→冠军种子→国外选手→伤病/年龄→自我怀疑",
        core_appeal="体育竞技的热血与拼搏，技术的极限突破",
        pace_reference="竞技文—训练+比赛循环，每场比赛一个小高潮",
    ),

    # ── 穿越/重生大类 ──
    "重生": GenreEngine(
        genre="重生",
        upgrade_chain="先知优势+经验积累 — 回到过去→用前世记忆避坑→抢占先机→建立势力→改变命运→修正历史遗憾",
        conflict_pattern="重生觉醒→利用记忆抄底→提前布局→前世仇人找上门→比前世走得更远→面对全新挑战",
        antagonist_system="前世仇人→今世变数→蝴蝶效应引发的意外→重生背后的神秘原因",
        core_appeal="弥补遗憾+预知碾压，每一步都走在别人前面",
        pace_reference="重生文—前世信息差为核心驱动，中后期面对全新未知",
    ),
    "快穿": GenreEngine(
        genre="快穿",
        upgrade_chain="任务积分/技能继承 — 每完成一个世界任务获得技能/道具/属性累积",
        conflict_pattern="被系统选中→进入第一个世界→完成新手任务→连续穿越→积累能力→对抗系统→揭示穿越真相",
        antagonist_system="任务世界反派→同批穿越者→系统本身→穿越机制背后的存在",
        core_appeal="每个世界一种人生，能力跨世界累积的成长感",
        pace_reference="快穿文—每个世界独立故事+主世界能力成长双线并行",
    ),
    "无限流": GenreEngine(
        genre="无限流",
        upgrade_chain="副本积分/能力/权限 — 每通关一个副本获得强化点和技能，逐步解锁更高权限",
        conflict_pattern="被拉入轮回空间→新手副本→小队组队→连续副本→对抗主神/轮回系统→打破空间→获得自由",
        antagonist_system="副本BOSS→敌对小队→主神/轮回空间管理者→不同轮回空间",
        core_appeal="在不同世界观副本中生存进化，能力和装备的无限累积",
        pace_reference="《无限恐怖》— 副本制，每个副本一个独立世界+基因锁升级",
    ),
    "穿越": GenreEngine(
        genre="穿越",
        upgrade_chain="现代知识+异世界规则 — 现代人在古代/异界用知识降维打击",
        conflict_pattern="穿越觉醒→利用现代知识→建立初始优势→遭遇本土势力→知识+修炼双修→改变世界格局",
        antagonist_system="本土保守势力→利益受损者→穿越秘密被发现→穿越机制的限制",
        core_appeal="现代思维解决古代/异界问题的爽感，降维打击",
        pace_reference="穿越文—现代知识是最强金手指，知识差=力量差",
    ),

    # ── 系统/金手指大类 ──
    "系统流": GenreEngine(
        genre="系统流",
        upgrade_chain="任务-奖励-升级闭环 — 签到→任务→积分→兑换→强化→新功能解锁",
        conflict_pattern="获得系统→完成新手任务→能力初显→系统升级开放新功能→系统任务与主线融合→对抗同类系统持有者→系统背后的真相",
        antagonist_system="任务目标→其他系统持有者→系统互相吞噬→系统创造者",
        core_appeal="确定性成长 — 读者清楚'做A能得到B'，消除不确定性焦虑",
        pace_reference="系统文—面板数值驱动，每次打开面板都是一次爽点",
    ),
    "签到流": GenreEngine(
        genre="签到流",
        upgrade_chain="签到次数/地点品质 — 每日签到→稀有地点签到→签到冷却→连续签到奖励→终极签到",
        conflict_pattern="觉醒签到→日常签到积累→特殊地点冒险签到→签到奖励引发争端→用签到积累碾压对手",
        antagonist_system="觊觎签到奖励者→签到地点争夺→签到系统升级的挑战",
        core_appeal="每日签到的即时正反馈，看着资源自动累积的快感",
        pace_reference="签到文—签到即高潮，每章有新奖励，节奏极快",
    ),

    # ── 言情/女性大类 ──
    "言情": GenreEngine(
        genre="言情",
        upgrade_chain="感情阶段 — 相遇→暧昧→确认关系→热恋→考验→修成正果→婚后生活",
        conflict_pattern="邂逅→心动→误会→分离→各自成长→重逢→真心表白→走到一起",
        antagonist_system="情敌→家庭反对→社会压力→自我怀疑→命运的捉弄",
        core_appeal="感情的波折与甜蜜，两个灵魂的相互靠近",
        pace_reference="言情文—感情线为主线，误会和重逢是核心驱动",
    ),
    "校园": GenreEngine(
        genre="校园",
        upgrade_chain="年级/成绩/社交 — 新生→适应期→融入→竞争→升学→毕业",
        conflict_pattern="入学→遇到对手/朋友→学习/竞赛/社团冲突→青春期烦恼→关键考试→毕业抉择",
        antagonist_system="学霸对手→校霸→升学压力→家庭期望→自我怀疑",
        core_appeal="青春成长的共鸣，校园日常的温馨和热血",
        pace_reference="校园文—日常+成长双线，考试/比赛=高潮节点",
    ),

    # ── 其他大类 ──
    "武侠": GenreEngine(
        genre="武侠",
        upgrade_chain="武学境界+江湖地位 — 内功层数→招式境界→江湖称号→开宗立派→武林盟主",
        conflict_pattern="师门被灭→流落江湖→奇遇得功→复仇打脸→卷入正邪之争→揭示武林真相→重塑江湖秩序",
        antagonist_system="灭门仇人→名门正派的伪君子→魔教→朝廷势力→江湖规则本身",
        core_appeal="快意恩仇，刀光剑影中的情义和热血",
        pace_reference="《雪中悍刀行》— 珠帘式群像，情义串线，江湖庙堂交织",
    ),
    "轻小说": GenreEngine(
        genre="轻小说",
        upgrade_chain="日常事件+感情线 — 单元剧→日常累积→感情萌发→关键事件→确定关系→毕业后的人生",
        conflict_pattern="转学/新学期→加入社团→日常互动→出现情敌/矛盾→文化祭/修学旅行→关键抉择→走到一起",
        antagonist_system="情敌→学业压力→家长反对→升学→毕业=离别",
        core_appeal="轻松温馨的校园日常+细腻的感情线发展",
        pace_reference="日系轻小说式—一卷一个阶段，事件+感情渐进",
    ),
    "同人": GenreEngine(
        genre="同人",
        upgrade_chain="原作角色+原创剧情 — 原作能力体系内成长+新故事线展开",
        conflict_pattern="进入原作世界→结识原作角色→参与/介入原作事件→改变故事走向→面对蝴蝶效应→创造新结局",
        antagonist_system="原作反派→改变历史引发的意外后果→原作世界意识的修正力",
        core_appeal="熟知的角色和世界，全新的故事可能性",
        pace_reference="同人文—读者自带对角色和世界的感情，开局即代入",
    ),
    "发疯文": GenreEngine(
        genre="发疯文",
        upgrade_chain="疯狂深度/认知层次 — 轻度异常→认知分裂→两界模糊→真相揭示→疯狂即力量",
        conflict_pattern="发现异常→被认为疯了→在两个世界间挣扎→越疯越强→揭示'疯狂'才是世界的真相",
        antagonist_system="正常人世界→心理医生→收容机构→试图'治愈'主角的力量→认知的囚笼",
        core_appeal="跟着主角一起发疯的沉浸感，认知被不断颠覆",
        pace_reference="《道诡异仙》— 现代与修仙世界交错，坐忘道乐子人",
    ),
    "克系发疯": GenreEngine(
        # 合并克苏鲁+发疯文 — 当 genre_knowledge 同时匹配两个标签时的融合
        genre="克苏鲁",
        upgrade_chain="序列途径+疯狂深度 — 序列9→1，越接近真神越疯狂",
        conflict_pattern="接触非凡→序列提升→SAN值下降→认知分裂→在疯狂中看见真相",
        antagonist_system="失控非凡者→邪神→旧日→自己认知的极限",
        core_appeal="疯狂不是代价，是看清真相的代价",
        pace_reference="《诡秘之主》+《道诡异仙》— 序列体系和发疯叙事的结合",
    ),
}


# ══════════════════════════════════════════════════════════════════════
# 风格 → 叙事模式
# ══════════════════════════════════════════════════════════════════════

@dataclass
class StyleMode:
    """写作风格的叙事模式参数"""
    style: str
    emotion_curve: str      # 情绪曲线
    pacing_rule: str         # 节奏规则
    pov_rule: str            # 视角约束
    dialogue_ratio: str      # 对话占比
    forbidden_patterns: List[str] = field(default_factory=list)  # 禁用模式

# 20 种写作风格的叙事模式（来源：知乎骨肉血模型、POLARIS 2026、社区共识）
STYLE_MODES: Dict[str, StyleMode] = {
    "热血燃向": StyleMode(
        style="热血燃向",
        emotion_curve="螺旋上升，压抑铺垫(80%)→热血爆发(20%)，压抑越深爆发越燃",
        pacing_rule="3-5章小高潮(对峙/打脸)，10-15章中高潮(破境/复仇)，50章大高潮(终极对决)",
        pov_rule="锁定主角内聚焦——写他的所见所感所怒，不跳跃到其他角色内心",
        dialogue_ratio="25-30%，战前简短宣言，战中不废话，战后不总结感悟",
        forbidden_patterns=["高潮前主角长篇大论", "战后立刻总结感悟和收获", "绝望时心理描写超过50字"],
    ),
    "暗黑": StyleMode(
        style="暗黑",
        emotion_curve="持续中低压+阶段性绝望，偶尔微光但不彻底释放，保持紧张感不消散",
        pacing_rule="慢速铺陈，不追密集爽点，重视压抑感的累积和道德困境的反复拷问",
        pov_rule="限知外视角——作者不进入角色内心，读者只能从行为推断情绪",
        dialogue_ratio="20-25%，对话简短冰冷，潜台词比说出来的多",
        forbidden_patterns=["角色自我肯定式内心独白", "道德问题的简单化处理", "用旁白解释'他已经释然了'"],
    ),
    "古龙风格": StyleMode(
        style="古龙风格",
        emotion_curve="意境驱动，不依赖爽点堆叠，靠留白和余韵，高潮是对话中的沉默或一个动作",
        pacing_rule="短句+频繁分段，对话占比极高，叙事密度低但信息密度高",
        pov_rule="外部限知视角——不写内心活动，只写行为和对话，让读者自己揣测",
        dialogue_ratio="50-60%，对话充满机锋和潜台词，每句话都在推进或揭示",
        forbidden_patterns=["直接解释人物动机", "用旁白评价人物", "大段心理描写", "情节总结式段落"],
    ),
    "轻松搞笑": StyleMode(
        style="轻松搞笑",
        emotion_curve="张弛有度但整体轻快，不追求压抑→爆发的剧烈起伏",
        pacing_rule="日常+吐槽交替，每个行为后可以插入反差吐槽（弹幕式旁白）",
        pov_rule="弹性视角——允许跳入跳出，允许吐槽旁白和内心戏",
        dialogue_ratio="35-45%，对话是笑点主要载体，配角脑补（迪化）增加喜剧效果",
        forbidden_patterns=["严肃说教", "刻意煽情超过100字", "笑点重复超过3次"],
    ),
    "快节奏爽文": StyleMode(
        style="快节奏爽文",
        emotion_curve="高潮密集不喘气，每章至少一个爽点（打脸/身份反转/获得奖励）",
        pacing_rule="每2000字一个爽点，每章结尾留钩子，章节间无缝衔接",
        pov_rule="单线跟随主角——不要支线，不要配角视角，一口气跟到底",
        dialogue_ratio="20-25%，对话为打脸服务，不要单独的大段对话场景",
        forbidden_patterns=["超过500字的纯日常/对话/心理", "章节末用总结句（'今天真是收获满满'）", "慢热铺垫"],
    ),
    "细腻写实": StyleMode(
        style="细腻写实",
        emotion_curve="渐进式积累，情感一点点渗透而非爆发式释放",
        pacing_rule="中等节奏，重视细节的真实感，每个场景有足够的感官描写",
        pov_rule="内聚焦——跟随主角的感官（触觉/嗅觉/温度/光线）而非心理活动",
        dialogue_ratio="25-30%，对话自然口语化，不同角色有不同说话节奏",
        forbidden_patterns=["过度戏剧化的冲突", "用形容词堆砌代替具体细节", "浮夸的情绪描写"],
    ),
    "黑色幽默": StyleMode(
        style="黑色幽默",
        emotion_curve="表面轻松底下沉重——用荒诞消解悲剧，笑着笑着就沉默了",
        pacing_rule="事件→荒诞反应→黑色笑点→隐约不安→更荒诞的事件，循环推进",
        pov_rule="冷眼旁观的叙述者——距离感，不共情，只记录",
        dialogue_ratio="30-35%，对话充满反讽和双关，角色说的话和想的事常常相反",
        forbidden_patterns=["直接表达悲伤/愤怒/感动", "用旁白解释'这是个悲剧'"],
    ),
    "意识流": StyleMode(
        style="意识流",
        emotion_curve="内心波动驱动——外部事件退居其次，情绪流动和记忆闪回是主要节奏",
        pacing_rule="不遵循线性时间，当下→回忆→联想→当下，情绪和意象引导叙事跳转",
        pov_rule="内聚焦（深度）——自由间接引语+内心独白，读者完全沉浸在主角感知中",
        dialogue_ratio="15-20%，对话少但每句重千钧，常被内心活动打断",
        forbidden_patterns=["清晰的时间线和因果链", "客观的外部事件描述"],
    ),
    "硬核科幻": StyleMode(
        style="硬核科幻",
        emotion_curve="理性推演驱动——技术参数的突破和逻辑链条的闭合是高潮所在",
        pacing_rule="问题→假设→验证→技术突破→新问题，科学方法驱动节奏",
        pov_rule="多视角+技术日志体——允许技术文档/会议记录/实验报告形式的叙事",
        dialogue_ratio="25-30%，技术讨论就是高潮，对话可以长达整章",
        forbidden_patterns=["反科学逻辑的剧情", "用情感代替推理解释", "主角凭直觉做重大决策"],
    ),
    "现代主义": StyleMode(
        style="现代主义",
        emotion_curve="多层交织——一个场景同时承载多个情感层次，不线性释放",
        pacing_rule="碎片化拼贴，多线索交叉，读者需要主动拼合",
        pov_rule="多视角自由切换——同一事件从不同角色角度呈现",
        dialogue_ratio="25-30%，对话碎片化，每句承载信息密度高",
        forbidden_patterns=["线性叙事", "单一情绪贯穿全章", "明确的道德判断"],
    ),
    "极简主义": StyleMode(
        style="极简主义",
        emotion_curve="冰山式——只写露出水面的1/8，水下的7/8留给读者想象",
        pacing_rule="短句→空白→短句→空白，省掉的比写出的多",
        pov_rule="纯外部视角——像摄像机一样只记录行为和对话，不进入任何角色内心",
        dialogue_ratio="40-50%，对话极简，每句不超过30字，潜台词是写出来的3倍",
        forbidden_patterns=["任何形式的心理描写", "形容词和副词的堆叠", "超过100字的场景描写"],
    ),
    "硬派写实": StyleMode(
        style="硬派写实",
        emotion_curve="零度叙事——不煽情不渲染，用事实本身的力量打动读者",
        pacing_rule="事件自然推进，不加速不减速，拒绝戏剧化高潮",
        pov_rule="旁观叙述者——报告体，精确到数字和细节，不加评论",
        dialogue_ratio="30-35%，对话像录音笔录下来的原始素材",
        forbidden_patterns=["任何形式的抒情", "夸张和渲染", "作者跳出来的评论"],
    ),
    "多视角切换": StyleMode(
        style="多视角切换",
        emotion_curve="多角色情绪交织——不同角色对同一事件有不同的情感反应",
        pacing_rule="每3-5章切换一次视角，视角切换点=悬念钩子",
        pov_rule="多角色分视角——每章锁定一个角色的视角，章内不跳",
        dialogue_ratio="30-35%，不同角色的对话有不同语癖和节奏",
        forbidden_patterns=["同一章内视角跳跃", "用全知旁白覆盖视角角色的认知范围"],
    ),
    "反套路": StyleMode(
        style="反套路",
        emotion_curve="预期违背驱动——读者以为A，给B，每次违背预期制造新鲜感",
        pacing_rule="建立预期→颠覆→建立新预期→再颠覆，三层嵌套",
        pov_rule="跟随主角的认知过程——让读者和主角一起被反转让",
        dialogue_ratio="30-35%，对话是反套路的主要载体（角色自己都在吐槽'这跟剧本不一样'）",
        forbidden_patterns=["标准的爽文套路", "大团圆结局", "主角光环无理由生效"],
    ),
    # 以下风格数据较薄（社区未形成完整共识），标注为观察分析
    "史诗感": StyleMode(
        style="史诗感",
        emotion_curve="宏大叙事，个人命运融入时代洪流，悲壮而不煽情",
        pacing_rule="长跨度——几代人的时间尺度，大事件之间跨度以年计",
        pov_rule="多代主角视角——群像，每个时代有代表性人物",
        dialogue_ratio="20-25%，对话承载历史重量，每句像碑文",
        forbidden_patterns=["速食式爽文节奏", "主角一人拯救世界", "历史简化为好人和坏人"],
    ),
    "剧本式": StyleMode(
        style="剧本式",
        emotion_curve="视觉化情感——通过动作和对白传达情绪，禁止内心旁白式抒情",
        pacing_rule="场景→场景→场景，像电影镜头切换，每个场景有明确意图",
        pov_rule="摄影机视角——只记录可见的行为和可听见的对话",
        dialogue_ratio="50-60%，几乎纯对话驱动，像剧本",
        forbidden_patterns=["内心独白", "作者旁白", "纯描写段落超过100字"],
    ),
    "网络小说": StyleMode(
        style="网络小说",
        emotion_curve="标准爽文曲线——期待感→优越感→安全感→获得感交替循环",
        pacing_rule="起点工业标准——3-5章一个事件闭环，章末留钩子",
        pov_rule="主角跟随——不跳跃，偶尔切配角视角做平行悬念",
        dialogue_ratio="25-30%，对话为推进和打脸服务",
        forbidden_patterns=["慢热", "超过500字的环境描写", "与主线无关的支线"],
    ),
    # 以下是占位风格（有风格标签但社区未形成完整共识，标记为观察分析）
    "日系轻小说": StyleMode(
        style="日系轻小说",
        emotion_curve="温馨+吐槽交替——萌点和笑点驱动，情感克制不煽情",
        pacing_rule="一卷一个阶段——日常→事件→解决→下一阶段，卷末留悬念",
        pov_rule="第一人称内聚焦——'我'的所见所感，内心吐槽是风格核心",
        dialogue_ratio="45-55%，对话占比极高，吐槽和误解是主要笑点",
        forbidden_patterns=["上帝视角叙事", "严肃的说教", "过度戏剧化的大场面"],
    ),
    "清新文艺": StyleMode(
        style="清新文艺",
        emotion_curve="淡雅含蓄——情感像水彩一样一层层渲染，不浓墨重彩",
        pacing_rule="慢速——重视氛围和意境，不追求事件密度",
        pov_rule="第一人称——沉浸式感知，细微的观察是风格灵魂",
        dialogue_ratio="20-25%，对话少而精，每句像诗",
        forbidden_patterns=["激烈的冲突", "粗俗的语言", "快节奏叙事"],
    ),
}


# ══════════════════════════════════════════════════════════════════════
# 题材 × 风格 → 写作约束
# ══════════════════════════════════════════════════════════════════════

def match_storyform(genre: str, style: str) -> dict:
    """匹配题材和风格，返回完整的故事结构约束。

    Args:
        genre: 流派标签，如 '修仙' '玄幻' '都市'
        style: 写作风格，如 '热血燃向' '暗黑' '古龙风格'

    Returns:
        dict with keys:
          - genre: 题材引擎
          - style: 风格模式
          - constraints: 合并后的写作约束列表（≤5条）
          - genre_found: 是否找到该题材
          - style_found: 是否找到该风格
    """
    genre_engine = GENRE_ENGINES.get(genre)
    style_mode = STYLE_MODES.get(style)

    result = {
        "genre": genre_engine,
        "style": style_mode,
        "genre_found": genre_engine is not None,
        "style_found": style_mode is not None,
        "constraints": [],
    }

    if not genre_engine and not style_mode:
        result["constraints"] = ["（无匹配——请选择有效的题材和风格）"]
        return result

    constraints = []

    # 题材约束
    if genre_engine:
        constraints.append(f"[升级链] {genre_engine.upgrade_chain}")
        constraints.append(f"[冲突模式] {genre_engine.conflict_pattern}")
        constraints.append(f"[反派体系] {genre_engine.antagonist_system}")

    # 风格约束
    if style_mode:
        constraints.append(f"[情绪曲线] {style_mode.emotion_curve}")
        constraints.append(f"[节奏] {style_mode.pacing_rule}")
        constraints.append(f"[视角] {style_mode.pov_rule}")
        constraints.append(f"[对话] 对话占比约{style_mode.dialogue_ratio}")
        if style_mode.forbidden_patterns:
            forbidden = "；".join(style_mode.forbidden_patterns[:3])
            constraints.append(f"[禁止] {forbidden}")

    # 最多 5 条核心约束（设计法则 1：27B 只能消化 ≤5 条）
    # 如果超过 5 条，取最重要的：升级链 + 冲突模式 + 情绪曲线 + 节奏 + 反派体系
    if len(constraints) > 5:
        priority_keys = ["[升级链]", "[冲突模式]", "[情绪曲线]", "[节奏]", "[反派体系]"]
        constraints = [c for c in constraints if any(c.startswith(k) for k in priority_keys)]
        constraints = constraints[:5]

    result["constraints"] = constraints
    return result


def build_writing_context(genre: str, style: str) -> str:
    """生成 27B 写作模型可执行的约束文本。

    输出 ≤5 条中文约束，零 Dramatica 术语，带具体示例。

    Args:
        genre: 流派标签
        style: 写作风格
    Returns:
        写作约束文本（直接附加到 prompt）
    """
    result = match_storyform(genre, style)
    if not result["constraints"]:
        return ""

    parts = ["\n[故事引擎 — 写作约束]\n"]
    for i, c in enumerate(result["constraints"], 1):
        parts.append(f"{i}. {c}")

    # 添加调试信息（标记数据来源）
    warnings = []
    if not result["genre_found"]:
        warnings.append(f"题材'{genre}'：无匹配引擎，使用默认")
    if not result["style_found"]:
        warnings.append(f"风格'{style}'：无匹配模式，使用默认")

    if warnings:
        parts.append(f"\n（注意：{'；'.join(warnings)}）")

    return "\n".join(parts)


def list_genres() -> List[str]:
    """列出所有支持的题材。"""
    return sorted(GENRE_ENGINES.keys())


def list_styles() -> List[str]:
    """列出所有支持的风格。"""
    return sorted(STYLE_MODES.keys())


def list_combos(genre: Optional[str] = None, style: Optional[str] = None) -> List[dict]:
    """列出题材×风格组合。

    Args:
        genre: 限定题材（可选）
        style: 限定风格（可选）
    Returns:
        [{"genre": ..., "style": ..., "constraint_count": ...}]
    """
    genres = [genre] if genre else sorted(GENRE_ENGINES.keys())
    styles = [style] if style else sorted(STYLE_MODES.keys())
    combos = []
    for g in genres:
        for s in styles:
            r = match_storyform(g, s)
            combos.append({
                "genre": g,
                "style": s,
                "constraint_count": len(r["constraints"]),
                "genre_found": r["genre_found"],
                "style_found": r["style_found"],
            })
    return combos


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 快速自检
    print(f"题材引擎: {len(GENRE_ENGINES)}")
    print(f"风格模式: {len(STYLE_MODES)}")

    # 测试几个组合
    for genre, style in [("修仙", "热血燃向"), ("都市", "快节奏爽文"), ("悬疑", "暗黑"),
                          ("赛博朋克", "硬核科幻"), ("发疯文", "古龙风格"), ("不存在的", "热血燃向")]:
        ctx = build_writing_context(genre, style)
        constraint_count = len([l for l in ctx.split('\n') if l.strip().startswith(tuple('12345'))])
        print(f"\n{'='*50}")
        print(f"{genre} × {style} ({constraint_count}条约束):")
        print(ctx[:600])

    print(f"\n{'='*50}")
    print(f"总组合数: {len(list_genres())} × {len(list_styles())} = {len(list_genres())*len(list_styles())}")
