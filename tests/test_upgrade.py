import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f'  [PASS] {name}')
    else:
        failed += 1
        print(f'  [FAIL] {name}')

# 1. Model routing
print('=== 1. Model Routing ===')
from utils.llm_client import get_task_model, get_task_client
from utils.llm_client import _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p

check('planning model -> Uncensored', 'uncensored' in get_task_model('planning').lower())
check('writing model -> Uncensored', 'uncensored' in get_task_model('writing').lower())
check('reasoning model -> Uncensored', 'uncensored' in get_task_model('reasoning').lower())
check('planning temp=0.6', abs(_llm_temperature('planning') - 0.6) < 0.01)
check('writing temp=0.9', abs(_llm_temperature('writing') - 0.9) < 0.01)
check('reasoning temp=0.5', abs(_llm_temperature('reasoning') - 0.5) < 0.01)
check('deai temp=0.7', abs(_llm_temperature('deai') - 0.7) < 0.01)
check('writing freq_pen=0.25', abs(_llm_frequency_penalty('writing') - 0.25) < 0.01)
check('deai freq_pen=0.4', abs(_llm_frequency_penalty('deai') - 0.4) < 0.01)
check('writing top_p=0.95', abs(_llm_top_p('writing') - 0.95) < 0.01)

# 2. De-AI engine
print('=== 2. De-AI 6-Layer Detection ===')
from skills.gen_deai_engine.skill import GenDeaiEngineSkill
class Ctx:
    def set_shared(s, k, v): pass
    def get_shared(s, k, d=None): return d
e = GenDeaiEngineSkill(Ctx())

ai_text = '他缓缓地抬起头，微微皱眉，心中不由得一震。不禁倒吸一口凉气，顿时感到百感交集、五味杂陈。她静静地站在那，幽幽地叹了一口气，仿佛整个世界都安静了，宛如一幅画卷缓缓展开。嘴角微微上扬，眼神中闪过一丝复杂的神色。'
r = e.analyze(ai_text)
check('AI text score < 80', r['overall_score'] < 80)
check('9 dimensions (L1-L9)', len(r['dimensions']) == 9)
check('L3 adj_density', 'density' in r.get('adj_density', {}))
check('L4 idiom_density', 'density' in r.get('idiom_density', {}))
check('L5 para_variation', 'variance' in r.get('para_variation', {}))
check('L6 punct_rhythm', 'ellipsis_per_k' in r.get('punct_rhythm', {}))

clean_text = '门开了。她没回头。脚步声。松脂和铁锈的气味。他停在她身后两步远。手指叩了两下桌面。一张纸，叠得方正。推到她的手边。她没接。他又叩了一下。\n\n然后走了。门没关。她这才拿起那张纸，翻过来，空的。背面也只有三个字，铅笔写的，笔画很轻。\n\n她把纸对折，又对折，塞进袖口。炉火噼啪响了一声。窗外有人在喊什么，听不真切。'
r2 = e.analyze(clean_text)
check('clean > AI text', r2['overall_score'] > r['overall_score'])
check('adj_density clean better', r2['adj_density']['density'] <= r['adj_density']['density'])
check('idiom_density clean better', r2['idiom_density']['density'] <= r['idiom_density']['density'])
print(f'  AI={r["overall_score"]} clean={r2["overall_score"]} adj:AI={r["adj_density"]["density"]} clean={r2["adj_density"]["density"]} idiom:AI={r["idiom_density"]["density"]} clean={r2["idiom_density"]["density"]}')

# 3. Workflow prompts
print('=== 3. Agent Prompts ===')
from skills.wf_mo_shen_workflow.skill import (
    ARCHITECT_SYSTEM, SCRIBE_SYSTEM, EDITOR_SYSTEM,
    POLISHER_SYSTEM, GATEKEEPER_SYSTEM
)
check('Architect: scene decomposition', '场景' in ARCHITECT_SYSTEM)
check('Scribe: dialogue 30%', '30%' in SCRIBE_SYSTEM)
check('Scribe: banned words', '前所未有' in SCRIBE_SYSTEM)
check('Editor: hook check', '章末钩子' in EDITOR_SYSTEM)
check('Editor: POV lock', '视角' in EDITOR_SYSTEM)
check('Polisher: externalize emotion', '心理描写外化' in POLISHER_SYSTEM)
check('Gatekeeper: 5 dims', '追读力' in GATEKEEPER_SYSTEM)
check('Editor: moralizing check', '说教' in EDITOR_SYSTEM)
check('Polisher: externalize emotion', '心理描写外化' in POLISHER_SYSTEM)
check('Polisher: remove ending summary', '删结尾升华' in POLISHER_SYSTEM)
check('Gatekeeper: 5 dims', '追读力' in GATEKEEPER_SYSTEM)
check('Gatekeeper: AI flavor', 'AI味' in GATEKEEPER_SYSTEM)

# 4. Genre/style injection
print('=== 4. Genre/Style Injection ===')
from webui.app import _build_genre_style_injection
inj = _build_genre_style_injection({'genre': '玄幻', 'style': '古龙风格'})
check('genre present', '流派' in inj)  # 流派
check('anti-patterns present', '反套路' in inj)  # 反套路
check('style present', '写作风格' in inj)  # 写作风格
check('style prompt content', '古龙' in inj)  # 古龙
empty = _build_genre_style_injection({})
check('empty config -> empty', empty == '')

# 5. Prompt files
print('=== 5. Prompt Files ===')
base = r'C:\Users\abee\ai-novel-frameworks\Novel-Claude\prompts\model-prompts'
for fn in sorted(os.listdir(base)):
    if fn.endswith('.md'):
        c = open(os.path.join(base, fn), encoding='utf-8').read()
        check(f'{fn}: >200 chars', len(c) > 200)

# 6. Config
print('=== 6. Config ===')
cfg_path = r'C:\Users\abee\ai-novel-frameworks\Novel-Claude\config.json'
cfg = json.load(open(cfg_path, encoding='utf-8'))
gen = cfg.get('generation', {})
check('temperature_writing', 'temperature_writing' in gen)
check('frequency_penalty', 'frequency_penalty' in gen)
check('top_p', 'top_p' in gen)
check('task_models.planning', 'planning' in cfg.get('llm', {}).get('task_models', {}))

# 7. WebUI HTML
print('=== 7. WebUI HTML ===')
html_path = r'C:\Users\abee\ai-novel-frameworks\Novel-Claude\webui\templates\index.html'
html = open(html_path, encoding='utf-8').read()
check('agent_progress handler', 'agent_progress' in html)
check('agent_result handler', 'agent_result' in html)
check('agent mode checkbox', 'agentMode' in html)
check('mode=agent URL', 'mode=agent' in html)
check('L3-L6 detail table', '六层检测详情' in html)  # 六层检测详情
check('status: plan model', '策划模型' in html)  # 策划模型
check('status: workflow mode', '工作流模式' in html)  # 工作流模式

# Summary
print()
print('=' * 40)
print(f'TOTAL: {passed} passed, {failed} failed')
print('ALL PASSED!' if failed == 0 else f'{failed} FAILURES!')
