# RAG 质量评测与维护

本项目把工程测试、检索评测和模型辅助答案评分分开。测试通过率和代码覆盖率不代表回答准确率。
模型评分也不是人工验收结论，特别是生成器和评分器使用同一模型时。

## 数据与来源

固定集合包含 60 条样本、215 份资料：
- XQuAD 中文：20 条，在所选 20 个段落中检索。
- HotpotQA：20 条，保留每题原始的 10 个候选段落及句子级支持事实。
- 项目边界：20 条，覆盖资料不足、空库、库外、部分回答、指代、纠错、换话题、干扰与澄清。

项目边界样本由 Codex 编写，尚待独立人工复核；公开样本继承原始标注。
开发/保留切片分别为 37/23 条，按固定 group_id 分组；其中可计算证据指标的样本为 32/22 条。
本轮开发查看过全量输出，因此不能将保留切片描述为完全未触碰的独立测试集。
公开基准也可能已进入模型预训练，结果不能外推为真实业务准确率。

数据位于 evals/data/。manifest.json 固定种子、原始下载哈希和产物哈希。
许可与作者见 [LICENSES](../evals/LICENSES.md)。HotpotQA 使用维护者 Hugging Face 发布文件，
Kaggle 镜像仅为发现入口，未使用 Kaggle 账号或宣称从 Kaggle 下载。

重建：
```bash
python -m app.evaluation.build_dataset --xquad path/to/xquad.zh.json --hotpot path/to/hotpot.json
```
Hotpot 输入可以是原始 distractor JSON，也可以是 manifest 中公开 rows 接口的响应。
重建后需要对照 manifest 检查哈希；数据升级应独立更新数据版本，不能混用不同集合进行版本对比。
答案、标签和支持事实只进入评分器，生成器的输入中只有问题、指定历史和检索资料。

## 安装和运行

```bash
python -m venv .venv
# 激活虚拟环境后
pip install -e ".[dev]"
pytest --cov=app
ruff check .
```

Windows 环境迁移后，旧 .venv 可能仍指向不存在的 Python。应使用当前解释器重新建立环境；
不能把“解释器启动失败”当成项目测试失败。本次本地验证使用 Python 3.13.14。

离线流程冒烟不需要网络、模型或密钥：
```bash
python -m app.evaluation run --task e2e --embedding mock --llm mock --split all --output artifacts/smoke
```
mock 分数只验证评测管线，不能作为回答质量成绩。

真实检索（首次需要下载 BGE）：
```bash
python -m app.evaluation run --task retrieval --embedding real --split dev --output artifacts/retrieval
```

真实端到端（从环境或 .env 读取模型配置，会产生模型调用费用）：
```bash
python -m app.evaluation run --task e2e --embedding real --llm real --split all --workers 4 --output artifacts/run
python -m app.evaluation judge artifacts/run --output artifacts/judged --workers 4
```

生成隔离评测可以使用 --task oracle：它向生成器提供标准证据覆盖的切块。
该模式用于诊断生成，不包含检索难度，不能与 e2e 的分数混比。
--dataset project / xquad_zh / hotpotqa 可以选择切片。
固定历史属于 teacher-forced 场景，不是自由生成的完整多轮 rollout。

每次 output 必须是新目录。运行器使用独立内存数据库，不连接或清理正在使用的知识库。
原始问题、上下文、模型 messages/output、引用、耗时、错误、请求模型名、参数、
提示词和运行源码哈希都写入 cases.jsonl / metadata.json。summary.json 与 report.md 提供切片汇总。
外部模型别名和推理实现会变化，保存配置也不意味着逐字输出完全可复现。

评分格式异常会保留原始输出并标记 judge_error，不会当作通过。
可仅重试失败项，既有成功结果复用，历史尝试保留：
```bash
python -m app.evaluation judge artifacts/judged --retry-errors --output artifacts/judged-retry
```

## 指标解释

| 指标 | 含义与边界 |
|---|---|
| evidence_recall_at_k | 标准证据跨度被前 K 个切块完整覆盖的比例；跨块按原文位置合并 |
| MRR | 首个与标准证据有跨度交集的切块的倒数排名 |
| context_precision_at_k | 前 K 个切块中与标注证据有交集的比例；未标出的相关内容可能被低估 |
| required_fact_coverage | 指定事实的词面命中比例，不是语义正确率 |
| answer_token_f1 | 中英文 token 重叠诊断，不适合单独评价长答案 |
| semantic_correctness / completeness | 模型按 0/1/2 判断错误、部分正确、正确，再归一化；须人工抽查 |
| faithfulness | 评分器提取的事实中，得到检索资料支持的比例 |
| citation_support | 带行内引用的事实中，所指证据实际支持该事实的比例 |
| citation_coverage | 所有事实中，具有支持性行内引用的比例 |
| inappropriate_refusal | 可回答或可部分回答样本中，被判为不当拒答的比例 |
| inappropriate_answer | 应拒答样本中，被判行为不匹配的比例，需结合原始理由复核 |

没有相关证据标注的负例不计算 Recall/MRR；没有事实陈述的拒答不计算忠实性和引用比例。
null 是不适用或未评测，绝不是满分。超时和无效评分单列错误。
每个均值带 n，拒答变化会改变忠实性等指标的有效样本数量，不能忽略分母直接比较。
评分器依据参考答案评价正确性，依据实际召回资料评价忠实性，两者不能互相替代。

版本比较：
```bash
python -m app.evaluation compare artifacts/baseline artifacts/candidate --output artifacts/comparison.json
python -m app.evaluation compare artifacts/baseline artifacts/candidate --output artifacts/gate.json --fail-on-regression --metric semantic_correctness --metric behavior_match_judged --max-regression 0.02
```
集合哈希、任务、切片、样本 ID、评分模型和评分提示词不一致时拒绝比较。
无评分或分母不同的指标不能直接作为门槛。门槛的方向默认为越高越好，请勿用于错误数量等反向指标。
同一模型评分有自偏好和随机波动，本轮结果未经过独立人工校准或重复实验显著性验证。

## 线上回答策略与开关

- 每一轮都检查证据；空库追问也会拒答。
- 短追问用近期用户问题辅助检索，历史助手陈述不作为事实证据。
- 检索过滤已删除、其他用户的资料。
- 每条事实输出逐字证据和来源编号，服务端核验原文存在、编号有效。
- 默认额外调用模型核验陈述与引用的语义支持关系。
- 部分陈述未通过时只保留通过部分并说明不足；全部不通过时拒答。
- 澄清、拒答和缺失说明使用固定文本，避免自由 message 混入未经核验的事实。
- SSE 在核验完成后发送最终答案；这会延后首字显示，不再实时透出未经校验的草稿。
- 质量状态及原始模型输出保存在消息 quality 中。model_verified 是模型判断，不是事实保证。

| 环境变量 | 默认值 | 用途 |
|---|---|---|
| RAG_KEYWORD_IDF_ENABLED | true | 对稀有词加权，提升混合检索中关键词的区分能力 |
| RAG_GROUNDED_OUTPUT_ENABLED | true | 启用结构化事实和引用；关闭后回到普通生成且标为未检查 |
| RAG_VERIFY_CLAIMS_ENABLED | true | 额外执行模型语义核验；关闭后仅校验格式与原文存在 |

关闭语义核验不能宣称“引用支持性已验证”。不要将模型核验状态等同于零幻觉。
本版本没有承诺增加跨编码器、引入专用向量库、完全解决多跳或所有指代场景。
后续应先人工复核失败样本，再按检索、证据完整性、生成和评分器错误分别改进。

## 发布与维护

CI 默认执行功能测试和离线评测冒烟，上传报告。真实质量回归是手动 workflow_dispatch，
需要仓库配置 DEEPSEEK_API_KEY secret；本次没有向 GitHub 上传本地密钥。
发布报告目录见 evals/reports/v1.2.0/。报告中的 raw 输出和判断理由应一并保留。

本次环境未安装 Docker，未实际构建容器镜像；已更新镜像复制规则与数据许可。

评测数据以 LF 纳入 Git。发布报告的 scored metadata 使用规范化后的集合哈希，
其原始值保存在 metadata.original.json；原始生成运行记录位于 *-raw 目录。
