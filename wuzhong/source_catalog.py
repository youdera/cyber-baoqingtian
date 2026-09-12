"""Reviewed official entry points. Candidates are not enabled collection adapters."""
from .notices import SOURCES
from .portal_seeds import DIRECTORY_SEEDS

CANDIDATES = [
    dict(id='scs2026', name='国家公务员局 · 2026招录专题', owner='国家公务员局', url='https://bm.scs.gov.cn/kl2026/', kind='国考', region=''),
    dict(id='mohrss_public', name='人社部 · 中央和国家机关事业单位拟聘公示', owner='人力资源和社会保障部', url='https://www.mohrss.gov.cn/SYrlzyhshbzb/fwyd/SYkaoshizhaopin/zyhgjjgsydwgkzp/nprygs/', kind='事业单位', region=''),
    dict(id='jiangsu', name='江苏先锋 · 通知公告', owner='江苏省委组织部', url='https://www.jsxf.gov.cn/tzgg/index.html', kind='', region='江苏'),
    dict(id='beijing', name='首都之窗 · 公务员招考', owner='北京市人民政府', url='https://www.beijing.gov.cn/gongkai/rsxx/gwyzk/', kind='省考', region='北京'),
    dict(id='beijing_jxj', name='北京经信局 · 人事信息', owner='北京市经济和信息化局', url='https://jxj.beijing.gov.cn/zwgk/rsxx/', kind='', region='北京'),
    dict(id='zhejiang', name='浙江人社厅 · 拟聘公示', owner='浙江省人力资源和社会保障厅', url='https://rlsbt.zj.gov.cn/col/col1229743684/index.html', kind='事业单位', region='浙江'),
    dict(id='moe', name='教育部 · 机关公务员招录', owner='教育部', url='https://www.moe.gov.cn/s78/A04/gongzuo/moe_450/', kind='国考', region=''),
]


def catalog():
    entries = [dict(s, enabled=True) for s in SOURCES] + [
        dict(s, enabled=False, max_pages=1, history=False, note='候选入口：尚未接入正式公告索引，巡检只检查当前目录。')
        for s in CANDIDATES + DIRECTORY_SEEDS if s['id'] not in {enabled['id'] for enabled in SOURCES}
    ]
    for entry in entries:
        if not entry.get('portal'): continue
        base = entry['url'].rstrip('/')
        entry['linked_source_ids'] = [s['id'] for s in SOURCES
            if s['url'].split('#')[0].rstrip('/') == base
            or s['url'].startswith(base + '/')
            or s.get('provenance', '').rstrip('/') == base]
    return entries
