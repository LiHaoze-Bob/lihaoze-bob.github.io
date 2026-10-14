---
tags:
- Ollama
- macOS
title: Can I Run AI
---
# Can I Run AI {#can-i-run-ai}

从 [CanIRun.ai](https://www.canirun.ai/) 的硬件推荐出发，尝试在 Intel Mac 上运行 Qwen，并了解模型、数据、Agent 和实时信息的边界。


!!! summary "核心认识"
    对这台 Intel Mac，优先尝试 1B–4B 的小型量化模型，适合短文本整理、改写和有限的代码辅助；实时新闻需要外部资料，Agent 需要执行工具的程序，二者都不会因为模型下载到本地而自动获得。


## 1. 我的硬件 {#1-我的硬件}


| 项目 | 本机读取结果 | 如何理解 |
|---|---|---|
| CPU | Intel Core i7，2.6 GHz，6 核，支持超线程 | x86_64 架构；本次未成功单独读取逻辑线程数 |
| RAM | 16 GB | 系统、应用、模型运行共同使用 |
| 集成显卡 | Intel UHD Graphics 630，动态显存上限 1536 MB | 使用共享内存，不是 4 GB 独立显存 |
| 独立显卡 | AMD Radeon Pro 5300M，4 GB VRAM | 有显卡不代表所选推理软件支持它 |

### 参数解释 {#参数解释}

| 参数          | 意义            | 常见误解                                |
| ----------- | ------------- | ----------------------------------- |
| GPU         | 显卡型号          | 浏览器检测到的显卡未必是推理程序使用的显卡               |
| VRAM        | 显存容量          | 不能与系统 RAM 简单相加，作为任意后端的可用容量          |
| BW，GB/s     | 内存/显存带宽       | 不是网速；网站用它估算生成速度                     |
| RAM         | 系统内存          | 浏览器可能只报告粗略范围，截图的 ≥8 GB 不等于实际只有 8 GB |
| Cores       | 网站显示的核心数指标    | 不能未经核对就当作物理核心数                      |
| 0.8B、2B、4B  | 参数量，B 表示十亿    | 参数量不是磁盘大小，也不是准确率                    |
| Q4_K_M、Q8_0 | 量化格式          | 位宽越低通常越省空间，但能力和后端性能也受影响             |
| tok/s       | 每秒生成的 token 数 | token 不严格对应一个汉字；也不包含全部首字等待时间        |
| S–F         | 网站的运行适配等级     | 不是模型智能排名，更不是本机实测                    |
| AA          | 网站的能力评分字段     | 本次未核实评分版本和口径，不用于选型结论                |

## 2. 模型大小、磁盘与运行内存 {#2-模型大小磁盘与运行内存}

权重体积可粗略理解为：

```text
权重大小 ≈ 参数量 × 每个参数的存储位数 ÷ 8
运行内存 ≈ 权重 + 上下文状态/缓存 + 临时计算缓冲 + 其他组件
整机内存需求 = 模型运行内存 + macOS + 其他应用
```


### 候选模型 {#候选模型}

| 模型标签 | 下载体积约 | 适合尝试的任务 | 本机选型判断 |
|---|---:|---|---|
| `qwen3.5:0.8b` | 1.0 GB | 短文本分类、简单改写 | 入门试验，能力有限 |
| `qwen3.5:2b` | 2.7 GB | 中文短文本、摘要、轻量问答 | 已下载；优先建立实测基线 |
| `qwen3.5:4b` | 3.4 GB | 更复杂的整理与解释 | 可尝试对照 2B，不能预先承诺效果和速度 |
| `qwen2.5-coder:3b` | 1.9 GB | 单函数代码解释、补全、小修改 | 成熟的代码专项候选 |
| `gemma3:1b` | 815 MB | 轻量文本任务 | 可作不同模型家族的对照；1B 版是纯文本 |
| `deepseek-r1:1.5b` | 1.1 GB | 体验推理输出 | 蒸馏小模型，不代表完整 R1 的能力 |
| `llama3.2:3b` | 2.0 GB | 英文短文本与摘要 | 中文任务不作为首选；官方支持语言列表不含中文 |
| `phi4-mini` | 2.5 GB | 数学、逻辑类试验 | 需核验答案，非英文表现有差异 |

容量来源：[Qwen 3.5](https://ollama.com/library/qwen3.5/tags)、[Qwen Coder](https://ollama.com/library/qwen2.5-coder)、[Gemma 3](https://ollama.com/library/gemma3)、[DeepSeek-R1](https://ollama.com/library/deepseek-r1/tags)、[Llama 3.2](https://ollama.com/library/llama3.2)、[Phi-4 Mini](https://ollama.com/library/phi4-mini)。

本次我尝试的是qwen3.5:2b

### 怎么测试 {#怎么测试}
```bash
# 运行时显示耗时统计；至少比较冷启动和模型已加载两种情况
ollama run qwen3.5:2b --verbose

# 查看当前加载模型、内存与处理设备
ollama ps
```


## 3. 模型部署 {#3-模型部署}

Ollama 负责下载、加载模型并提供推理服务，macOS 图形应用提供聊天界面，其他应用也能调用后台服务。

Ollama也提供云端模型

```bash
ollama --version
ollama run qwen3.5:2b   # 缺少模型时先下载，之后进入聊天
ollama ls              # 磁盘上已安装的模型
ollama ps              # 当前加载到内存的模型
ollama stop qwen3.5:2b  # 卸载运行中的模型，保留磁盘文件
ollama rm qwen3.5:2b  #卸载本地模型
```

在交互聊天中，可以先采用较小上下文：

```text
/set parameter num_ctx 4096
```


[Ollama CLI 命令](https://docs.ollama.com/cli)

## 4. 本地文件 {#4-本地文件}

| 数据             | 本机路径                                                         |
| -------------- | ------------------------------------------------------------ |
| 模型权重           | `/Users/bob.li/.ollama/models/blobs/`                        |
| 模型标签与权重映射      | `/Users/bob.li/.ollama/models/manifests/`                    |
| Ollama 图形应用数据库 | `/Users/bob.li/Library/Application Support/Ollama/db.sqlite` |
| 数据库写前日志及共享状态   | 同目录的 `db.sqlite-wal`、`db.sqlite-shm`                         |
| 终端输入历史         | `/Users/bob.li/.ollama/history`，不能视为完整问答备份                   |
| 应用和服务日志        | `/Users/bob.li/.ollama/logs/`                                |

这些位置属于 Ollama 自己的界面。通过其他 Agent/聊天前端调用 Ollama 时，对话通常由那个前端保存，不能假定所有对话都在 Ollama 的数据库里。推理服务与对话存储是不同职责。


## 5. Agent 能力 {#5-agent-能力}

可以用“模型 + 工具 + 执行循环 + 权限与状态管理”理解一个 Agent：模型提出动作，宿主程序验证并执行，再把结果交回模型。

Ollama 支持 tool calling，官方提供多轮 Agent loop 示例；读写文件、执行命令或搜索的具体实现仍由程序或接入的 Agent 提供。[Ollama Tool Calling](https://docs.ollama.com/capabilities/tool-calling)
*

### Codex 集成 {#codex-集成}

`model` 是模型名称，`model_provider` 是提供商/请求路由。只修改模型名，不能保证请求转发到正确后端。

```bash
# 在终端启动一个本地模型会话；先确保 Ollama 服务可用
codex --oss --local-provider ollama -m qwen3.5:2b
```

```shell
ollama launch codex --model qwen3.5:2b #在codex客户端使用ollama模型
ollama launch codex --restore   #恢复codex原来配置
```

## 6. 实验：今天三条新闻 {#6-实验今天三条新闻}

**2026-09-04 向本地 Qwen 提问“给出今天的三条新闻”，模型给出的日期是 `2025-09-06`。


错误日期不等于模型知识截止日期。它可能来自上下文、提示处理问题或无依据生成，不能仅凭一个日期确定原因。此前回答“并未获取新闻，只是在编造”的语气过于确定，应改为待验证的解释。

一个基础对照提示词如下，每次测试替换成真实日期：

```text
当前日期是 2026-09-05，时区 Asia/Shanghai。
本次没有提供联网工具或新闻资料。
请给出今天的三条新闻；如果无法验证，请明确说明缺少实时资料，不得猜测新闻或链接。
```



## 7. 使用价值 {#7-使用价值}
- 私密数据
- 敏感内容的本地处理


!!! hint
    由于本机算力有限，暂时无法部署更加高级的模型，所以还在实验阶段，无法真正地加入工作流。
