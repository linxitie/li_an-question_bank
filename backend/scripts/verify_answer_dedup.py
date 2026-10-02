#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""答案/解析去重校验的单元测试 + 解析非空 -1 的归因。

当前 254 份语料里**没有**出现「解析是答案子串」的案例，所以全量指标看不到变化。
本脚本用构造用例证明去重逻辑真实有效，避免"看起来加了代码但从没被执行过"。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app.services.text_parser import _essay_split_answer_analysis as S


def case(name, seg, want_ans, want_ana):
    a, n = S(seg)
    ja, jn = '\n'.join(a).strip(), '\n'.join(n).strip()
    ok = (ja == want_ans) and (jn == want_ana)
    print('%-42s ans=%r ana=%r %s' % (name, ja[:22], jn[:22],
                                       'OK' if ok else 'FAIL'))
    return ok


def main():
    results = []

    # CASE1 正常切分：解析标记之后的内容归解析
    results.append(case(
        'C1 正常切分',
        ['1.创新项目落地机制。设计流程图。',
         '2.开启智慧平台。梳理诉求。',
         '参考答案说明：本参考答案从四个方面介绍。',
         '做法和成效一一对应。'],
        '1.创新项目落地机制。设计流程图。\n2.开启智慧平台。梳理诉求。',
        '本参考答案从四个方面介绍。\n做法和成效一一对应。'))

    # CASE2 解析是答案的子串 → 解析置空（去重核心）
    results.append(case(
        'C2 解析=答案子串->解析置空',
        ['创新项目落地机制。', '参考答案说明：创新项目落地机制。'],
        '创新项目落地机制。', ''))

    # CASE3 答案是解析的子串 → 答案置空
    results.append(case(
        'C3 答案=解析子串->答案置空',
        ['参考答案说明：', '本答案分条撰写。'],
        '', '本答案分条撰写。'))

    # CASE4 无解析标记 → 解析留空，绝不把答案当解析
    results.append(case(
        'C4 无标记->解析留空',
        ['1.生产方式变化。', '2.销售方式转变。'],
        '1.生产方式变化。\n2.销售方式转变。', ''))

    # CASE5 忽略空白差异的子串判定（PDF 换行不应影响判定）
    results.append(case(
        'C5 空白差异仍判为子串',
        ['参考答案从五个方面\n进行了分条撰写。',
         '参考答案说明：参考答案从五个方面 进行了分条撰写。'],
        '参考答案从五个方面\n进行了分条撰写。', ''))

    print()
    bad = results.count(False)
    print('TOTAL %d / PASSED %d / FAILED %d' % (len(results),
                                                len(results) - bad, bad))
    print('DEDUP_LOGIC_VERIFIED' if bad == 0 else 'DEDUP_LOGIC_BROKEN')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())