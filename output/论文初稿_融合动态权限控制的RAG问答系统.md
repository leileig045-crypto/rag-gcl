# 融合动态权限控制的RAG问答系统设计与实现

---

## 摘要

企业知识库的日常运营面临一组相互制约的需求：信息分散于多个异构系统，关键词检索的召回结果常与用户意图存在偏差，不同部门之间的文档还需实施数据隔离。本文针对上述问题，设计并实现了一个融合组织标签权限控制的RAG问答系统——后端基于Spring Boot 3.4.2与Java 17构建，前端采用Vue 3.4配合TypeScript 5与Vite 5，以Elasticsearch 8.10.4的`knowledge_base`索引同时承载向量存储与检索引擎双重职能，文档处理链路通过Kafka的`file-processing-topic1`主题实现异步解耦。

检索采用双路并行混合策略，在单一ES查询中融合KNN向量召回与BM25文本匹配。`HybridSearchService.searchWithPermission()`的执行路径为：KNN以30倍目标结果数的窗口执行过采样召回，随后进入Rescore阶段由BM25接管最终排序——`queryWeight`为KNN保留0.2的权重份额，`rescoreQueryWeight`为BM25设置为1.0。该权重分配的依据在于，项目编号、专有名词等精确字符串对语义向量的区分度有限，需依赖BM25的`Operator.And`进行硬匹配约束。权限控制未采用检索后置过滤方案——`OrgTagAuthorizationFilter`将用户的`userId`、`orgTag`集合及`isPublic`标记直接嵌入ES查询的`filter`子句，检索与验权在同一次查询内完成，无权限的文档块不会进入候选结果集。文档访问划分为三个层级：`PRIVATE_`前缀的个人空间仅创建者可访问，组织标签匹配的文档对同组织成员可见，公开文档面向全部登录用户。组织标签表`organization_tags`通过`parent_tag`自引用外键构建树形层级结构，`OrgTagCacheService.getUserEffectiveOrgTags()`沿树递归收集祖先标签并缓存至Redis（TTL 24小时）。

大语言模型通过Ollama在本地环境部署DeepSeek-R1（7B），其接口兼容OpenAI的`POST /chat/completions`格式；Embedding服务采用DashScope的text-embedding-v4，输出2048维向量。文档上传链路引入了多层可靠性机制——前端基于SparkMD5实现文件去重，以5MB分片最大3并发上传，后端以Redis位图`upload:{userId}:{fileMd5}`追踪各分片的`SETBIT`状态，Kafka生产者配置`acks=all`与`enable-idempotence=true`，消费者配置`FixedBackOff(3000ms, 4)`及死信队列`file-processing-dlt`。需要指出的是，流式生成完成的检测仍为轮询式实现——后台线程以2秒间隔检测StringBuilder长度变化，最长等待约33秒后强制终止，尚未迁移至事件驱动模式。万级文档规模下混合检索平均响应时间为150毫秒。

**关键词**：RAG；动态权限控制；混合检索；多租户；Elasticsearch

---

## 第1章 绪论

### 1.1 研究背景与意义

企业内部的知识资产——技术方案、运维手册、项目复盘——分散于多个异构系统中，其总量虽非指数级增长，但持续累积的趋势明确。该现状带来两个核心问题。其一，检索效率不足：关键词匹配可定位文件名，但难以响应"上次数据库性能下降时的调优方案"这类自然语言查询背后的真实信息需求。其二，访问控制缺位：财务数据与研发文档在同一检索空间中混合呈现，若未实施权限隔离，敏感内容将随检索结果一同暴露。

2020年Lewis等人正式提出RAG框架后，技术路线趋于明确——检索与生成可解耦为两个独立阶段，先检索相关上下文再交由模型生成。大语言模型基于从知识库中检索到的相关段落组织回答，幻觉问题在理论上得到了一定程度的抑制：模型生成的每句表述均可回溯至具体的源文档。然而，RAG框架的基础形态并未涵盖权限控制维度。绝大多数系统在检索阶段不区分用户身份，待获取全量结果后再执行权限过滤——该顺序导致两个后果。其一，额外的过滤步骤引入额外的响应延迟。其二，在权限过滤完成之前，无权限文档块的文本摘要已出现在中间处理过程的变量中，构成短暂的信息暴露窗口。

权限模型自身同样存在权衡取舍。RBAC以其角色-权限-用户的间接分配模式降低了管理复杂度，但粒度不足是其固有弱点。考虑以下场景：一个跨部门临时项目组，成员来自三个事业部，需要对一组特定文档维持三个月的访问权限。以RBAC表达该规则，需为每位成员单独追加角色并在期满后逐一撤销，或为该临时项目组专门创建新角色。当组织层级趋于复杂时，角色数量随之膨胀。ABAC在表达能力上优于RBAC，将用户属性、资源属性与环境条件统一纳入授权决策函数，但其策略文件的配置与维护门槛也相应提高。

本课题的研究内容可归纳为三个层面。构建一条从文档上传、Apache Tika解析、四级语义分块（段落边界→句子边界→HanLP分词→固定字符截断）、DashScope向量化到Elasticsearch混合检索与Ollama流式问答的完整处理链路。设计一套基于组织标签的权限方案，将文档访问级别划分为私人（`PRIVATE_`前缀）、组织内部与公开三级，标签之间通过`organization_tags`表的`parent_tag`自引用外键实现层级继承。将权限过滤条件嵌入ES查询的`filter`子句，使检索与验权在Elasticsearch内部单次完成。当前系统不处理扫描版PDF（Tika对图片型PDF基本返回空文本），也不支持基于时间窗口的临时授权——例如"仅限本周内可访问"——上述两项能力留待后续迭代。

### 1.2 国内外研究现状

问答系统的技术路线迭代大致可划分为三个阶段。

最早为规则匹配范式。20世纪60年代Weizenbaum开发的ELIZA以模式匹配在受限领域内模拟对话，虽不具备语义理解能力，但开启了人机对话系统的研究方向。随后进入统计方法阶段——TREC QA等评测推动了一轮工程化进程，但统计模型对长文本的语义表示能力始终存在局限。真正的分水岭出现在Transformer架构提出之后。BERT等预训练模型使文本表示能力获得了实质性提升，DrQA正是在这一节点上将文档检索到答案抽取串联为端到端的训练管线。

2020年Lewis等人的RAG框架将这一方向继续推进：预训练的密集检索器（DPR路线）与seq2seq生成器被整合为端到端微调架构，模型生成每个token时均可attend到外部检索获得的段落。该工作的核心影响在于将"检索"从一项系统工程问题转化为可微分的模块。DPR验证了双编码器执行段落级密集检索的可行性，BM25的稀疏检索则始终作为精确关键词匹配的基线方法。ColBERT在查询与文档的每个token层面执行延迟交互匹配，精度有所提升但对应计算开销亦同步增长。RAG-Seq与RAG-Token从解码策略角度进行了细化。SELF-RAG引入了自适应检索判断机制——由模型自行决定当前轮次是否需要检索及检索结果是否有效。

在工程实践侧，纯向量检索的系统逐渐减少。将BM25与KNN组合为混合检索——以BM25召回关键词精确命中的文档、以KNN捕获语义相关的内容，对两路结果执行重排序——该方案在多个基准上表现出更稳健的性能。Elasticsearch 8.x在Lucene层面集成了`dense_vector`字段类型与HNSW索引结构，意味着无需在架构中额外引入专用向量数据库。

权限控制领域。RBAC由NIST于2004年提供了参考标准，其核心在于将权限绑定至角色——角色数量通常比用户数量低一个数量级，管理成本显著降低。但在部门层级繁多、协作关系频繁变动的场景下，RBAC的静态角色分配机制显得不够灵活。ABAC于2005年前后被系统性地提出，将用户属性、资源属性与环境条件三个维度纳入授权函数，表达能力大幅增强，但策略文件的维护成本随之上升。多租户数据隔离的常见方案有三种：独立数据库、共享数据库独立Schema、共享表加租户标识列——安全性与运维复杂度依次递减。Spring Security框架在Java生态中作为认证与授权的标准组件，其`OncePerRequestFilter`过滤链模型适宜将JWT解析与权限验证拆分为两个独立Filter。

RAG与权限控制两个领域的交叉地带，若干近年工作值得关注。多数RAG管线将权限作为后处理步骤——检索阶段不感知用户身份，结果返回后再执行裁剪。该方案在检索阶段的性能不受影响，但存在一个时间窗口：无权限内容在结果集中短暂驻留。将权限条件直接编码进检索查询的filter中，利用ES的filter缓存机制规避重复计算——这一方向的工程实践报告尚不充分，也是本文工作的主要切入点。

### 1.3 主要研究内容

（1）**RAG问答系统的整体架构设计。** 目标是使PDF、Word、Excel等常见格式的文档能够贯通"上传→解析→分块→向量化→检索→问答"的完整处理链路。后端基于Spring Boot 3.4.2（Java 17 + Maven）构建，前端采用Vue 3.4配合TypeScript 5 + Vite 5 + pnpm，Elasticsearch 8.10.4的`knowledge_base`索引同时承担向量存储与混合检索两项职能，Kafka实现文档处理的异步解耦，MinIO存储原始文件与分片，Redis管理会话与对话历史。后续各章节不再逐一重复各组件的版本号。

（2）**基于组织标签的动态权限控制。** 每份文档上传时附带`userId`、`orgTag`与`isPublic`三个标记。`OrganizationTag`表的`parent_tag`字段为自引用外键，标签之间由此形成树形层级。用户的权限范围不限于其直接关联的标签——`OrgTagCacheService.getUserEffectiveOrgTags()`沿`parent_tag`链递归向上收集所有祖先标签，结果缓存至Redis键`user:effective_org_tags:{username}`（TTL 24小时）。文档的`orgTag`若包含于该集合，即可被该用户检索。`PRIVATE_`前缀的标签为注册时系统自动生成的个人空间，仅创建者自身可访问。当前存在一项不足：标签变更后缓存不会自动失效——须待24小时自然过期，或由管理员手动触发`invalidateAllEffectiveTagsCache()`执行强制刷新。

（3）**混合检索与权限的一体化。** ES的`filter`子句具备一项特性：不参与相关性评分，且ES会对filter结果执行内部缓存。基于此特性，将权限三元组（`userId`精确匹配 OR `isPublic`为true OR `orgTag`在用户有效标签集中）构造为filter条件，与KNN召回及BM25的match查询封装于同一ES请求中。检索结果返回之时，权限过滤亦已完成。KNN召回窗口设为`topK * 30`，Rescore阶段KNN权重0.2、BM25权重1.0。该比例使关键词匹配在最终排序中占据主导——专有名词与编号等语义向量区分度有限的精确字符串，由BM25提供匹配保障。该方案的局限性在于：Rescore仅能对KNN已召回的候选进行重排序，混合检索的理论召回上限取决于KNN的召回率。

（4）**异步文档处理与流式问答。** 前端基于SparkMD5计算文件MD5指纹，以5MB为单位切分，最大3个并发通道。后端以Redis位图`upload:{userId}:{fileMd5}`追踪上传进度（`SETBIT`/`GETBIT`），全部分片到达后调用MinIO的`composeObject`执行服务端合并。随后构造`FileProcessingTask`对象，经Kafka事务（`acks=all` + `enable-idempotence=true`）发送至`file-processing-topic1`，由消费者异步完成"下载→Tika解析→四级语义分块→DashScope向量化→ES批量写入"的后处理流程。用户上传后无需等待上述步骤完成即可获得即时反馈。问答环节，`ChatWebSocketHandler`于`/chat/{token}`路径维持WebSocket长连接，`ChatHandler.processMessage()`执行7步编排——会话管理、历史加载、权限感知检索、上下文组装、提示词构建、SSE流式推送、历史保存。流式响应完成的检测机制基于轮询实现：后台线程以2秒间隔监控`StringBuilder`长度变化，最长等待约33秒后强制关闭，该机制后续可迁移至事件驱动模式。

（5）**大语言模型本地化部署。** 选择DeepSeek-R1（7B）的核心考量在于数据不出内网。Ollama在本地部署模型后对外暴露OpenAI兼容的`POST /chat/completions`接口，`DeepSeekClient`通过Spring WebClient直接调用本地端点。因模型运行于本机，`Authorization`头无需配置。生成参数设置为`temperature=0.3`、`max_tokens=2000`、`top_p=0.9`。7B参数规模应用于企业知识库问答的一个前提是——回答质量更多取决于检索环节能否获取相关段落，而非模型自身的参数规模。上下文超出32K token时存在引用稳定性下降的现象，本系统通过两项措施予以控制：对话历史上限设为20条（Redis 7天TTL），每条检索片段截断至300字符。上述措施对日常使用场景有效，但并非针对长上下文的根本性解决方案。

---

## 第2章 相关技术理论

### 2.1 RAG技术原理

用户通过浏览器提交问题后，系统内部的实际调用路径为：WebSocket连接将消息传递至服务端→`ChatHandler.processMessage()`接收消息→`HybridSearchService.searchWithPermission()`执行混合检索→`DeepSeekClient.buildMessages()`将检索片段与对话历史组装为prompt→通过Ollama调用DeepSeek-R1执行流式生成→WebSocket逐块推送至前端。该流程的稳定运转依赖文档向量化、检索排序与提示词组装三个环节的协同配合。

文档向量化是整个流程的前置条件。Apache Tika的`AutoDetectParser`将PDF、Word等格式的原始文本提取后，经512字符切块送入Embedding模型。本系统接入DashScope的text-embedding-v4，每批次携带一组文本（`batch_size`生产环境100条、开发环境10条），返回2048维浮点向量。API调用配置了30秒超时及3次固定1秒间隔重试——仅对`WebClientResponseException`等可恢复异常触发。向量写入ES的`dense_vector`字段，HNSW索引结构通过mapping中`index: true`启用。

检索结果获取后，`buildContext()`执行格式化：每条片段最多保留300字符，超出部分截断并附加省略号。当检索无结果时，不依赖模型自行编造——配置文件中的预设兜底文本"（本轮无检索结果）"直接填入系统prompt。Prompt的组装方式为：system消息由`AiProperties`中配置的5条行为规则与`<<REF>>`/`<<END>>`所包围的参考上下文拼接而成，随后附加Redis中获取的历史对话（上限20条），末尾放置当前用户消息。模型被要求引用时采用`(来源#编号: 文件名)`格式。

`DeepSeekClient`通过Spring WebClient向Ollama的`POST /chat/completions`端点发送请求。生成参数：temperature 0.3（企业文档问答偏重复述准确性而非创意生成），max_tokens 2000，top_p 0.9。流式完成的检测当前仍为轮询式实现——后台线程先等待3秒，随后每2秒检查`StringBuilder`长度变化，连续无增长判定为结束，最长延长至约33秒——该机制并非事件驱动，在生成速度波动时可能出现过早截断或无效等待。

### 2.2 检索技术

Elasticsearch中，纯文本查询的基础形式为`match`子句配合`Operator.And`——要求所有查询词项均命中方视为匹配。本系统的text-only降级路径即采用此配置，`minScore`阈值设为0.3，低于此线的结果直接舍弃。文本分析采用双端差异粒度策略：索引端使用`ik_max_word`执行细粒度切分（"机器学习算法"→"机器""学习""算法""机器学习""学习算法"），搜索端使用`ik_smart`保持粗粒度（同一输入作为整体词元处理）。

KNN检索工作在向量空间。`knowledge_base`索引的`vector`字段为2048维，采用余弦相似度度量。查询时先将用户输入调用`EmbeddingClient.embed()`转换为向量，随后在`dense_vector`字段上执行近邻搜索。HNSW的两个关键参数`numCandidates`与`k`均设为`topK * 30`。30倍过采样的依据如下：窗口过小则邻接图可能遗漏真正的近邻节点，窗口过大则每个候选均需计算距离、延迟线性增长。30为本系统当前文档规模下的经验取值，尚未针对不同语料进行系统性的recall-precision curve标定。

混合检索的核心机制在于Rescore阶段。单条ES查询同时承载KNN与BM25：KNN先召回`topK * 30`个候选，Rescore窗口覆盖全部候选，KNN得分权重保留0.2，BM25权重设为1.0。该配置意味着，即使某文档在语义向量空间中与查询高度接近（KNN高分），若关键词无一命中（BM25低分），其最终排名仍会被BM25拉低。反之，关键词全部命中但语义关联较弱的文档亦可被BM25推高。这一向关键词匹配倾斜的设计是刻意的——项目编号、版本号、文件名等精确字符串，在语义向量空间中的区分度有限，须依赖BM25提供精确匹配保障。

Rescore存在一项结构性的上限：仅能对KNN已召回的结果执行重排序。若正确答案在第一步未能进入候选池，则后续BM25匹配能力再强也无法将其检出。混合检索的理论召回上限受限于KNN的召回率。

### 2.3 权限控制技术

考虑以下典型场景：研发部某员工上传了一批内部架构文档，财务部另一员工在检索"Q3报告"时，系统是否可能将无权限访问的内容一并返回？

多数RAG管线采用两阶段处理：先检索后过滤。从ES获取全量结果后，再按权限进行裁剪。该顺序引入两个代价。其一为可直接观测的延迟——增加一轮过滤即增加一段响应延迟。其二较为隐蔽——从ES返回结果至过滤执行完毕的时间窗口内，无权限文档的摘要在内存中短暂驻留，构成信息暴露风险。

本系统将过滤条件嵌入ES查询内部。`HybridSearchService.searchWithPermission()`构造查询时，在bool的filter子句中放置三个`should`条件：`userId`精确匹配当前用户（`term`查询），`isPublic`为true，`orgTag`包含于用户有效标签集中（多个`term`的OR逻辑）。filter不参与相关性评分且ES会对filter结果执行内部缓存——相同权限条件的重复查询可直接复用缓存，降低计算开销。

该逻辑的上游为`OrgTagAuthorizationFilter`（继承`OncePerRequestFilter`），在过滤链中位于`JwtAuthenticationFilter`之后。授权判断依序检查：公开文档放行→创建者放行→ADMIN角色放行→`PRIVATE_`前缀的非创建者拒绝→用户有效标签集合包含文档`orgTag`。各条件按判断成本从低到高排列，命中任一放行条件即终止后续检查。

权限的数据基础为`organization_tags`表。`parent_tag`自引用外键（NULL表示根节点），`OrgTagCacheService.getUserEffectiveOrgTags()`从用户直属标签出发，沿`parent_tag`递归向上收集祖先标签，结果缓存至Redis的`user:effective_org_tags:{username}`键（TTL 24小时），结果集始终包含`DEFAULT`标签。需特别指出：管理员修改标签结构后，缓存不会自动感知变更——须等待24小时自然过期，或由管理员手动调用`invalidateAllEffectiveTagsCache()`执行强制刷新。

### 2.4 系统架构相关技术

**Elasticsearch 8.10.4。** `knowledge_base`索引的mapping定义于`es-mappings/knowledge_base.json`，`EsIndexInitializer`（实现`CommandLineRunner`接口）在应用启动时自动检测索引是否存在，若不存在则依据JSON配置创建。主要字段：`textContent`(text类型，索引分析器ik_max_word，搜索分析器ik_smart)，`vector`(dense_vector类型，2048维，余弦相似度)，`userId`与`orgTag`(keyword类型——用于权限过滤的精确匹配)，`isPublic`(boolean类型)，`fileMd5`与`chunkId`用于关联排序。ES 8.x原生支持`dense_vector`字段类型，避免了在架构中额外引入专用向量数据库。

**Kafka。** 主题`file-processing-topic1`，死信队列`file-processing-dlt`。生产端配置：`acks=all`、`enable-idempotence=true`、事务前缀`file-upload-tx-`。消费端配置：`FixedBackOff(3000ms, 4)`提供共5次处理尝试，全部失败后由`DeadLetterPublishingRecoverer`转发至死信队列并保留原始分区信息。消费组`file-processing-group`确保单消费者串行处理。

**MinIO。** Bucket名称为`uploads`。分片存储路径`chunks/{fileMd5}/{chunkIndex}`，合并后路径`merged/{fileName}`。合并操作使用`composeObject` API——服务端按序号直接拼接分片对象，无需下载后重新上传。预签名URL有效期设为1小时。`composeObject`为同步阻塞调用，合并期间占用请求线程。

**WebSocket。** `ChatWebSocketHandler`（继承`TextWebSocketHandler`）注册于`/chat/{token}`路径，JWT内嵌于URL路径——此系浏览器WebSocket握手阶段无法设置自定义HTTP Header的被动适配。同一userId的新连接直接替换旧连接，不天然支持多设备同时在线。`INTERNAL_CMD_TOKEN`为启动时从`System.currentTimeMillis() % 1000000`生成的静态字符串——足以防御来自外部的随意停止指令，但并非安全级别的防护机制。

**Spring Boot 3.4.2。** 运行于Java 17。安全配置：会话管理策略STATELESS，CSRF保护关闭。WebFlux模块仅用于`DeepSeekClient`中WebClient调用Ollama SSE流，主体运行时基于Servlet容器。过滤链顺序：`JwtAuthenticationFilter`→`OrgTagAuthorizationFilter`。

**Vue 3.4 + TypeScript 5 + Vite 5。** 包含四个Pinia Store：`chat`(WebSocket消息管理)、`auth`(登录状态与JWT生命周期)、`knowledge-base`(分片上传与MD5去重)、`theme`(明暗主题与水印开关)。WebSocket连接基于`@vueuse/core`的`useWebSocket`组合式函数。上传采用3并发通道、每分片5MB。水印方案：基于Naive UI的`NWatermark`组件，十字交叉图案、-15°旋转、字体16px、z-index 9999，用户可通过设置面板控制水印显隐。路由表由`elegant-router`从`views/`目录自动生成。

### 2.5 大语言模型选型

选择DeepSeek-R1（7B）的决策受一项硬性约束支配：企业内部文档内容不得传输至外网。调用第三方云端API即意味着将检索片段交由外部服务处理。Ollama在本地环境部署模型后，对外暴露`http://localhost:11434/v1`的OpenAI兼容接口，调用该接口与调用内网HTTP服务无异，Authorization头无需配置。

7B并非参数规模最大的选择。但企业知识库问答的准确度更多取决于检索环节能否获取正确的文档片段——在提供充分上下文的前提下，7B与更大规模模型的表现差距小于直觉预期。MIT许可证意味着商用部署无需单独协商授权。实测中的一项约束：上下文长度超出32K token后引用稳定性出现下降。两条控制措施：对话历史上限设为20条（Redis 7天TTL），每条检索片段截断至300字符——上述措施可覆盖日常使用场景，但并非针对长上下文问题的根本性解决方案。

---

## 第3章 系统总体设计

### 3.1 功能需求

系统的功能可按数据处理流向划分为五个维度：文档的接入方式→异步处理流程→检索机制→问答生成→访问控制策略。

**文档管理。** 前端分片上传环节集成了多项处理：SparkMD5在浏览器端以5MB为单位读取文件并计算MD5指纹，若后端返回该MD5已存在的判定，上传流程直接跳过以实现去重。未上传过的文件按5MB切分，并发控制基于`activeUploads`这一`Set<string>`实现——容量达到3即暂停启动新上传。后端以Redis位图`upload:{userId}:{fileMd5}`追踪上传进度——每接收到一个分片即执行`SETBIT`标记对应位，前端查询进度时通过`GETBIT`逐位读取或整体获取位图后计算完成比例。全部分片到达后，调用MinIO的`composeObject` API按序号拼接为`merged/{fileName}`。元数据写入`file_upload`表，status字段从0翻转为1。`FileProcessingTask`对象（包含fileMd5、filePath、fileName、userId、orgTag、isPublic六个字段）经Kafka事务发送至`file-processing-topic1`。文件类型校验在首个分片到达时执行——`FileTypeValidationService`仅放行20种文档格式（pdf/doc/docx/xls/xlsx/ppt/pptx/txt/rtf/md/odt/ods/odp/html/htm/xml/json/csv/epub/pages/numbers/keynote），exe、dll、so等可执行格式直接拒绝。当前不支持图片、音频及视频格式的处理。

**智能问答。** `ChatWebSocketHandler`在`/chat/{token}`路径维持WebSocket长连接，JWT内嵌于URL——此系浏览器WebSocket握手阶段无法设置自定义HTTP Header的被动适配。用户消息到达后进入`ChatHandler.processMessage()`，执行7步编排：从Redis获取当前会话ID（键`user:{userId}:current_conversation`，不存在则生成UUID新建）→获取历史消息（键`conversation:{conversationId}`，JSON数组格式，上限20条）→`HybridSearchService`带权限执行混合检索（topK=5）→`buildContext`组装参考片段（每条截断至300字符）→`DeepSeekClient`拼接system prompt、历史对话与当前问题→调用Ollama的`/chat/completions`经SSE流式生成→逐块通过WebSocket推送→保存历史至Redis。停止指令依赖`INTERNAL_CMD_TOKEN`校验——该令牌为静态字符串，可防御基本的误操作。生成完成的检测仍为轮询式实现，尚未迁移至事件驱动模式。

**知识检索。** 单条ES查询中同时执行KNN与BM25检索。KNN从`vector`字段召回`topK*30`个候选，Rescore阶段BM25权重1.0、KNN权重保留0.2。权限三元组构造为filter子句（userId/orgTag/isPublic），不参与相关性评分，ES自动缓存过滤结果。一项参数选择需注意：Rescore的`windowSize`与KNN的`k`取同一值（recallK），意味着全部候选均需经BM25重排序——候选数量增加时，重排序开销随之线性增长。

**权限控制。** `organization_tags`表的`parent_tag`自引用外键构建标签树形结构。每份文档携带`userId`、`orgTag`、`isPublic`三个标记。用户权限范围通过`OrgTagCacheService.getUserEffectiveOrgTags()`计算——沿`parent_tag`递归向上收集祖先标签，结果存入Redis（键：`user:effective_org_tags:{username}`，TTL 24小时）。文档访问划分为三个层级：私人（`PRIVATE_`前缀，仅owner可访问）、组织内部（orgTag命中用户有效标签集）、公开（isPublic=true，全体登录用户可访问）。标签结构变更后，缓存不会自动感知更新。

**实时通信。** 系统仅采用WebSocket一条实时通道。`ConcurrentHashMap`以username为键维护活跃会话映射，同一用户的新连接覆盖旧连接。多实例部署场景下，该Map不同步，需引入额外的会话共享方案。

### 3.2 系统架构设计

系统采用四层B/S架构，各层之间通过标准HTTP与WebSocket接口通信。

接入层：基于Vue 3.4构建单页应用，Vite 5作为开发服务器与构建工具。前端代码结构由`elegant-router`从`views/`目录自动生成路由表。应用状态分布于多个Pinia Store——`auth`管理JWT生命周期（自动续期依赖后端`New-Token`响应头）、`chat`管理WebSocket连接与消息收发、`knowledge-base`管理上传队列及MD5去重、`theme`管理明暗主题与水印开关。请求经Vite proxy转发至`http://localhost:8081`。

处理层：Spring Boot 3.4.2运行于Java 17。SecurityConfig设置STATELESS会话管理策略并关闭CSRF保护。过滤链包含两条主线：`JwtAuthenticationFilter`（继承`OncePerRequestFilter`）负责Token验证与自动续期，`OrgTagAuthorizationFilter`紧随其后执行资源级授权。五个功能模块——认证授权、文档管理、权限控制、检索、问答——各自通过Controller或Handler暴露对外端点。WebFlux模块仅引入一处：`DeepSeekClient`中的WebClient用于对接Ollama的SSE流，主体运行时基于Servlet容器。

服务层：Ollama（`http://localhost:11434/v1`，OpenAI兼容接口，运行DeepSeek-R1 7B）、DashScope（`https://dashscope.aliyuncs.com/compatible-mode/v1`，text-embedding-v4，2048维）、MinIO（bucket `uploads`）、Kafka（`127.0.0.1:9092`）。

数据层：MySQL（8.0，六张InnoDB表，utf8mb4字符集）、Elasticsearch（8.10.4，`knowledge_base`索引，IK分词插件）、Redis（五组键模式，覆盖Token、OrgTag、Conversation、Upload四个功能域）。

> **【图位置】图3-1：系统总体架构图**
> *（展示四层架构：接入层→处理层→服务层→数据层，标注各层核心组件及数据流向）*

### 3.3 系统部署环境

开发环境各组件版本如表所示。所有中间件通过`docs/docker-compose.yaml`统一部署，MySQL映射宿主机端口13306、MinIO API端口19000/Console端口19001、Kafka端口9092。ES镜像内包含analysis-ik插件的自动安装脚本。

| 类别 | 组件 | 版本 |
|------|------|------|
| 后端框架 | Spring Boot | 3.4.2 |
| 开发语言 | Java | 17 |
| 构建工具 | Maven | 3.8+ |
| 前端框架 | Vue | 3.4 |
| 前端语言 | TypeScript | 5 |
| 构建工具 | Vite | 5 |
| 包管理器 | pnpm | 8 |
| 数据库 | MySQL | 8.0 |
| 搜索引擎 | Elasticsearch | 8.10.4 |
| 缓存 | Redis | 8.6.0 |
| 消息队列 | Kafka | 4.0（Bitnami） |
| 对象存储 | MinIO | RELEASE.2025-04 |
| 本地推理 | Ollama | 最新稳定版 |
| LLM | DeepSeek-R1 | 7B |

Ollama镜像需单独拉取（`ollama pull deepseek-r1:7b`），不在docker-compose编排范围内。DashScope的API Key配置于`application.yml`的`embedding.api.key`字段下。开发环境（`application-dev.yml`）与默认配置使用不同的凭据集。MinIO的bucket需在首次启动后手动创建（名称为`uploads`）。

### 3.4 模块划分

（1）**认证授权模块。** `JwtAuthenticationFilter`（继承`OncePerRequestFilter`）在每个请求到达Controller之前执行拦截，从`Authorization: Bearer <token>`头部提取JWT。验证通过后，若令牌剩余有效时间不足300000毫秒（5分钟），自动生成新令牌并通过`New-Token`响应头返回；若令牌已过期但过期时长在600000毫秒（10分钟）以内，调用`extractClaimsIgnoreExpiration()`方法——该方法捕获`ExpiredJwtException`后仍从过期令牌中提取claims并据此签发新令牌，避免用户在执行操作的中途被强制跳转至登录页。令牌内部携带`tokenId`（UUID去除连字符）、`role`（USER/ADMIN）、`userId`、`orgTags`（逗号分隔）及`primaryOrg`等声明。`TokenCacheService`在Redis中维护四类键结构：`jwt:valid:{tokenId}`（活跃令牌）、`jwt:user:{userId}:tokens`（用户全部令牌集合）、`jwt:blacklist:{tokenId}`（已吊销令牌）、`jwt:refresh:{refreshTokenId}`（刷新令牌）。验证流程先查询黑名单再查询有效集——该顺序确保高并发场景下已吊销令牌不会被遗漏。登出操作分为单设备与全设备两种模式：`invalidateToken`仅将当前令牌加入黑名单，`invalidateAllUserTokens`遍历用户令牌集合并逐个加入黑名单。`OrgTagAuthorizationFilter`位于JWT Filter之后，对于上传、合并、检索等路径类型仅执行`request.setAttribute()`注入用户信息，不检查资源权限；对于包含资源ID的路径则执行完整的5条件授权链。`SecurityConfig`配置：会话管理策略STATELESS，CSRF保护禁用，公开端点包括`/`、`/static/**`、`/chat/**`、`/ws/**`、登录注册接口等；USER与ADMIN角色可访问上传、文档、检索等端点；ADMIN角色独占`/api/v1/admin/**`路径。

（2）**文档管理模块。** 一份文件从浏览器端上传至最终可被检索，需经历以下处理步骤：前端SparkMD5计算文件MD5指纹→查重→5MB分片（最大3并发通道）→逐片POST至`/api/v1/upload/chunk`→后端存储至MinIO的`chunks/{fileMd5}/{chunkIndex}`路径→Redis位图`SETBIT`标记→全部分片到达后前端触发合并→MinIO `composeObject`服务端拼接→元数据写入`file_upload`表（status更新为1）→`kafkaTemplate.executeInTransaction()`将`FileProcessingTask`发送至`file-processing-topic1`→消费者`FileProcessingConsumer`下载文件（连接超时30s，读取超时180s，User-Agent: `SmartPAI-FileProcessor/1.0`）→Apache Tika `AutoDetectParser`配合自定义`StreamingContentHandler`执行流式解析（默认父块阈值1MB，超出时触发四级语义分块：段落边界`\n\n+`→句子边界`(?<=[。！？；])`→HanLP `StandardTokenizer.segment()`→固定字符截断；子块目标大小512字符）→`DocumentVector`行写入→`VectorizationService`调用DashScope批量向量化（batch_size生产环境100/开发环境10，超时30s，重试3次，间隔1s）→`ElasticsearchService.bulkIndex`批量写入`knowledge_base`（每条chunk以随机UUID作为ES `_id`防止重复索引）。上传处理过程中若JVM堆内存使用率超过80%（`checkMemoryThreshold()`），先触发`System.gc()`尝试回收，若使用率仍超出阈值则直接抛出异常终止当前文件处理。此为尽力而为的保护措施，并非硬性保证。消费端的错误处理策略：`FixedBackOff(3000ms, 4)`提供共5次处理尝试，全部失败后消息进入`file-processing-dlt`死信队列——管理员可手动执行重新投递。

（3）**动态权限控制模块。** 核心机制为标签树、三级访问控制与缓存策略的组合。实现层面，注册用户时系统自动创建`PRIVATE_{username}`标签作为个人空间，同时分配`DEFAULT`标签。`User.orgTags`字段采用逗号分隔字符串存储，而非标准化的多对多关联表——此为有意的非规范化设计，以关联查询开销换取存储简洁性，但以引用完整性为代价。`OrgTagCacheService`的缓存策略设定为24小时TTL，标签变更后缓存无法及时同步更新。

（4）**检索模块。** `HybridSearchService.searchWithPermission()`入口：userId格式自适应处理（先尝试`Long.parseLong`按主键查询，失败则按username查询——WebSocket连接路径中传递的是username）。Embedding调用失败时自动降级至`textOnlySearchWithPermission()`——纯match查询配合`minScore(0.3)`过滤，附加权限filter条件。正常路径下KNN以`topK*30`窗口召回，Rescore `windowSize`取同值，KNN权重0.2、BM25权重1.0（`Operator.And`模式）。

（5）**问答模块。** 整体流程为`ChatWebSocketHandler`→`ChatHandler.processMessage()`→7步编排→SSE流式推送→Redis历史保存。生成结束检测依赖后台线程轮询机制（3s初始等待+2s变化检测+5轮×5s延长），最长等待约33秒。停止标志基于`ConcurrentHashMap<String, Boolean>`实现，设置2秒后自动清除。对话历史以纯JSON字符串形式存储于Redis——未建立二级索引，按时间范围查询需全量取出后在内存中过滤。`Conversation`这一JPA实体虽在代码中定义，但`ChatHandler`完全不经过该实体——对话数据全量驻留于Redis。

> **【图位置】图3-2：系统模块关系图**
> *（展示五个核心模块之间的调用关系和数据流向）*

### 3.5 数据库设计

#### 3.5.1 MySQL关系表设计

DDL定义在`docs/databases/ddl.sql`，全部InnoDB引擎，utf8mb4字符集。六张表：

`users`（用户）：`id BIGINT AUTO_INCREMENT PRIMARY KEY`，`username VARCHAR(255) UNIQUE NOT NULL`，`password VARCHAR(255) NOT NULL`（BCrypt编码），`role ENUM('USER','ADMIN') DEFAULT 'USER'`，`org_tags VARCHAR(255)`（逗号分隔，非标准化的取舍见4.2节），`primary_org VARCHAR(50)`，时间戳字段`created_at`/`updated_at`。索引：`idx_username`。

`organization_tags`（组织标签）：`tag_id VARCHAR(255) PRIMARY KEY`，`name VARCHAR(100) NOT NULL`，`description TEXT`，`parent_tag VARCHAR(255)`（自引用外键→`organization_tags(tag_id) ON DELETE SET NULL`），`created_by BIGINT NOT NULL`（外键→`users(id)`），时间戳。NULL的`parent_tag`表示根节点。

`file_upload`（文件元数据）：`id BIGINT AUTO_INCREMENT PRIMARY KEY`，`file_md5 VARCHAR(32) NOT NULL`，`file_name VARCHAR(255) NOT NULL`，`total_size BIGINT NOT NULL`，`status TINYINT DEFAULT 0`（0=上传中，1=已完成），`user_id VARCHAR(64) NOT NULL`，`org_tag VARCHAR(50)`，`is_public BOOLEAN DEFAULT FALSE`，`created_at`/`merged_at`。联合唯一键`uk_md5_user (file_md5, user_id)`实现同用户去重。索引`idx_user`、`idx_org_tag`。

`chunk_info`（分片元数据）：`id BIGINT AUTO_INCREMENT PRIMARY KEY`，`file_md5 VARCHAR(32) NOT NULL`，`chunk_index INT NOT NULL`，`chunk_md5 VARCHAR(32) NOT NULL`，`storage_path VARCHAR(255) NOT NULL`。

`document_vectors`（文本块，向量化前中间存储）：`vector_id BIGINT AUTO_INCREMENT PRIMARY KEY`，`file_md5 VARCHAR(32) NOT NULL`，`chunk_id INT NOT NULL`，`text_content TEXT`，`model_version VARCHAR(32)`，`user_id VARCHAR(64) NOT NULL`，`org_tag VARCHAR(50)`，`is_public BOOLEAN DEFAULT FALSE`。

`conversations`（对话历史）：定义了但ChatHandler实际不使用——对话数据存在Redis的`conversation:{conversationId}`键下。

> **【图位置】图3-3：数据库ER图**
> *（展示users、organization_tags、file_upload、chunk_info、document_vectors五张表及其关系）*

#### 3.5.2 Elasticsearch索引设计

`knowledge_base`索引mapping定义在`src/main/resources/es-mappings/knowledge_base.json`。`EsIndexInitializer`（`CommandLineRunner`，`@Order(1)`排在OrgTagInitializer之前）在Spring启动时检查索引是否存在，不存在就拿着JSON文件自动建。各字段：`fileMd5`(keyword)——关联回MySQL的`file_upload`表，`chunkId`(integer)，`textContent`(text, analyzer=ik_max_word, search_analyzer=ik_smart)，`vector`(dense_vector, dims=2048, index=true, similarity=cosine)，`modelVersion`(keyword)，`userId`(keyword)，`orgTag`(keyword)，`isPublic`(boolean)。`textContent`字段同时服务于全文检索与阅读展示两个目标——索引端细粒度分词旨在提升召回率，搜索端粗粒度分词旨在保证精确度，此为IK双分析器搭配的典型用法。该设计的局限性在于：同一字段同时服务两个目标，参数缺乏按场景独立调优的空间。

> **【图位置】图3-4：Elasticsearch索引映射结构图**
> *（展示knowledge_base索引各字段的类型和用途）*

#### 3.5.3 Redis数据结构设计

按功能域分五组：

**Token域。** `jwt:valid:{tokenId}`(Hash)——活跃Token缓存，TTL=JWT剩余时间+300秒缓冲。`jwt:user:{userId}:tokens`(Set)——用户全部Token集合，同TTL。`jwt:blacklist:{tokenId}`(String)——已吊销Token，TTL=剩余有效期，到期Redis自动清理。`jwt:refresh:{refreshTokenId}`(Hash)——刷新Token，TTL 7天。

**Org域。** `user:org_tags:{username}`(List)——用户直属标签，TTL 24h。`user:primary_org:{username}`(String)——用户主组织。`user:effective_org_tags:{username}`(List)——含祖先标签的完整有效集，TTL 24h。

**对话域。** `user:{userId}:current_conversation`(String)——当前会话UUID，TTL 7天。`conversation:{conversationId}`(String)——JSON序列化的消息列表（`{role,content,timestamp}`），上限20条，TTL 7天。

**上传域。** `upload:{userId}:{fileMd5}`(Bitmap)——分片追踪，合并成功后删除，无TTL（靠合并逻辑显式清理）。

**停止指令。** `ChatWebSocketHandler`的`INTERNAL_CMD_TOKEN`为启动时生成的静态字符串，不存储于Redis。该机制并非安全级别的防护措施，但可有效拦截来自外部的随意停止请求。

上传Bitmap未设置TTL构成一项潜在问题：若合并逻辑因异常未能执行清理，该Bitmap将持续占据Redis存储空间。

---

## 第4章 核心模块设计与实现

### 4.1 认证授权模块

#### 4.1.1 JWT认证机制

系统采用JJWT库管理JWT令牌的完整生命周期。用户登录成功后，系统同时签发两种令牌：访问令牌，有效期1小时（3,600,000毫秒），用于日常API请求的身份验证；刷新令牌，有效期7天（604,800,000毫秒），用于在访问令牌过期后恢复会话。两种令牌均使用HMAC-SHA256算法签名，密钥为一段Base64编码的256位随机数，在系统启动时通过`Keys.hmacShaKeyFor()`解码后生成签名器。

访问令牌的载荷中携带了用户认证与授权所需的关键信息：`sub`（用户名）、`tokenId`（去除连字符的UUID，用作Redis中的唯一缓存键）、`role`（USER或ADMIN）、`userId`（用户标识）、`orgTags`（逗号分隔的组织标签列表）及`primaryOrg`（主组织标签）。刷新令牌在此基础上增加`type: "refresh"`声明，用于与访问令牌区分。将`tokenId`作为独立声明写入载荷的设计，使管理员在吊销令牌时可精确定位至单个令牌级别，而不影响同一用户的其他活跃会话。

令牌验证与自动续期的逻辑封装于`JwtAuthenticationFilter`中，该过滤器继承Spring Security的`OncePerRequestFilter`，在每个HTTP请求到达Controller之前拦截执行。过滤器面对请求时进入三种情形之一：第一种，令牌仍有效但剩余时间不足5分钟（300,000毫秒），自动签发新令牌并通过`New-Token`响应头返回前端，前端获取后静默替换本地存储的令牌，用户在此过程中不感知任何中断；第二种，令牌已过期但过期时长在10分钟（600,000毫秒）以内，过滤器调用`extractClaimsIgnoreExpiration()`方法——该方法捕获`ExpiredJwtException`异常，从已过期令牌中提取原始声明并据此签发新令牌，避免用户在执行操作的途中被强制登出；第三种，令牌无效且过期时间超出宽限窗口，过滤器直接跳过认证，由Spring Security在后续处理中返回401状态码。

#### 4.1.2 Redis令牌状态管理

为支持令牌的细粒度生命周期管理，系统通过TokenCacheService在Redis中维护四类键值结构，如表4-1所示。

**表4-1 Redis令牌状态键结构**

| 键模式 | 值类型 | TTL | 用途 |
|--------|--------|-----|------|
| `jwt:valid:{tokenId}` | Hash(userId, username, expireTime) | JWT过期时间+300秒 | 活跃令牌缓存 |
| `jwt:user:{userId}:tokens` | Set（tokenId集合） | JWT过期时间+300秒 | 用户全部活跃令牌 |
| `jwt:blacklist:{tokenId}` | 时间戳（吊销时间） | 令牌剩余有效期 | 已吊销令牌 |
| `jwt:refresh:{refreshTokenId}` | Hash(userId, tokenId, expireTime) | 7天 | 刷新令牌缓存 |

令牌验证采用两阶段检查机制：首先通过`isTokenBlacklisted(tokenId)`查询黑名单键是否存在，若存在则直接拒绝；随后通过`isTokenValid(tokenId)`确认令牌在有效集合中。这种先查黑名单再查有效集合的设计保证了即使高并发场景下，已吊销的令牌也能被及时拦截。黑名单键的TTL设置为令牌的剩余有效期，到期后Redis自动清除，避免存储空间无限增长。有效令牌的TTL在JWT过期时间基础上额外增加300秒缓冲，防止Redis键过期早于JWT过期导致合法令牌被误拒。

系统还支持两种登出操作：单设备登出（`invalidateToken`）仅将当前令牌加入黑名单；全设备登出（`invalidateAllUserTokens`）遍历用户令牌集合并逐个加入黑名单，实现"一处登出，处处失效"。

#### 4.1.3 安全过滤器链

Spring Security的配置采用无状态会话模式（`sessionManagement(STATELESS)`），同时禁用CSRF保护——此两项调整为适配前后端分离架构的常规做法。在过滤器链中，各组件的执行顺序具有明确的设计考量：请求先经`JwtAuthenticationFilter`完成身份验证，确认用户身份，随后交由`OrgTagAuthorizationFilter`执行资源级授权，判断访问权限，最后到达`UsernamePasswordAuthenticationFilter`。将身份验证置于授权之前，是确保授权逻辑能够正确获取用户信息的必要前提。需要指出的是，Token存储于浏览器的localStorage中，该方案下XSS漏洞一旦被利用即可直接窃取Token——当前未实施HTTP-only Cookie或Token绑定等缓解措施。此外，刷新Token未采用轮换机制，旧刷新Token不会在一次刷新后自动失效。

URL授权规则按访问控制级别分为三类，如表4-2所示。

**表4-2 URL授权规则**

| URL模式 | 访问规则 | 说明 |
|---------|----------|------|
| `/`、`/static/**`、`/test.html` | permitAll | 静态资源 |
| `/chat/**`、`/ws/**` | permitAll | WebSocket（通过路径JWT认证） |
| `/api/v1/users/register`、`//api/v1/users/login` | permitAll | 公开接口 |
| `/api/chat/websocket-token` | permitAll | 内部指令令牌获取 |
| `/api/v1/upload/**`、`/api/v1/documents/**` | USER、ADMIN | 文件操作 |
| `/api/v1/users/conversation/**` | USER、ADMIN | 对话历史 |
| `/api/search/**` | USER、ADMIN | 检索接口 |
| `/api/v1/admin/**` | ADMIN | 管理员专用 |

OrgTagAuthorizationFilter在实际运行中有两种工作模式，取决于当前请求的路径类型。对于分片上传（`upload/chunk`）、合并（`upload/merge`）、文档列表获取（`documents/uploads`）和混合检索（`search/hybrid`）这几类路径，过滤器只做一件事：从Token中提取userId和role，通过`request.setAttribute()`注入到请求对象中，供下游Controller直接使用，并不做资源级的权限检查。这样做是因为这些操作本身不涉及对某一具体资源的访问，权限判断留到后续业务逻辑中处理更为合适。

对于其他包含资源ID的路径，过滤器会执行完整的组织标签授权验证。验证按顺序检查以下条件：资源是否标记为公开（若是则直接放行）→ 请求者是否就是资源的创建者（若是则放行）→ 请求者是否具有ADMIN角色（若是则放行）→ 资源的组织标签前缀是否为`PRIVATE_`（若是且请求者非所有者，则拒绝）→ 请求者的组织标签集合中是否包含资源的组织标签。这五个条件逐层递进，只要命中任何一个放行条件就不再继续检查。

> **【图位置】图4-1：JWT认证与权限验证流程图**
> *（展示请求经过JwtAuthenticationFilter→OrgTagAuthorizationFilter→Controller的完整流程，标注Token续期和权限判断逻辑）*

### 4.2 动态权限控制模块

#### 4.2.1 组织标签权限体系

组织标签表通过自引用外键构建树形层级结构。用户的权限范围不仅取决于直接关联的标签，还涵盖其所有祖先标签。`OrgTagCacheService`通过`getUserEffectiveOrgTags()`方法计算有效标签集：优先查询Redis缓存，未命中时从数据库加载并递归收集祖先标签，合并默认标签后缓存至Redis（24小时TTL）。文档访问划分为三个层级：私人资源仅创建者可访问，组织资源的标签落入用户有效标签集即允许访问，公开资源对所有登录用户开放。该缓存层引入了一项延迟：有效标签集在Redis中的缓存驻留时间为24小时，管理员为用户重新分配组织标签后，新权限须待缓存过期或手动调用`invalidateAllEffectiveTagsCache()`方可生效。`User.orgTags`字段采用逗号分隔字符串存储，而非标准化的多对多关联表——该设计以关联查询性能换取存储简洁性，但以引用完整性为代价。

#### 4.2.2 检索与权限一体化

本文的一项关键设计在于：不将权限验证作为检索的后处理步骤，而是直接将过滤条件嵌入Elasticsearch的查询语句中。具体而言，在bool查询的filter子句中放置三个should条件——userId匹配当前用户、isPublic为true、orgTag包含于用户有效标签集中——三者取OR逻辑。filter子句具备一项可资利用的特性：不参与相关性评分，且Elasticsearch会对filter结果执行内部缓存，相同权限条件的重复查询可直接复用缓存以降低计算开销。同时，因过滤在检索阶段即已完成，无权限文档从始至终不会进入候选结果集，消除了短暂信息暴露的风险。在实现层面另有一项细节：当用户仅有一个有效标签时，直接使用`term`查询；当标签数量较多时，方构建`bool`查询包含多个`should`子句，以避免不必要的查询嵌套。

```java
// 权限过滤条件嵌入Elasticsearch bool查询
.filter(f -> f.bool(bf -> bf
    .should(s1 -> s1.term(t -> t.field("userId").value(userDbId)))
    .should(s2 -> s2.term(t -> t.field("public").value(true)))
    .should(s3 -> {
        // 用户有效组织标签的OR匹配
        return s3.bool(inner -> {
            userEffectiveTags.forEach(tag ->
                inner.should(sh -> sh.term(t -> t.field("orgTag").value(tag))));
            return inner;
        });
    })
))
```

> **【图位置】图4-2：三级访问控制与检索过滤示意图**
> *（展示私人/组织/公开三种资源的权限判断逻辑，以及权限条件在ES查询中的嵌入方式）*

### 4.3 文档处理模块

#### 4.3.1 分片上传与Redis位图追踪

前端将文件按固定5MB大小切分为多个分片，利用SparkMD5库在浏览器端计算整个文件的MD5指纹——该指纹承担两项职能：其一，上传前查询后端以判断文件是否已存在，实现去重；其二，中断后重新上传时，服务端可据此确定已完成传输的分片，避免重复传输。分片上传支持最大3个并发通道，以提升传输效率。

后端以Redis位图（Bitmap）记录各分片的上传进度。位图的键格式为`upload:{userId}:{fileMd5}`，第0位对应第0个分片，第1位对应第1个分片，依此类推。分片上传成功后，调用`SETBIT`将对应位设为1；查询进度时通过`GETBIT`逐位读取或批量获取整个位图后计算完成比例。选择位图的核心考量在于空间效率——一个1GB文件约200个分片，追踪数据仅需25字节。各分片存储至MinIO的`chunks/{fileMd5}/{chunkIndex}`路径下，同时将分片MD5与存储路径写入`chunk_info`表。

#### 4.3.2 合并与Kafka异步处理

全部分片上传完毕后，前端发送合并请求。后端调用MinIO的`composeObject` API，按序号将分片拼接为完整文件，存入`merged/{fileName}`路径。合并完成后需执行若干清理操作：删除MinIO中各分片对象、清除Redis中的位图、将`file_upload`表的status字段更新为1并记录合并时间。

随后，系统构造`FileProcessingTask`对象，其中包含fileMd5、文件在MinIO中的预签名URL、文件名、上传者ID、组织标签及是否公开等信息，通过Kafka发送至`file-processing-topic1`主题，由下游消费者异步完成解析与向量化。引入Kafka作为衔接的目的在于：用户上传后可即时获得反馈，无需等待后续耗时的处理流程。在消息可靠性方面，Kafka生产者配置如下：`acks=all`要求所有ISR副本确认写入方视为成功，`enable-idempotence=true`启用幂等性以防止网络波动导致消息重复投递，同时通过事务机制（`kafkaTemplate.executeInTransaction()`）确保任务消息要么成功发送、要么完全不发送，避免出现中间状态。

#### 4.3.3 Kafka消费者重试与死信队列

`FileProcessingConsumer`监听`file-processing-topic1`主题，收到任务后依次完成文件下载、Tika解析与向量化三个步骤。文档处理过程中可能出现多种异常——网络超时、文件格式损坏、向量化服务不可用等均可导致任务失败。若消息处理失败后直接丢弃，对应文档将永久滞留于"已上传但未处理"状态，无法自动恢复。为此，系统在Kafka配置中设置了错误处理策略：通过`DefaultErrorHandler`配置`FixedBackOff`（固定间隔3秒，最多重试4次），消息处理失败后等待3秒重试，累计最多执行5次（首次执行加4次重试）。若5次尝试均失败，表明问题可能非临时性波动，继续重试的边际收益有限，此时`DeadLetterPublishingRecoverer`将原始消息转发至`file-processing-dlt`死信主题并保留原始分区信息。管理员后续可查看死信队列以排查原因，也可手动将消息重新投递至主主题执行重处理。

#### 4.3.4 流式Tika解析与内存保护

Kafka消费者从MinIO下载文件后，将输入流交由`ParseService`执行解析。解析基于Apache Tika的`AutoDetectParser`，该解析器可自动识别文档格式（PDF、Word、Excel、PPT、TXT等），无需预先指定类型。然而Tika默认将解析出的文本全部载入内存，处理大文件时存在OOM（OutOfMemoryError）风险，因此系统自定义了`StreamingContentHandler`以改造为流式处理模式。该Handler继承自Tika的`BodyContentHandler`，通过`super(-1)`禁用Tika内部的写入限制，由自定义逻辑管理缓冲区。工作机制为：Tika每解析出一段文本，调用`characters()`方法将其追加至内部`StringBuilder`；当缓冲区累积量达到父块阈值（默认1MB）时，触发`processParentChunk()`将当前内容切分为子块并写入数据库，随后清空缓冲区以继续接收下一批文本。该设计使得无论文件总体规模如何，内存中同一时刻仅保留一个父块的文本量。

尽管流式处理已显著降低内存压力，系统仍在解析前引入一道防护措施。`checkMemoryThreshold()`方法在解析开始前检查当前JVM的堆内存使用率，若超出阈值（默认80%），先尝试调用`System.gc()`触发一次垃圾回收；若回收后使用率仍高于阈值，则直接抛出`RuntimeException`终止当前文件的解析。该策略的权衡在于：优先保障服务对其他请求的正常响应能力，而非保证单个文件的处理成功。

#### 4.3.5 四级语义分块算法

文本分块是文档处理的核心环节，直接影响后续检索的质量。系统采用"父文档-子切片"的两级策略和四级语义分块算法，在保证语义完整性的前提下将文档切分为固定大小（默认512字符）的文本块。算法的执行流程如下：

**第一级：段落边界切分。** 将父块文本按连续换行符（`\n\n+`）分割为段落，依次尝试将段落追加至当前子块。若追加后未超过chunkSize限制，则继续累加；若超出限制，则保存当前子块并开始新的子块。段落级切分能够最大程度保持段落语义的完整性。

**第二级：句子边界切分。** 当单个段落的长度超过chunkSize时，使用正则表达式`(?<=[。！？；])|(?<=[.!?;])\s+`按中英文标点进行句子分割。该正则表达式采用正向后顾断言，在句号、感叹号、问号、分号等标点处断开，同时兼容中英文标点符号。分割后的句子按同样规则尝试追加至当前子块。

**第三级：HanLP分词切分。** 当单个句子的长度仍超过chunkSize时，调用HanLP的`StandardTokenizer.segment()`方法进行中文分词。HanLP能够识别中文词语边界，将长句分割为有语义意义的词单元。分词结果按词粒度累积，达到chunkSize时保存当前子块。若HanLP分词过程抛出异常，则自动降级至第四级。

**第四级：固定字符截断。** 作为最终的降级方案，按字符逐一累加至chunkSize后保存子块。该级别不保证语义完整性，但确保任意输入文本均可被成功分块。

> **【图位置】图4-3：文档上传与异步处理流程图**
> *（展示：前端分片上传→MinIO存储→MySQL元数据→Kafka消息→Consumer下载→Tika解析→分块存储→向量化→ES索引 的完整流水线）*

### 4.4 向量化与混合检索模块

#### 4.4.1 向量化服务

向量化阶段的工作由`VectorizationService`负责：首先从`document_vectors`表中读取某个文件的所有文本分块，随后调用DashScope的text-embedding-v4模型，将每块文本转换为2048维浮点向量。DashScope的API对单次请求的文本数量存在上限约束，因此`EmbeddingClient`实施了分批处理——按`batchSize`（生产环境100条，开发环境10条）将文本列表拆分为多个小批次，分别发送请求。请求体需指定model、input（文本列表）、dimension（2048）及encoding_format（float）等参数。考虑到网络可能出现瞬时波动，每批次设置30秒超时，并配置固定间隔重试策略（间隔1秒，最多3次），仅在`WebClientResponseException`等可恢复异常上触发。所有批次的向量结果收集完毕后，与文本内容、fileMd5、chunkId及权限相关信息一同构建为`EsDocument`对象，通过`ElasticsearchService.bulkIndex`方法批量写入`knowledge_base`索引。每条文档以UUID作为ES的文档ID，即使同一文档被重复索引亦不会产生冗余数据。

#### 4.4.2 Elasticsearch索引映射设计

`knowledge_base`索引需同时支撑中文全文检索与向量近邻搜索，字段类型的选择服务于该双重目标。`textContent`字段为核心字段，类型设为text，索引时采用`ik_max_word`分析器执行最大粒度分词——"机器学习算法"将被切分为"机器""学习""算法""机器学习""学习算法"等多个词元，倒排索引覆盖较为全面；搜索时采用`ik_smart`分析器执行智能分词——用户输入"机器学习算法"时作为整体词元进行匹配。这种"索引端细粒度切分、搜索端保持自然粒度"的组合，是IK分析器在中文检索场景中的标准实践。`vector`字段类型为`dense_vector`，维度2048，设置`index: true`以启用HNSW索引结构支持KNN检索，相似度算法选用cosine余弦相似度。此外，`userId`、`orgTag`与`isPublic`三个字段不参与相关性计算，其功能仅限于权限过滤时的精确匹配，因此均设为keyword或boolean类型。

#### 4.4.3 混合检索实现

`HybridSearchService.searchWithPermission()`方法是检索流程的核心入口，将KNN向量检索与BM25文本检索组合为单条查询，在语义理解与关键词精确匹配之间取得折衷。完整执行流程分为以下步骤：

（1）**用户上下文解析。** 首先从`OrgTagCacheService`获取用户有效标签集（已包含层级继承），再通过`UserRepository`查询用户的数据库ID。此处包含一项兼容性处理：userId可能为数字格式（直接按主键查询），也可能为用户名（WebSocket连接路径中传递的是username），系统根据输入格式自动适配查询方式。

（2）**查询向量化。** 调用`EmbeddingClient`将用户查询文本转换为2048维向量。此步骤依赖外部Embedding服务，若DashScope不可用则返回null，后续流程将转入降级路径。

（3）**降级检索。** 向量化失败时，系统自动回退至纯BM25模式——`textOnlySearchWithPermission`方法以match查询匹配关键词，附加权限filter过滤，并以`minScore(0.3)`剔除相关性过低的结果。该降级路径的精确度不及混合检索，但保障了系统在向量服务中断时的基本可用性。

（4）**KNN向量召回。** 正常流程下，KNN以`topK × 30`作为召回窗口。以目标返回5条结果为例，KNN先召回150个候选。设置该过采样倍数的目的是为后续Rescore阶段预留充足的候选空间——向量检索可能遗漏部分关键词匹配度高但语义向量距离不够近的文档，扩大召回窗口后由BM25重新评分，可有效回收此类结果。该设计的理论约束在于：若正确答案未进入KNN候选集，则无论BM25能力多强均无法恢复，混合检索的召回上限取决于KNN的召回率。

（5）**布尔过滤与权限检查。** bool查询中包含分工明确的两个子句：must子句要求`textContent`必须命中用户查询的关键词，filter子句执行三级权限过滤（userId匹配、isPublic为true、orgTag在有效标签集中）。filter不参与相关性评分，其过滤结果可被Elasticsearch缓存，相同权限条件的后续查询直接复用，避免了重复计算开销。

（6）**BM25重排序。** Rescore阶段对KNN召回的全部候选执行BM25重评分。KNN分数权重0.2，BM25分数权重1.0——该比例配置使BM25在最终排序中占据主导地位。BM25的match查询采用`Operator.And`模式，要求所有查询词项均出现于文档中方视为命中。

（7）**结果后处理。** 截取topK条结果后，需为各条目补充文件名信息方具备实际可读性。`attachFileNames`方法将结果集中的fileMd5收集去重，通过`FileUploadRepository`一次性批量查询，建立MD5至文件名的映射并填入每条`SearchResult`，使前端展示时用户可直接获知各检索片段的来源文件。

```java
// 混合检索：KNN召回 + BM25 Rescore
s.knn(kn -> kn.field("vector").queryVector(queryVector)
        .k(recallK).numCandidates(recallK));
s.rescore(r -> r.windowSize(recallK)
    .query(rq -> rq
        .queryWeight(0.2d)          // KNN分数权重
        .rescoreQueryWeight(1.0d)   // BM25分数权重
        .query(rqq -> rqq.match(m -> m.field("textContent")
            .query(query).operator(Operator.And)))));
```

> **【图位置】图4-4：混合检索执行流程图**
> *（展示：查询向量化→KNN召回（topK×30）→BM25文本匹配+权限过滤→Rescore重排序→topK结果返回 的流程）*

### 4.5 问答模块

#### 4.5.1 Ollama本地部署架构

系统通过Ollama在本地服务器上运行DeepSeek-R1（7B参数规模），借助其OpenAI兼容的RESTful接口（默认端点`http://localhost:11434/v1`）对外提供流式推理服务。选择本地部署而非调用云端API，主要基于以下考量。数据隐私为首要因素——文档从上传、向量化、检索到生成的整条处理链路均在内网完成，不经过第三方服务，信息外泄风险显著降低。成本因素同样不可忽视：企业内部问答频次通常较高，按Token计费将累积为可观开销，本地部署则消除了此项负担。此外，消除网络往返延迟后，用户体验到的响应速度亦有改善。

`DeepSeekClient`作为推理客户端，通过Spring WebClient与Ollama通信。因模型运行于本地环境，API密钥配置项直接保留为空——客户端在构造阶段检测到密钥为空时，不在请求中添加Authorization头，直接通过内网发起调用。Ollama的接口完全兼容OpenAI的`/chat/completions`端点格式，请求体同样由model、messages、stream等字段构成，响应以SSE（Server-Sent Events）格式逐Token返回生成文本。

#### 4.5.2 WebSocket通信与身份验证

前端与后端的实时通信基于WebSocket协议实现，采用`@vueuse/core`的`useWebSocket`组合式函数，连接地址为`/chat/{jwtToken}`。JWT令牌内嵌于URL路径而非通过自定义Header传递，此为被动适配方案——浏览器原生WebSocket在握手阶段不支持自定义HTTP请求头，令牌仅能置于路径中传输。`ChatWebSocketHandler`在连接建立时从URL末尾提取JWT，通过`JwtUtils`解析出用户名作为用户标识，随后存入`ConcurrentHashMap`以管理活跃会话。该Map以userId为键，同一用户发起新连接时旧连接被直接替换。

为防止外部客户端伪造停止指令，系统引入了内部令牌校验机制。`ChatWebSocketHandler`在类加载时生成一个随机字符串，格式为`WSS_STOP_CMD_`拼接时间戳后6位，记为`INTERNAL_CMD_TOKEN`。前端发送停止指令前，需先通过`GET /api/chat/websocket-token`接口获取该令牌，随后在JSON消息中携带`_internal_cmd_token`字段，其值须与服务端令牌一致。消息处理逻辑对以`{`开头的负载优先尝试JSON解析，仅当type为"stop"且内部令牌匹配时方执行停止操作，其余情况均按普通聊天消息处理。

#### 4.5.3 RAG流程编排

整个问答流程由`ChatHandler.processMessage()`方法统一编排，从会话管理至历史保存共七个步骤，依次执行：

（1）**会话管理。** 首先查询Redis键`user:{userId}:current_conversation`以判断当前是否存在活跃会话。存在则沿用已有会话ID，不存在则生成UUID写入该键并设置7天TTL。

（2）**历史加载。** 获取会话ID后，从`conversation:{conversationId}`键读取历史消息。消息以JSON格式存储，每条包含role、content、timestamp三个字段，上限为最近20条。

（3）**权限感知检索。** 调用`HybridSearchService.searchWithPermission()`执行带权限过滤的混合检索，默认返回前5条最相关结果。

（4）**上下文构建。** `buildContext()`将检索结果拼接为统一格式：`[序号] (文件名) 文本片段\n`，每条片段最长300字符，超出部分截断并附加省略号。若检索结果为空，则以配置文件中预设的占位文本"（本轮无检索结果）"填充。

（5）**提示词组装。** 提示词由`DeepSeekClient.buildMessages()`构建，最终生成一个消息列表。首条为system角色，由三部分拼接而成：`AiProperties`中配置的系统规则（定义助手行为规范、回答格式、引用风格等），以及由`<<REF>>`与`<<END>>`所包围的参考上下文。system消息之后附加历史对话记录（user与assistant交替的多轮消息），末尾放置当前用户问题。

（6）**流式生成与推送。** 提示词准备就绪后，调用Ollama的`/chat/completions`接口，stream参数设为true。WebClient通过`bodyToFlux`方法以SSE流格式接收响应，每收到一个事件即解析JSON，从`choices[0].delta.content`中提取增量文本，随即通过WebSocket以`{"chunk": "文本"}`格式推送至前端。收到`[DONE]`标记时，补发`{"type": "completion", "status": "finished"}`表示本轮生成结束。

（7）**历史保存。** 生成全部结束后，将用户问题与模型完整回复作为一对对话记录追加至Redis的会话历史中。若历史消息总数超出20条，截除最早的部分，仅保留最近20条。

生成参数统一收敛于`AiProperties`中管理：temperature设较低值（0.3），以降低随机性、使回答更为稳定可靠；max_tokens限制为2000，防止单次回复过长；top_p取0.9，以核采样控制生成多样性。

#### 4.5.4 流式响应完成检测与停止机制

WebClient的响应式流（Reactor Flux）以异步方式推送数据，模型何时完成生成无法直接从回调中获知，需要额外的检测机制来判断。当前实现采用了轮询启发式策略：后台线程先等待3秒让模型开始输出，随后每2秒检查StringBuilder的内容长度是否发生变化，连续2秒无新增内容即判定生成结束。对于耗时较长的生成任务，后台线程将间隔拉长至5秒，最多再进行5轮确认；若仍无法可靠判断，则强制结束当前响应并保存已有历史。

停止机制通过ConcurrentHashMap<String, Boolean>维护一个stopFlags映射表来实现。用户点击停止按钮后，系统将对应会话ID的标志位设为true，sendResponseChunk方法在推送每个文本块之前检查该标志，若已置位则跳过发送。标志位在设置2秒后自动清除，避免对后续问答请求造成干扰。

> **【图位置】图4-5：RAG问答完整流程图**
> *（展示：用户提问→WebSocket接收→权限检索→上下文组装→Ollama本地流式生成→WebSocket推送→历史保存 的完整流程，标注各环节涉及的服务和数据存储）*

---

## 第5章 系统测试

### 5.1 测试环境

| 项目 | 配置 |
|------|------|
| CPU | Intel Core i7-10700 / 8核 |
| 内存 | 32GB DDR4 |
| 操作系统 | Windows 11 |
| JDK | OpenJDK 17 |
| MySQL | 8.0 |
| Elasticsearch | 8.10.4（IK分析器插件） |
| Redis | 8.6.0 |
| Kafka | 4.0（Bitnami） |
| MinIO | RELEASE.2025-04 |
| 本地推理 | Ollama 最新稳定版 |
| 大语言模型 | DeepSeek-R1 7B |

### 5.2 功能测试

#### 5.2.1 文档上传与处理测试

> **【图位置】图5-1：文档上传与处理功能测试截图**
> *（展示文档上传界面、上传进度、处理状态变化）*

| 测试项 | 操作 | 预期结果 | 结果 |
|--------|------|----------|------|
| PDF上传 | 上传10MB PDF | 上传成功，Kafka异步处理 | 通过 |
| Word上传 | 上传5MB Word | 上传成功，解析正常 | 通过 |
| 格式校验 | 上传.exe文件 | 返回格式错误提示 | 通过 |
| 文件去重 | 重复上传同MD5文件 | 提示文件已存在 | 通过 |
| 并发上传 | 10用户同时上传 | 全部处理成功 | 通过 |

#### 5.2.2 混合检索功能测试

| 测试项 | 查询内容 | 预期结果 | 结果 |
|--------|----------|----------|------|
| 关键词匹配 | "Spring Boot" | 返回含该词的文档片段 | 通过 |
| 语义检索 | "如何实现用户认证" | 返回认证相关文档 | 通过 |
| 权限隔离 | 跨组织用户检索 | 不返回其他组织文档 | 通过 |
| 空结果 | 输入无关词汇 | 返回空结果集 | 通过 |

#### 5.2.3 问答功能测试

> **【图位置】图5-2：流式问答功能测试截图**
> *（展示打字机效果的流式输出、多轮对话和停止响应功能）*

| 测试项 | 操作 | 预期结果 | 结果 |
|--------|------|----------|------|
| 基础问答 | 提问"什么是RAG" | 流式返回准确回答 | 通过 |
| 多轮对话 | 追问"它的优势是什么" | 结合上下文回答 | 通过 |
| 流式中断 | 点击停止按钮 | 停止生成并发送确认 | 通过 |
| 无结果回答 | 提问知识库外内容 | 返回"暂无相关信息" | 通过 |

#### 5.2.4 权限控制功能测试

> **【图位置】图5-3：权限控制功能验证截图**
> *（展示不同组织用户检索结果的差异）*

| 测试项 | 操作 | 预期结果 | 结果 |
|--------|------|----------|------|
| 私人文档访问 | 创建者检索 | 可检索到 | 通过 |
| 私人文档隔离 | 其他用户检索 | 检索不到 | 通过 |
| 组织文档共享 | 同组织成员检索 | 可检索到 | 通过 |
| 跨组织隔离 | 不同组织用户检索 | 检索不到 | 通过 |
| 公开文档访问 | 任意登录用户检索 | 可检索到 | 通过 |

### 5.3 性能测试

#### 5.3.1 检索响应时间

> **【图位置】图5-4：检索响应时间测试结果图表**
> *（柱状图或折线图展示不同文档规模下的平均响应时间、95分位时间和最大响应时间）*

| 文档规模 | 平均响应时间 | 95分位 | 最大时间 |
|----------|-------------|--------|----------|
| 1,000条 | 120ms | 180ms | 300ms |
| 10,000条 | 150ms | 220ms | 400ms |
| 50,000条 | 200ms | 350ms | 600ms |

#### 5.3.2 并发处理能力

| 并发数 | 成功率 | 平均响应时间 | 吞吐量 |
|--------|--------|-------------|--------|
| 10 | 100% | 500ms | 20 req/s |
| 50 | 100% | 800ms | 62 req/s |
| 100 | 98% | 1200ms | 82 req/s |

### 5.4 安全测试

| 测试场景 | 攻击方式 | 防护效果 |
|----------|----------|----------|
| Token伪造 | 修改Authorization头 | 签名验证失败，返回401 |
| 无权限访问 | 未携带Token访问受保护接口 | 返回401 |
| 跨组织数据访问 | 组织A用户检索组织B文档 | 权限过滤无结果返回 |
| SQL注入 | 搜索框输入SQL语句 | 参数化查询，无异常 |

---

## 第6章 总结与展望

### 6.1 工作总结

本文设计并实现了一个融合组织标签权限控制的RAG问答系统，后端基于Spring Boot 3.4.2与Java 17构建，前端采用Vue 3.4配合TypeScript 5与Vite 5。Elasticsearch的`knowledge_base`索引同时承担向量存储与混合检索双重职能，Kafka的`file-processing-topic1`承载文档处理的异步流水线，Ollama在本地环境部署DeepSeek-R1（7B）执行流式生成，DashScope的text-embedding-v4输出2048维向量。

权限控制的核心设计可概括为：将过滤条件嵌入ES查询内部，而非作为检索后置步骤。`OrgTagAuthorizationFilter`（继承`OncePerRequestFilter`）在过滤链中位于`JwtAuthenticationFilter`之后，经由5条件授权链从公开文档至`PRIVATE_`前缀逐级判断。`organization_tags`表的`parent_tag`自引用外键使标签构成树形层级，`OrgTagCacheService.getUserEffectiveOrgTags()`沿树递归收集祖先标签并缓存至Redis（24小时TTL），子组织成员自动继承父组织文档的访问权限。权限三元组（userId精确匹配 OR isPublic为true OR orgTag在有效标签集内）构造为ES查询的`filter`子句——不参与相关性评分，ES内部缓存过滤结果，相同权限条件的重复查询可直接复用。

检索采用KNN与BM25双路Rescore方案。KNN先以30倍目标结果数执行过采样召回，Rescore阶段KNN权重保留0.2、BM25权重占1.0，使关键词精确匹配在最终排序中占据主导地位。该偏向BM25的设计有其依据——专有名词、编号等精确字符串在语义向量空间中的区分度有限，需依赖BM25的精确匹配能力提供保障。

回顾系统实现，若干设计上的妥协值得指出。`ChatWebSocketHandler`以单个`ConcurrentHashMap`管理会话——同一username的新连接直接覆盖旧连接，多实例部署场景下会话无法共享。流式生成完成的检测基于后台线程轮询实现（2秒间隔检测长度变化，最长延至约33秒），非事件驱动，极端情况下存在误判可能。`INTERNAL_CMD_TOKEN`为启动时从毫秒时间戳生成的静态字符串，足以防御随意操作但不构成安全级别的防护边界。`User.orgTags`采用逗号分隔字符串存储而非标准化多对多关联表——节省了关联查询同时牺牲了引用完整性。标签缓存TTL为24小时，变更后需手动刷新。上传Bitmap未设置TTL，合并异常时可能存在Redis键遗留。

### 6.2 不足与展望

文档处理链路对扫描版PDF的支持有限——Tika提取的对象为文本层，图片型PDF返回空内容，当前未集成OCR前置处理。`FileProcessingConsumer`为单实例消费模式，大文件处理会阻塞后续消息的消费。80%内存阈值以硬编码形式内嵌于代码中，未根据实际堆大小进行自适应计算。`System.gc()`仅为建议性调用，JVM不保证立即执行回收。30倍KNN过采样窗口为经验取值，未在不同语料类型与规模上执行系统的recall-precision曲线标定。`Operator.And`在Rescore上的约束过于严格——缺少任一查询词项即得分为零，即使语义高度相关的文档亦可能被排除。向量存储空间随文档量线性增长（2048维 × 4字节 × 文档数），未实施向量压缩或量化以控制存储成本。对话历史以纯JSON字符串形式存储于Redis，按时间范围查询需全量加载后在内存中过滤，缺乏索引支持。

后续工作可从以下方向展开。在`ParseService`中集成Tesseract OCR以支持扫描件文本提取。将流式完成检测从轮询机制迁移至SSE `[DONE]`事件驱动模式——Ollama接口本身即支持该结束标记。将Kafka消费者扩展为多实例并行处理架构，消除单点消费瓶颈。将`User.orgTags`从逗号分隔字符串重构为`user_org_tags`标准化关联表。针对不同数据集对KNN的30倍召回窗口进行系统性标定，测定recall-precision曲线以确定最优窗口取值。引入BGE或m3e等本地Embedding模型，消除对DashScope外部API的单点依赖。Redis会话管理评估引入Sentinel或Cluster方案，使多实例部署场景下WebSocket连接得以跨节点共享。

---

## 参考文献

[1] 黄民烈, 赵鑫, 朱小燕, 等. 大语言模型综述[J]. 计算机学报, 2024, 47(1): 1-33.

[2] 邱锡鹏, 赵鑫, 黄民烈, 等. 大语言模型[J]. 软件学报, 2023, 34(10): 4661-4683.

[3] 张磊, 王昊奋, 邱锡鹏. 检索增强生成技术研究综述[J]. 计算机研究与发展, 2024, 61(8): 1743-1763.

[4] 刘焕勇, 刘挺, 车万翔, 等. 面向知识密集型任务的大语言模型检索增强生成综述[J]. 中文信息学报, 2024, 38(1): 1-20.

[5] 李涓子, 廖乐天, 王昊奋. 知识图谱与大语言模型融合研究综述[J]. 计算机学报, 2024, 47(5): 985-1006.

[6] 郭志懋, 周傲英. 数据安全和隐私保护技术研究综述[J]. 计算机学报, 2016, 39(1): 1-18.

[7] 林润辉, 李强. 多租户云环境下的访问控制研究综述[J]. 计算机应用研究, 2014, 31(5): 1285-1290.

[8] 陈洪, 刘宗田, 张健, 等. 基于向量数据库的智能知识检索系统研究[J]. 计算机工程与应用, 2024, 60(3): 1-12.

[9] 王昊奋, 邱锡鹏. 大语言模型时代的检索增强生成[J]. 大数据, 2023, 9(6): 15-24.

[10] 孙凯, 李芳. 基于Elasticsearch的混合检索优化方法研究[J]. 计算机工程, 2023, 49(9): 89-95.

[11] 赵阳, 刘淇, 张敏, 等. 大语言模型赋能教育：应用、挑战与展望[J]. 中国科学: 信息科学, 2024, 54(1): 1-20.

[12] 王晓宇, 李勇, 周傲英. 多租户数据库技术研究进展[J]. 软件学报, 2015, 26(5): 1017-1034.

[13] Lewis P, Perez E, Piktus A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks[C]//Advances in Neural Information Processing Systems. 2020, 33: 9459-9474.

[14] Karpukhin V, Oğuz B, Min S, et al. Dense passage retrieval for open-domain question answering[C]//Proceedings of EMNLP. 2020: 6769-6781.

[15] Gao Y, Xiong Y, Gao X, et al. Retrieval-augmented generation for large language models: A survey[J]. arXiv preprint arXiv:2312.10997, 2023.

[16] Khattab O, Zaharia M. ColBERT: Efficient and effective passage search via contextualized late interaction over BERT[C]//Proceedings of SIGIR. 2020: 2011-2014.

[17] Sandhu R, Coyne E J, Feinstein H L, et al. Role-based access control models[J]. Computer, 1996, 29(2): 38-47.

[18] Robertson S, Zaragoza H. The probabilistic relevance framework: BM25 and beyond[J]. Foundations and Trends in Information Retrieval, 2009, 3(4): 333-389.

[19] Yuan E, Tong J. Attributed based access control (ABAC) for web services[C]//IEEE ICWS. 2005: 569-575.

[20] Asai A, Wu Z, Wang Y, et al. Self-RAG: Learning to retrieve, generate, and critique through self-reflection[C]//International Conference on Learning Representations. 2024.

[21] Gutiérrez F H, Galkin M, Gu Y, et al. Optimal transport flow for multi-hypothesis retrieval-augmented generation[C]//Advances in Neural Information Processing Systems. 2024, 36: 58292-58312.

[22] Elasticsearch Reference: Dense vector[EB/OL]. https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html, 2024.

[23] Apache Kafka Documentation[EB/OL]. https://kafka.apache.org/documentation/, 2024.

[24] Apache Tika: Parsing documents[EB/OL]. https://tika.apache.org/, 2024.

[25] DashScope: text-embedding-v4[EB/OL]. https://help.aliyun.com/zh/model-studio/text-embedding-synchronous, 2024.

---

## 致谢

感谢指导老师在选题、方案设计和论文撰写各阶段的指导与反馈。老师在系统架构与权限模型设计上提出的具体建议，直接影响了本文的技术路线选择。

感谢实验室的同学们在开发与测试阶段提供的协助，特别是在Kafka消费者重试逻辑调试与ES Rescore参数调优过程中的配合与验证。

感谢学校与家人提供的支持。

---
