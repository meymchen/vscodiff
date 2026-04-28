# vscodiff

VS Code diff 算法的 Python 实现，参考自 VS Code 源码。

## 特性

- Myers 差分算法（`O(ND)` 复杂度）
- 行级差分 + 子词精炼
- 支持超时控制（可设置单次 diff 最大耗时）
- LRU 缓存，重复请求直接命中
- 支持移动检测（move detection）
- 完整类型标注（`py.typed`）

## 安装

**推荐使用 uv：**

```bash
uv add vscodiff
```

**备选 — 使用 pip：**

```bash
pip install vscodiff
```

需要 Python ≥ 3.12。

## 快速上手

```python
from vscodiff import VSCDiff

diff = VSCDiff()

# 计算两段文本的差异
result = diff.compute_diff("hello\nworld", "hello\nthere\nworld")

for change in result.changes:
    print(f"  原始行 {change.original}: {change.inner_changes}")
```

## API

### `VSCDiff`

主入口。通过 `VSCDiffOptions` 配置：

```python
from vscodiff import VSCDiff, VSCDiffOptions, DiffOptions

options = VSCDiffOptions(
    diff_options=DiffOptions(
        ignore_trim_whitespace=True,   # 忽略首尾空白
        max_computation_time_ms=1000,  # 最大计算时间（毫秒）
        compute_moves=False,           # 是否检测移动
        diff_algorithm="advanced",     # 算法：advanced 或 legacy
    ),
    cache_size=100,  # 缓存大小
)
diff = VSCDiff(options)
result = diff.compute_diff(original_text, modified_text)
```

### 核心类型

| 类型 | 说明 |
|------|------|
| `VSCDiff` | 主 diff 引擎 |
| `DocumentDiff` | 结果：identical, quit_early, changes, moves |
| `DetailedLineRangeMapping` | 变更行范围，含字符级内部差异 |
| `RangeMapping` | 字符级差异范围 |
| `LinesDiff` | 原始行 diff 输出（changes + moves + timeout） |

## 协议

MIT
