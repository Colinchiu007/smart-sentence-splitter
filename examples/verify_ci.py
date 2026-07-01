"""CI 验证脚本 — 本地模拟 GitHub Actions 跑一遍 (v0.8.3 新增).

模拟 test.yml 的核心步骤:
1. 装依赖
2. 跑单元测试
3. 跑集成测试
4. 跑性能基线
5. 跑 lint
6. 检查文档同步

用法:
    python examples/verify_ci.py
"""

import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = sys.executable


def step(name, cmd, cwd=None, check=True):
    """跑一步, 计时 + 显示结果。"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  $ {cmd}")
    t0 = time.perf_counter()
    r = subprocess.run(
        cmd, shell=True, cwd=cwd or ROOT,
        capture_output=True, text=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"  ⏱️  {elapsed:.1f}s")
    if r.stdout.strip():
        # 只显示最后 5 行
        lines = r.stdout.strip().split("\n")
        for line in lines[-5:]:
            print(f"  {line}")
    if r.returncode != 0 and check:
        print(f"  ❌ FAILED (exit {r.returncode})")
        if r.stderr.strip():
            lines = r.stderr.strip().split("\n")
            for line in lines[-5:]:
                print(f"  ERR: {line}")
        return False
    print(f"  ✅ PASSED")
    return True


def main():
    print("=" * 60)
    print("  CI 验证 (模拟 GitHub Actions test.yml)")
    print("=" * 60)

    results = []

    # 1. 装依赖
    results.append(step(
        "1. 安装依赖 (./.[all] + pytest)",
        f'"{PY}" -m pip install -e ".[all]" --quiet',
    ))

    if not all(results):
        print("\n❌ 前面步骤失败, 中断")
        sys.exit(1)

    # 2. 单元测试
    results.append(step(
        "2. 单元测试 (tests/unit/)",
        f'"{PY}" -m pytest tests/unit/ -q --tb=line',
    ))

    # 3. 集成测试
    results.append(step(
        "3. 集成测试 (tests/integration/)",
        f'"{PY}" -m pytest tests/integration/ -q --tb=line',
    ))

    # 4. 性能基线
    results.append(step(
        "4. 性能基线 (test_performance_baseline.py)",
        f'"{PY}" -m pytest "tests/unit/test_performance_baseline.py" -q --tb=line',
    ))

    # 5. lint (如果有 ruff)
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, check=True, timeout=5)
        results.append(step(
            "5. Lint (ruff check)",
            "ruff check src/ tests/ --quiet",
        ))
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("\n" + "="*60)
        print("  5. Lint (ruff check) — SKIPPED (ruff not installed)")

    # 6. 文档同步检查
    results.append(step(
        "6. 文档同步检查 (CHANGELOG.md)",
        f'grep -q "## \\[$(grep version pyproject.toml | head -1 | cut -d\\"\\" -f2)\\]" CHANGELOG.md || (echo "❌ CHANGELOG missing current version" && exit 1)',
    ))

    # 7. README 引用
    results.append(step(
        "7. README 引用 vX.Y.Z",
        f'grep -q "v$(grep version pyproject.toml | head -1 | cut -d\\"\\" -f2)" README.md || (echo "❌ README missing v$(...)" && exit 1)',
    ))

    # 8. AGENTS 版本
    results.append(step(
        "8. AGENTS.md 版本号",
        'grep -q "v0\\." docs/AGENTS.md',
    ))

    # 总结
    print(f"\n{'='*60}")
    print(f"  CI 验证总结")
    print(f"{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"  通过: {passed}/{total}")

    if passed == total:
        print(f"  ✅ 所有步骤通过 — CI 可上线")
        return 0
    else:
        print(f"  ❌ {total - passed} 步失败 — 需修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
