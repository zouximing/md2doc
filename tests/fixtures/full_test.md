# md2doc 全面测试文档

> 本文档用于测试 md2doc 对各类 Markdown 元素 + mermaid 图 + 数学公式的转换效果。
> 生成时间：2026-08-09。

## 1. 基础文本元素

### 1.1 段落与换行

这是一个普通段落。第一句。
同一行的第二句（软换行，pandoc 默认会合并为空格）。

这是一个新段落（上方有空行）。

### 1.2 强调样式

- **粗体文本**
- *斜体文本*
- ***粗斜体***
- ~~删除线~~
- `行内代码`
- 普通**混合**文本与*样式*

### 1.3 标题层级测试

# 一级标题（文档中通常只有一个）
## 二级标题
### 三级标题
#### 四级标题
##### 五级标题
###### 六级标题

## 2. 列表

### 2.1 无序列表

- 苹果
- 香蕉
  - 帝王蕉
  - 小米蕉
- 樱桃

### 2.2 有序列表

1. 第一步：准备数据
2. 第二步：清洗数据
3. 第三步：训练模型
    1. 加载训练集
    2. 前向传播
    3. 反向传播

### 2.3 任务列表

- [x] 已完成项
- [ ] 未完成项
- [ ] 另一个待办

### 2.4 混合嵌套列表

1. 项目一
    - 子项 A
    - 子项 B
        - 更深层子项
2. 项目二
    - 子项 C

## 3. 引用

> 这是一段引用。
>
> 引用内可以有多个段落。
>
> > 嵌套引用：引用中的引用。
>
> 引用内还可以有 **粗体**、*斜体*、`代码`。

## 4. 代码

### 4.1 行内代码

使用 `pip install md2doc` 安装，运行 `md2doc input.md -o output.docx`。

### 4.2 代码块（带语法高亮标记）

```python
def fibonacci(n: int) -> int:
    """计算斐波那契数。"""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


class Calculator:
    def __init__(self):
        self.history: list[int] = []

    def add(self, x: int, y: int) -> int:
        result = x + y
        self.history.append(result)
        return result
```

```bash
# 常用命令
git status
git add .
git commit -m "feat: add new feature"
```

```json
{
  "name": "md2doc",
  "version": "0.3.0",
  "dependencies": ["pandoc", "mmdc"],
  "features": ["mermaid", "math", "batch"]
}
```

### 4.4 普通代码块（无语言标记）

```
这是一段纯文本代码块。
保留所有    空格 与换行。
```

## 5. 链接与图片

### 5.1 链接

- 行内链接：[GitHub](https://github.com)
- 带标题的链接：[Google](https://google.com "搜索引擎")
- 自动链接：<https://www.python.org>
- 参考链接：[Python 官网][py]

[py]: https://www.python.org "Python"

### 5.2 URL 与邮箱

- 网址：https://example.com
- 邮箱：user@example.com

## 6. 表格

### 6.1 简单表格

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|---|---|:---:|---:|---|
| name | string | 是 | - | 名称 |
| age | int | 否 | 0 | 年龄 |
| active | bool | 否 | true | 是否激活 |
| tags | list | 否 | [] | 标签列表 |

### 6.2 对齐测试

| 左对齐 | 居中对齐 | 右对齐 |
|:---|:---:|---:|
| 左 | 中 | 右 |
| AAAA | BBBB | CCCC |

### 6.3 复杂表格

| 模块 | 功能 | 状态 | 备注 |
|---|---|---|---|
| md2doc.core | 核心转换 | ✅ 完成 | - |
| md2doc.mermaid | mermaid 渲染 | ✅ 完成 | 依赖 mmdc |
| md2doc.cli | 命令行 | ✅ 完成 | rich 美化 |
| md2doc.web | Web 界面 | ✅ 完成 | FastAPI |

## 7. 数学公式（TeX）

### 7.1 行内公式

欧拉恒等式 $e^{i\pi} + 1 = 0$ 是数学中最美的等式之一。
勾股定理 $a^2 + b^2 = c^2$。

### 7.2 块级公式

二次方程求根公式：

$$
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$

高斯积分：

$$
\int_{-\infty}^{\infty} e^{-x^2} \, dx = \sqrt{\pi}
$$

欧拉公式展开：

$$
e^{i\theta} = \cos\theta + i\sin\theta
$$

矩阵乘法：

$$
\begin{bmatrix}
a_{11} & a_{12} \\
a_{21} & a_{22}
\end{bmatrix}
\begin{bmatrix}
x_1 \\
x_2
\end{bmatrix}
=
\begin{bmatrix}
a_{11}x_1 + a_{12}x_2 \\
a_{21}x_1 + a_{22}x_2
\end{bmatrix}
$$

求和与极限：

$$
\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}, \qquad
\lim_{x \to 0} \frac{\sin x}{x} = 1
$$

> 注意：数学公式能否正确渲染为 Word 公式取决于 pandoc 是否启用 `--mathml` 等选项；
> 默认情况下 pandoc 会将 `$...$` 转换为 Word 原生公式对象（OMML）。

## 8. 分隔线

上方内容

---

下方内容

## 9. HTML 内联

<details>
<summary>点击展开详情</summary>

这是 details 折叠块的内容。pandoc 默认可能将其转为 docx 中的提示文字。

</details>

<kbd>Ctrl</kbd> + <kbd>C</kbd> 复制，<kbd>Ctrl</kbd> + <kbd>V</kbd> 粘贴。

<sub>下标</sub> 与 <sup>上标</sup>：H<sub>2</sub>O，X<sup>2</sup>。

<span style="color: red;">红色文字</span>（docx 可能不保留内联样式）。

## 10. Mermaid 图

### 10.1 流程图（Flowchart）

```mermaid
flowchart TD
    A[开始] --> B{是否登录?}
    B -- 是 --> C[加载用户数据]
    B -- 否 --> D[跳转登录页]
    D --> E[用户输入凭据]
    E --> F{凭据正确?}
    F -- 是 --> C
    F -- 否 --> D
    C --> G[展示主页]
    G --> H[结束]
```

### 10.2 序列图（Sequence Diagram）

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant B as 后端
    participant DB as 数据库

    U->>F: 点击"提交"按钮
    F->>B: POST /api/order
    B->>DB: INSERT INTO orders
    DB-->>B: 返回 order_id
    B-->>F: 201 Created {order_id}
    F-->>U: 显示"下单成功"

    Note over F,B: 异常分支
    B->>DB: 库存不足
    DB-->>B: 错误
    B-->>F: 400 Bad Request
    F-->>U: 提示"库存不足"
```

### 10.3 类图（Class Diagram）

```mermaid
classDiagram
    class Person {
        +String name
        +int age
        +String email
        +introduce() String
    }

    class Student {
        +String studentId
        +double gpa
        +study() void
    }

    class Teacher {
        +String employeeId
        +String department
        +teach() void
    }

    class Course {
        +String courseId
        +String title
        +int credits
        +getDescription() String
    }

    Person <|-- Student
    Person <|-- Teacher
    Student "many" o-- "many" Course : 选修
    Teacher "one" --> "many" Course : 教授
```

### 10.4 状态图（State Diagram）

```mermaid
stateDiagram-v2
    [*] --> 待审核
    待审核 --> 已发布: 审核通过
    待审核 --> 已拒绝: 审核驳回
    已发布 --> 已下架: 主动下架
    已发布 --> 待审核: 编辑修改
    已拒绝 --> 待审核: 修改后重新提交
    已下架 --> [*]
```

### 10.5 实体关系图（ER Diagram）

```mermaid
erDiagram
    USER ||--o{ ORDER : 下单
    ORDER ||--|{ ORDER_ITEM : 包含
    PRODUCT ||--o{ ORDER_ITEM : 出现在

    USER {
        int id PK
        string name
        string email
    }
    ORDER {
        int id PK
        int user_id FK
        datetime created_at
    }
    ORDER_ITEM {
        int id PK
        int order_id FK
        int product_id FK
        int quantity
    }
    PRODUCT {
        int id PK
        string name
        decimal price
    }
```

### 10.6 甘特图（Gantt）

```mermaid
gantt
    title md2doc 开发计划
    dateFormat  YYYY-MM-DD
    section 核心功能
    需求分析       :done,    a1, 2026-07-01, 5d
    架构设计       :done,    a2, after a1, 3d
    核心转换实现   :done,    a3, after a2, 7d
    section 扩展功能
    mermaid 支持   :done,    b1, after a3, 4d
    Web 界面       :active,  b2, after b1, 5d
    section 收尾
    测试与文档     :         c1, after b2, 4d
    发布 v1.0      :         c2, after c1, 2d
```

### 10.7 饼图（Pie）

```mermaid
pie title 用户来源占比
    "搜索引擎" : 45
    "直接访问" : 25
    "社交媒体" : 20
    "其他"     : 10
```

### 10.8 用户旅程图（User Journey）

```mermaid
journey
    title 用户购物体验
    section 浏览商品
      打开首页: 5: 用户
      搜索商品: 4: 用户
      查看详情: 4: 用户
    section 下单支付
      加入购物车: 5: 用户
      提交订单: 3: 用户
      完成支付: 2: 用户, 系统
    section 售后
      收到商品: 5: 用户
      评价晒单: 4: 用户
```

### 10.9 Git 图（Git Graph）

```mermaid
gitGraph
    commit id: "init"
    commit id: "feat: core"
    branch develop
    checkout develop
    commit id: "feat: mermaid"
    commit id: "feat: web"
    checkout main
    merge develop id: "release v0.3"
    commit id: "fix: chrome"
```

## 11. 边界情况测试

### 11.1 空段落（下方应该看不到内容）



### 11.2 很长的行

这是一行非常长的中文文本，没有任何换行符，用来测试 pandoc 是否能正确进行软换行处理，以及 Word 是否能根据页面宽度自动折行显示，应该不会溢出页面边界才对。

### 11.3 转义字符

\*这不是斜体\*，\`这不是代码\`，\#这不是标题，\\这是反斜杠本身。

### 11.4 Emoji 与特殊符号

- Emoji：😀 🚀 📦 ✅ ❌ ⚠️ 🎉
- 数学符号：± × ÷ ≈ ≠ ≤ ≥ ∞ ∑ ∏ ∫ √ π
- 箭头：← → ↑ ↓ ↔ ⇒ ⇔
- 中文标点：「」『』【】（）《》——……

### 11.5 连续的引用嵌套与列表混合

> 引用开始
> 1. 引用内的有序列表第一项
> 2. 第二项
>
> - 引用内的无序列表
> - 第二项
>
> 引用结束

## 12. 综合收尾

如果以上所有元素都能在生成的 docx 中正确显示：
- 标题层级清晰
- 表格对齐无误
- 数学公式渲染为 Word 公式对象
- 9 张 mermaid 图全部以 PNG 形式嵌入
- 列表/引用/代码块完整保留

那么 md2doc 的转换能力可以认为**测试通过** ✅。

---

*文档结束*
