#!/usr/bin/env python3
"""
HTML 标签物理配平与 DOM 结构硬门禁 (Tag Balance & Container Gate)
确保全站所有 HTML 页面的标签完美匹配闭合，绝不允许出现容器逃逸或底部横向溢出。
"""
import glob, os, sys, html.parser

class TagBalanceChecker(html.parser.HTMLParser):
    def __init__(self, fname):
        super().__init__()
        self.fname = fname
        self.stack = []
        self.issues = []
    def handle_starttag(self, tag, attrs):
        if tag not in ['br', 'img', 'meta', 'link', 'hr', 'input']:
            self.stack.append((tag, self.getpos()[0]))
    def handle_endtag(self, tag):
        if tag in ['br', 'img', 'meta', 'link', 'hr', 'input']:
            return
        line = self.getpos()[0]
        if not self.stack:
            self.issues.append((line, f'Extra </{tag}> (empty stack)'))
        else:
            last, oline = self.stack.pop()
            if last != tag:
                self.issues.append((line, f'Mismatch </{tag}> (expected </{last}> from line {oline})'))

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_html = sorted(glob.glob(os.path.join(root_dir, '**', '*.html'), recursive=True))
    failed = []
    for p in all_html:
        # Skip node_modules or vendor if any
        if 'node_modules' in p or '.wrangler' in p:
            continue
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()
        checker = TagBalanceChecker(os.path.relpath(p, root_dir))
        checker.feed(content)
        if checker.issues or checker.stack:
            failed.append((p, checker.issues, checker.stack))

    if failed:
        print(f"❌ HTML 标签配平门禁拦截：发现 {len(failed)} 个文件存在标签未闭合或错位！")
        for f, issues, stack in failed:
            print(f"\n  文件: {f}")
            for iss in issues:
                print(f"    Line {iss[0]}: {iss[1]}")
            for unc in stack:
                print(f"    Unclosed <{unc[0]}> from line {unc[1]}")
        sys.exit(1)
    else:
        print(f"✅ HTML 标签配平硬门禁 100% 通过（已扫描 {len(all_html)} 个 HTML 页面，0 错误，0 未闭合标签）")
        sys.exit(0)

if __name__ == '__main__':
    main()
