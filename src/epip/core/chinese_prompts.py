# ruff: noqa: E501
"""自定义 LightRAG 提取 prompt，针对中文数据和 qwen2.5 模型优化。"""

from lightrag.prompt import PROMPTS

# 中文优化的实体提取系统提示词
CHINESE_ENTITY_EXTRACTION_SYSTEM_PROMPT = """---角色---
你是一位知识图谱专家，负责从输入文本中提取实体和关系。

---指令---
1. **实体提取与输出：**
   * **识别：** 从输入文本中识别清晰定义且有意义的实体。
   * **实体详情：** 对于每个识别的实体，提取以下信息：
     * `entity_name`：实体名称。使用标题大小写（每个重要词的首字母大写）。确保整个提取过程中**命名一致**。
     * `entity_type`：使用以下类型之一对实体进行分类：`{entity_types}`。如果没有合适的类型，归类为 `Other`。
     * `entity_description`：基于输入文本提供简洁但全面的实体属性和活动描述。
   * **输出格式 - 实体：** 每个实体输出4个字段，用 `{tuple_delimiter}` 分隔，写在一行。第一个字段**必须**是字符串 `entity`。
     * 格式：`entity{tuple_delimiter}实体名称{tuple_delimiter}实体类型{tuple_delimiter}实体描述`

2. **关系提取与输出：**
   * **识别：** 识别已提取实体之间直接、明确且有意义的关系。
   * **关系详情：** 对于每个关系，提取以下5个字段：
     * `source_entity`：源实体名称。
     * `target_entity`：目标实体名称。
     * `relationship_keywords`：总结关系性质的关键词，多个关键词用逗号 `,` 分隔。
     * `relationship_description`：关系的简洁解释。
   * **输出格式 - 关系：** 每个关系输出5个字段，用 `{tuple_delimiter}` 分隔，写在一行。第一个字段**必须**是字符串 `relation`。
     * 格式：`relation{tuple_delimiter}源实体{tuple_delimiter}目标实体{tuple_delimiter}关系关键词{tuple_delimiter}关系描述`

3. **分隔符使用：**
   * `{tuple_delimiter}` 是字段分隔符，**不要在其中填充内容**。

4. **输出顺序：**
   * 先输出所有实体，再输出所有关系。

5. **完成信号：**
   * 在所有实体和关系提取完成后，输出 `{completion_delimiter}`。
   * **重要：必须输出完成信号！**

---示例---
{examples}
"""

CHINESE_ENTITY_EXTRACTION_USER_PROMPT = """---任务---
从下方"待处理数据"中提取实体和关系。

---要求---
1. 严格遵守格式要求。
2. 只输出实体和关系列表，不要输出任何解释性文字。
3. **最后必须输出 `{completion_delimiter}` 作为完成标记。**
4. 输出语言：{language}。

---待处理数据---
<实体类型>
[{entity_types}]

<输入文本>
```
{input_text}
```

<输出>
"""

CHINESE_EXAMPLES = [
    """<实体类型>
["政策","组织","人物","地点","日期","指标","疾病","预算"]

<输入文本>
```
2023年，国家卫生健康委员会发布了《健康中国行动（2023-2030年）》，要求各地医疗机构加强慢性病防治工作。北京市卫健委主任李明表示，将投入50亿元用于基层医疗设施建设。
```

<输出>
entity<|#|>健康中国行动<|#|>政策<|#|>国家卫生健康委员会发布的健康行动计划，时间跨度为2023-2030年
entity<|#|>国家卫生健康委员会<|#|>组织<|#|>中国国家级卫生健康管理机构
entity<|#|>北京市卫健委<|#|>组织<|#|>北京市卫生健康管理机构
entity<|#|>李明<|#|>人物<|#|>北京市卫健委主任
entity<|#|>50亿元<|#|>预算<|#|>用于基层医疗设施建设的投入金额
entity<|#|>慢性病<|#|>疾病<|#|>需要长期防治的疾病类型
relation<|#|>国家卫生健康委员会<|#|>健康中国行动<|#|>发布,制定<|#|>国家卫生健康委员会发布了健康中国行动计划
relation<|#|>健康中国行动<|#|>慢性病<|#|>防治,要求<|#|>健康中国行动要求加强慢性病防治工作
relation<|#|>李明<|#|>北京市卫健委<|#|>任职,领导<|#|>李明担任北京市卫健委主任
relation<|#|>北京市卫健委<|#|>50亿元<|#|>投入,拨款<|#|>北京市卫健委将投入50亿元用于医疗设施建设
<|COMPLETE|>

""",
]


def apply_chinese_prompts():
    """应用中文优化的 prompt 到 LightRAG。"""
    PROMPTS["entity_extraction_system_prompt"] = CHINESE_ENTITY_EXTRACTION_SYSTEM_PROMPT
    PROMPTS["entity_extraction_user_prompt"] = CHINESE_ENTITY_EXTRACTION_USER_PROMPT
    PROMPTS["entity_extraction_examples"] = CHINESE_EXAMPLES


def get_chinese_entity_types() -> list[str]:
    """返回适合中文政策数据的实体类型。"""
    return [
        "政策",  # Policy
        "组织",  # Organization
        "人物",  # Person
        "地点",  # Location
        "日期",  # Date
        "指标",  # Metric
        "疾病",  # Disease
        "预算",  # Budget
        "法规",  # Regulation
        "项目",  # Project
        "设施",  # Facility
        "服务",  # Service
    ]
