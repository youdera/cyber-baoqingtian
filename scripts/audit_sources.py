"""Automatically inspect the fixed official source catalog, never personal lists."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from wuzhong.source_audit import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='data/source-audit')
    args = parser.parse_args()
    report = audit(ROOT, args.data_dir, progress=lambda done,total: print(f'Source probes: {done}/{total}', flush=True))
    lines = ['# 官方来源目录巡检', '', '仅检查登记入口当前可访问性及首页解析，不代表正式接入或历史完整覆盖。', '']
    for row in report['results']:
        lines.append(f"- {row['name']}：{row['status']}；识别{row['recognized']}条。{row['reason']}")
    text = '\n'.join(lines)+'\n'
    Path(args.data_dir, 'report.md').write_text(text, encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream: stream.write(text)


if __name__ == '__main__': main()
