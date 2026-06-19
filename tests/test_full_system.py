import sys, os, json
sys.path.insert(0, r'C:\Users\abee\ai-novel-frameworks\Novel-Claude')

passed = 0; failed = 0
def check(name, ok, detail=''):
    global passed, failed
    if ok: passed += 1; print(f'  [PASS] {name}')
    else: failed += 1; print(f'  [FAIL] {name} {detail}')

# ===== 1. Model Params (2026 tuned) =====
print('=== 1. Model Parameters (2026 Tuned) ===')
from utils.llm_client import _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p, get_task_model
check('planning->Opus', 'opus' in get_task_model('planning').lower())
check('writing->Uncensored', 'uncensored' in get_task_model('writing').lower())
check('writing freq_pen=0.5', abs(_llm_frequency_penalty('writing') - 0.5) < 0.01)
check('writing pres_pen=0.35', abs(_llm_presence_penalty('writing') - 0.35) < 0.01)
check('deai freq_pen=0.6', abs(_llm_frequency_penalty('deai') - 0.6) < 0.01)
check('deai pres_pen=0.5', abs(_llm_presence_penalty('deai') - 0.5) < 0.01)
check('planning temp=0.6', abs(_llm_temperature('planning') - 0.6) < 0.01)
check('writing temp=0.9', abs(_llm_temperature('writing') - 0.9) < 0.01)
check('reasoning temp=0.5', abs(_llm_temperature('reasoning') - 0.5) < 0.01)

# ===== 2. De-AI Six Layers with L4 Dialog =====
print('=== 2. De-AI Engine (L1-L6 + Dialog Intent) ===')
from skills.gen_deai_engine.skill import GenDeaiEngineSkill
class Ctx:
    def set_shared(s,k,v): pass
    def get_shared(s,k,d=None): return d
e = GenDeaiEngineSkill(Ctx())

# AI-heavy text
ai_text = '''他缓缓地抬起头，微微皱眉，心中不由得一震。不禁倒吸一口凉气，顿时感到百感交集、五味杂陈。
她静静地站在那，幽幽地叹了一口气，仿佛整个世界都安静了，宛如一幅画卷缓缓展开。
他的嘴角微微上扬，眼神中闪过一丝复杂的神色。心中仿佛翻涌着某种难以名状的情绪。
"你好。"他说。"你好。"她回答。"今天天气不错。"他说。"是的。"她点点头。'''

r = e.analyze(ai_text)
check('AI text detected (score<80)', r['overall_score'] < 80)
check('8 dimensions', len(r['dimensions']) == 8)
check('L3 adj_density present', 'density' in r['adj_density'])
check('L4 dialogue_intent_ratio present', 'dialogue_intent_ratio' in r['idiom_density'])
check('L5 para_variation present', 'variance' in r['para_variation'])
check('L6 punct_rhythm present', 'ellipsis_per_k' in r['punct_rhythm'])

# Clean text with intent-rich dialogue
clean_text = '''门开了。她没回头。脚步声停在身后两步远，带着松脂和铁锈的气味。手指在桌面上叩了两下，停了。
"最后问你一次。"他说。她没答。
一张纸被推到她手边，叠得方正。她没接。他又叩了一下。
"你知道这是什么。"
她还是没说话，但手指收紧了。他笑了一声，很短，然后走了。'''
r2 = e.analyze(clean_text)
check('clean > AI text', r2['overall_score'] > r['overall_score'])
check('L4 dialog intent > 0 (intent detected)', r2['idiom_density'].get('dialogue_intent_ratio', 0) > 0)
check('L3 adj clean better', r2['adj_density']['density'] < r['adj_density']['density'])
print(f'  AI={r["overall_score"]} clean={r2["overall_score"]}')

# ===== 3. Genre/Style DB (2026 anti-patterns) =====
print('=== 3. Genres (29, 2026 Anti-Patterns) ===')
from skills.gen_genre_tags.skill import GENRE_DB
from skills.gen_writing_style.skill import STYLE_DB
check('29 genres', len(GENRE_DB) == 29)
check('20 styles', len(STYLE_DB) == 20)

# Verify all genres have >=3 antiPatterns and >=20 char pacingStrategy
for g in GENRE_DB:
    a = GENRE_DB[g]['antiPatterns']
    s = GENRE_DB[g]['pacingStrategy']
    if len(a) < 3 or len(s) < 20:
        check(f'{g}: {len(a)} anti, {len(s)} pace', False)
# Check 2026-specific content
check('退婚流 in 玄幻', any('退婚' in x for x in GENRE_DB['玄幻']['antiPatterns']))
check('考据流 in 历史', '考据' in GENRE_DB['历史']['pacingStrategy'])
check('兵王停滞 in 都市', any('兵王回归' in x for x in GENRE_DB['都市']['antiPatterns']))
check('系统+职业 in 系统流', '职业' in GENRE_DB['系统流']['pacingStrategy'])

# ===== 4. Genre/Style Injection =====
print('=== 4. Genre/Style Injection ===')
from webui.app import _build_genre_style_injection

for genre, style, keywords in [
    ('玄幻', '古龙风格', ['退婚', '古龙', '情绪流']),
    ('历史', '说书风', ['考据', '说书', '造肥皂']),
    ('都市', '幽默吐槽', ['兵王', '职场PUA', '吐槽']),
    ('悬疑', '白描纪实', ['规则怪谈', '绝境钩子']),
]:
    inj = _build_genre_style_injection({'genre': genre, 'style': style})
    all_found = all(k in inj for k in keywords)
    check(f'{genre}+{style}', all_found, f'missing keywords: {[k for k in keywords if k not in inj]}')

# ===== 5. Scribe Prompt (2026 Techniques) =====
print('=== 5. Scribe Prompt (2026 Techniques) ===')
from skills.wf_mo_shen_workflow.skill import SCRIBE_SYSTEM

tech_checks = [
    ('3-second rule', '三秒法则' in SCRIBE_SYSTEM),
    ('action ellipsis', '动作留白' in SCRIBE_SYSTEM),
    ('detail anchor', '细节锚点' in SCRIBE_SYSTEM),
    ('sensory hierarchy', '触觉/嗅觉/温度' in SCRIBE_SYSTEM),
    ('genre language rules', '题材专属' in SCRIBE_SYSTEM),
    ('dialog intent labels', '意图标签' in SCRIBE_SYSTEM),
    ('expanded ban list', '骤然' in SCRIBE_SYSTEM and '回荡' in SCRIBE_SYSTEM),
    ('anti-analytic language', '分析报告式语言' in SCRIBE_SYSTEM),
    ('xuanhuan anti-numeric', '数值化战力' in SCRIBE_SYSTEM),
    ('horror anti-stated fear', '禁止直述恐惧' in SCRIBE_SYSTEM),
]
for name, ok in tech_checks:
    check(name, ok)

# ===== 6. Agent Prompts =====
print('=== 6. All Agent Prompts ===')
from skills.wf_mo_shen_workflow.skill import (
    ARCHITECT_SYSTEM, EDITOR_SYSTEM, POLISHER_SYSTEM, GATEKEEPER_SYSTEM
)
check('Architect: plan method', '章内计划' in ARCHITECT_SYSTEM)
check('Architect: cost system', '代价' in ARCHITECT_SYSTEM)
check('Editor: narrative scan', '叙事层面' in EDITOR_SYSTEM)
check('Editor: moralizing', '说教' in EDITOR_SYSTEM)
check('Polisher: 12 techniques', '思维中断' in POLISHER_SYSTEM and '延迟揭示' in POLISHER_SYSTEM)
check('Gatekeeper: 10 dims', 'sensory_richness' in GATEKEEPER_SYSTEM and 'cost_fulfillment' in GATEKEEPER_SYSTEM)

# ===== 7. Config =====
print('=== 7. Config ===')
cfg = json.load(open(r'C:\Users\abee\ai-novel-frameworks\Novel-Claude\config.json', encoding='utf-8'))
gen = cfg.get('generation', {})
check('freq_pen=0.5 in config', gen.get('frequency_penalty') == 0.5)
check('pres_pen=0.35 in config', gen.get('presence_penalty') == 0.35)
check('temperature_writing=0.9', gen.get('temperature_writing') == 0.9)

# ===== 8. Syntax =====
print('=== 8. Syntax ===')
import ast
for f in ['skills/gen_deai_engine/skill.py', 'skills/wf_mo_shen_workflow/skill.py',
           'webui/app.py', 'utils/llm_client.py']:
    path = os.path.join(r'C:\Users\abee\ai-novel-frameworks\Novel-Claude', f)
    try:
        ast.parse(open(path, encoding='utf-8').read())
        check(f'syntax: {f.split(chr(47))[-1]}', True)
    except SyntaxError as e:
        check(f'syntax: {f}', False, str(e))

# ===== 9. WebUI HTML =====
print('=== 9. WebUI HTML ===')
html = open(r'C:\Users\abee\ai-novel-frameworks\Novel-Claude\webui\templates\index.html', encoding='utf-8').read()
check('project selector', 'projectSelect' in html)
check('agent mode toggle', 'agentMode' in html)
check('genre->style filter', 'loadStylesForGenre' in html)
check('L3-L6 detail table', '六层检测详情' in html)
check('status panel updated', '策划模型' in html)

# ===== 10. Prompt Files =====
print('=== 10. Prompt Files ===')
base = r'C:\Users\abee\ai-novel-frameworks\Novel-Claude\prompts\model-prompts'
for fn in os.listdir(base):
    if fn.endswith('.md'):
        c = open(os.path.join(base, fn), encoding='utf-8').read()
        check(f'{fn} loaded', len(c) > 200)

print(f'\nTOTAL: {passed}P/{failed}F {"ALL PASSED" if failed == 0 else "FAILURES"}')
