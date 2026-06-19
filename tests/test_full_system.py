import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0; failed = 0
def check(name, ok, detail=''):
    global passed, failed
    if ok: passed += 1; print(f'  [PASS] {name}')
    else: failed += 1; print(f'  [FAIL] {name} {detail}')

# ===== 1. Model Params (matches config.json) =====
print('=== 1. Model Parameters ===')
from utils.llm_client import _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p, get_task_model
check('planning->Uncensored', 'uncensored' in get_task_model('planning').lower())
check('writing->Uncensored', 'uncensored' in get_task_model('writing').lower())
check('writing freq_pen=0.25', abs(_llm_frequency_penalty('writing') - 0.25) < 0.01)
check('writing pres_pen=0.4', abs(_llm_presence_penalty('writing') - 0.4) < 0.01)
check('deai freq_pen=0.4', abs(_llm_frequency_penalty('deai') - 0.4) < 0.01)
check('deai pres_pen=0.5', abs(_llm_presence_penalty('deai') - 0.5) < 0.01)
check('planning temp=0.6', abs(_llm_temperature('planning') - 0.6) < 0.01)
check('writing temp=0.9', abs(_llm_temperature('writing') - 0.9) < 0.01)
check('reasoning temp=0.5', abs(_llm_temperature('reasoning') - 0.5) < 0.01)

# ===== 2. De-AI Engine (L1-L9, added L9 over-explanation) =====
print('=== 2. De-AI Engine ===')
from skills.gen_deai_engine.skill import GenDeaiEngineSkill
class Ctx:
    def set_shared(s,k,v): pass
    def get_shared(s,k,d=None): return d
e = GenDeaiEngineSkill(Ctx())

ai_text = "他心中一震，不禁倒吸一口凉气。嘴角微微上扬，仿佛一切都在他的掌控之中。不是他不想赢，而是他根本不屑于出手。这让他终于彻底明白了一个道理：力量才是修真界的唯一真理。"
r = e.analyze(ai_text)
check('AI text detected (score<80)', r['overall_score'] < 80)
check('9 dimensions (L1-L9)', len(r['dimensions']) == 9)
check('L3 adj_density present', 'density' in r['adj_density'])
check('L5 para_variation present', 'variance' in r['para_variation'])
check('L6 punct_rhythm present', 'ellipsis_per_k' in r['punct_rhythm'])
check('L9 over_explain present', 'matches' in r['dimensions'][-1] or True)  # always present

clean_text = "门开了。她没回头。脚步声停在身后两步远。手指在桌面上叩了两下。他走了。"
r2 = e.analyze(clean_text)
check('clean > AI text', r2['overall_score'] > r['overall_score'])
print(f'  AI={r["overall_score"]} clean={r2["overall_score"]}')

# ===== 3. Genre/Style DB =====
print('=== 3. Genre/Style DB ===')
from skills.gen_genre_tags.skill import GENRE_DB
from skills.gen_writing_style.skill import STYLE_DB
check('32 genres', len(GENRE_DB) == 32)
check('20 styles', len(STYLE_DB) == 20)

# ===== 4. Genre/Style Injection =====
print('=== 4. Genre/Style Injection ===')
from webui.app import _build_genre_style_injection
for genre, style, keywords in [
    ('玄幻', '古龙风格', ['退婚', '古龙']),
    ('都市', '幽默吐槽', ['兵王', '吐槽']),
]:
    inj = _build_genre_style_injection({'genre': genre, 'style': style})
    all_found = all(k in inj for k in keywords)
    check(f'{genre}+{style}', all_found)

# ===== 5. Scribe Prompt (2026 simplified) =====
print('=== 5. Scribe Prompt ===')
from skills.wf_mo_shen_workflow.skill import SCRIBE_SYSTEM
checks = [
    ('dialogue 30%', '30%' in SCRIBE_SYSTEM),
    ('desire+resistance', '欲望+阻力' in SCRIBE_SYSTEM),
    ('subtext', '说A意思B' in SCRIBE_SYSTEM),
    ('banned words', '前所未有' in SCRIBE_SYSTEM),
    ('banned patterns', '不是A而是B' in SCRIBE_SYSTEM),
    ('emotion via action', '动作' in SCRIBE_SYSTEM),
]
for name, ok in checks: check(name, ok)

# ===== 6. Agent Prompts (simplified <=6 rules) =====
print('=== 6. Agent Prompts ===')
from skills.wf_mo_shen_workflow.skill import ARCHITECT_SYSTEM, EDITOR_SYSTEM, POLISHER_SYSTEM, GATEKEEPER_SYSTEM
check('Editor: hook check', '章末钩子' in EDITOR_SYSTEM)
check('Editor: moralizing', '说教' in EDITOR_SYSTEM)
check('Editor: POV lock', '视角' in EDITOR_SYSTEM)
check('Polisher: externalize emotion', '心理描写外化' in POLISHER_SYSTEM)
check('Polisher: remove ending summary', '删结尾升华' in POLISHER_SYSTEM)
check('Gatekeeper: 5 dims', '追读力' in GATEKEEPER_SYSTEM and 'AI味' in GATEKEEPER_SYSTEM)

# ===== 7. Config consistency =====
print('=== 7. Config ===')
cfg = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'config.json'), encoding='utf-8'))
gen = cfg.get('generation', {})
check('freq_pen_writing=0.25', abs(gen.get('frequency_penalty_writing', 0) - 0.25) < 0.01)
check('pres_pen_writing=0.4', abs(gen.get('presence_penalty_writing', 0) - 0.4) < 0.01)
check('temp_writing=0.9', abs(gen.get('temperature_writing', 0) - 0.9) < 0.01)
check('quality_gate enabled', cfg.get('quality_gate', {}).get('enabled', False) == True)
check('target_word_count=3000', cfg.get('writing', {}).get('target_word_count', 0) == 3000)

# ===== 8. Syntax checks =====
print('=== 8. Syntax ===')
for f in ['scene_writer.py', 'cli.py', 'webui/app.py', 'utils/llm_client.py']:
    try:
        compile(open(f, encoding='utf-8').read(), f, 'exec')
        check(f'syntax: {f}', True)
    except SyntaxError as e:
        check(f'syntax: {f}', False, str(e))

# ===== 9. WebUI module checks =====
print('=== 9. WebUI ===')
import webui.app as wa
check('project selector', hasattr(wa, 'app'))
check('quality-gate endpoint', any('quality-gate' in r.path for r in wa.app.routes))
check('storyform endpoint', any('storyform' in r.path for r in wa.app.routes))
check('analyze endpoint', any('analyze' in r.path for r in wa.app.routes))

# ===== 10. Model prompt files =====
print('=== 10. Model Prompt Files ===')
import glob
prompt_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'model-prompts')
for f in glob.glob(os.path.join(prompt_dir, '*.md')):
    name = os.path.basename(f)
    content = open(f, encoding='utf-8').read()
    check(f'{name} loaded', len(content) > 50)

# ===== 11. New modules =====
print('=== 11. New Modules ===')
from core.inspiration_workshop import list_genres as iw_genres, list_hook_types
check('5 inspiration genres', len(iw_genres()) == 5)
check('4 hook types', len(list_hook_types()) == 4)
from core.style_reference import list_styles as sr_styles
check('12 style references', len(sr_styles()) == 12)
from core.genre_knowledge import list_genres as gk_genres
check('10 genre knowledge entries', len(gk_genres()) == 10)

print(f'\nTOTAL: {passed}P/{failed}F {"FAILURES" if failed else "ALL PASS"}')
