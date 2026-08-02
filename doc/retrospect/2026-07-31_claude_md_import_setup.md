# 让文档在 Claude for VSCode 中总是被优先读到（流程模式）

> 日期: 2026-07-31
> 状态: ✅ 已验证生效
> 适用: 任何"想让某个文件每次会话都自动进入 Claude 上下文"的场景

---

## 一、需求背景

`doc/standards.md`（文档规范）只在 r2_integration 目录内、且由人主动打开时才会被
Claude 看到。VSCode 多根工作区（robot.code-workspace）下主工作区是 STM32_Now，
Claude 会话根本不会加载 r2_integration 下的任何内容 → 规范形同虚设。

**目标**：让 standards.md 在 Claude for VSCode 的每个新会话中总是自动加载。

---

## 二、机制：Claude Code 的 CLAUDE.md 加载链

每次会话启动时按顺序自动加载：

```
① 用户级  ~/.claude/CLAUDE.md        ← 所有项目、所有会话都读
② 项目级  从会话 cwd 向上查找 / git 根的 CLAUDE.md
```

关键特性：
- **`@路径` 导入语法**：CLAUDE.md 里写 `@文件路径`，启动时把该文件**全文展开**注入上下文
- 项目级只加载 cwd 向上路径上的第一个 CLAUDE.md；多根 VSCode 工作区里，
  非主工作区目录下的 CLAUDE.md 不会被加载
- CLAUDE.md 只在**会话启动时**加载，当前会话不重载

---

## 三、方案（两层保障）

### 第 1 层：用户级全局导入（保证"总是"）

`~/.claude/CLAUDE.md`（不存在则创建）：

```markdown
# 全局工作偏好

## 文档规范（每次修改文档前先读）

@/home/lin/Lin_workspace/r2_integration/doc/standards.md
```

- 绝对路径，任何项目、任何 cwd 都命中
- 缺点：全局注入，所有项目的会话都会带上这份内容

### 第 2 层：项目级导入（就近兜底）

`r2_integration/CLAUDE.md`（在包/仓库内）：

```markdown
# R2 集成工作区（r2_integration）

> 代码/文档修改前先读文档规范（自动注入）：
> @doc/standards.md
```

- 相对路径基于 CLAUDE.md 所在目录解析
- 当会话直接在 r2_integration 内工作时也生效

---

## 四、验证

新会话中直接问 Claude："文档规范 1.8 节的规则是什么" → 能准确回答即加载成功。
（本次已实测生效 ✅）

---

## 五、注意事项

| 项 | 说明 |
|:--|:--|
| 生效时机 | 新会话/重启 VSCode；当前会话不会重载 |
| token 开销 | 注入文件全文（standards.md ~290 行 ≈ 3~4k tokens），可接受 |
| 导入内容 | `@` 导入会展开全文，不适合超长文件；想只带重点就写精简摘要+文件路径 |
| git | 项目级 CLAUDE.md 随仓库提交；用户级在 `~/.claude/`，不在任何仓库 |
| 冲突 | 用户级内容对所有项目生效，放通用规则；项目专属规则放项目级 |

---

## 六、可复用步骤（流程模式）

1. 确定要常驻上下文的文件（规范/记忆/偏好）
2. 若需要**所有项目**生效 → 写入 `~/.claude/CLAUDE.md` 用 `@绝对路径` 导入
3. 若只需要**某项目内**生效 → 在项目根放 `CLAUDE.md` 用 `@相对路径` 导入
4. 新会话验证：问一句只有该文件里有的内容，能答对即生效
