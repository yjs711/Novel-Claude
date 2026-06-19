import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webui.app import load_cfg, save_cfg
cfg = load_cfg()
cfg['workspace']['novel_name'] = 'test_xiuzhen'
cfg['genre'] = '修仙'
cfg['style'] = '热血燃向'
cfg['workflow']['mode'] = 'quick'
save_cfg(cfg)
from utils.config import reload_workspace
reload_workspace()

print('Project: test_xiuzhen')
print('Genre: 修仙 | Style: 热血燃向 | Mode: quick')
print()

from utils.prompt_loader import writing_prompt
from webui.app import _build_genre_style_injection
system_prompt = writing_prompt() + _build_genre_style_injection(cfg)

user_prompt = """请写出以下修仙小说章节正文：

【章节信息】
- 书名：仙道长青
- 卷：第一卷 凡尘磨剑
- 章：第1章 药田异象
- 字数目标：1500-2500字

【本章大纲】
主角林渡是青玄宗外门弟子，灵根资质平庸，被分配看守药田。
这一夜，他在药田深处发现一株枯萎的灵草根部发出微光。
挖开泥土后，发现一枚古朴的玉简，上面记载着一门早已失传的炼体功法。
但他不知道的是，这枚玉简的出土，已经惊动了某个沉睡了千年的存在。

【出场角色】
- 林渡：19岁，青玄宗外门弟子，三灵根资质，性格坚韧内敛

【场景】青玄宗后山药田，深夜，月光稀疏

请直接写出本章正文："""

from utils.llm_client import get_task_client, get_task_model
from utils.llm_client import _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p

client = get_task_client('writing')
model = get_task_model('writing')
temp = _llm_temperature('writing')
freq = _llm_frequency_penalty('writing')
pres = _llm_presence_penalty('writing')
top_p = _llm_top_p('writing')

print(f'Model={model} temp={temp} freq={freq} pres={pres} top_p={top_p}')
print(f'System: {len(system_prompt)}c User: {len(user_prompt)}c')
print()
print('=' * 40)
print('GENERATING...')
print('=' * 40)

resp = client.chat.completions.create(
    model=model, temperature=temp, frequency_penalty=freq,
    presence_penalty=pres, top_p=top_p, max_tokens=3072,
    messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ],
    extra_body={'chat_template_kwargs': {'enable_thinking': False}},
)

content = resp.choices[0].message.content
print(content)
print()
print('=' * 40)
print(f'Generated: {len(content)} chars')

# De-AI check
from skills.gen_deai_engine.skill import GenDeaiEngineSkill
class Ctx:
    def set_shared(s,k,v): pass
    def get_shared(s,k,d=None): return d
e = GenDeaiEngineSkill(Ctx())
r = e.analyze(content)
print(f'De-AI Score: {r["overall_score"]}/100')
for d in r['dimensions'][:6]:
    flag = '!!' if d['score'] < 50 else '--' if d['score'] < 70 else 'OK'
    print(f'  [{flag}] {d["name"]}: {d["score"]}')

# Save
ms = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.novel_test_xiuzhen', 'manuscripts', 'vol_01')
os.makedirs(ms, exist_ok=True)
with open(os.path.join(ms, 'ch_001_final.md'), 'w', encoding='utf-8') as fp:
    fp.write(content)
print('\nSaved to .novel_test_xiuzhen/manuscripts/vol_01/ch_001_final.md')
