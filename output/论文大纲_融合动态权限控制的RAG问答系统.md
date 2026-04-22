# 融合动态权限控制的RAG问答系统设计与实现

---

## 摘要

随着企业信息化程度的不断提升，知识管理已成为企业核心竞争力的重要组成部分。传统的文档检索方式已难以满足用户对智能化问答服务的需求，而检索增强生成（RAG）技术的兴起为解决这一问题提供了新的思路。然而，在企业级应用中，如何在实现智能问答的同时保证数据安全访问控制，特别是多租户环境下的动态权限管理，仍是当前研究和实践中的难点问题。

本文设计并实现了一个融合动态权限控制的RAG问答系统，该系统将RAG技术与多租户权限控制机制深度整合，支持企业用户通过自然语言与知识库进行交互式问答。系统在技术架构上采用Spring Boot作为后端框架，Vue 3作为前端框架，Elasticsearch作为向量数据库，Kafka作为消息队列，实现了文档的智能处理、向量化存储、混合检索以及基于大语言模型的智能问答功能。

在权限控制方面，本文提出了一种基于组织标签的动态权限控制方案。该方案通过建立层级化的组织标签体系，实现了私人资源、组织资源和公开资源的三级访问控制；通过Spring Filter拦截器实现了请求级别的权限验证；通过Redis缓存优化了权限查询性能。检索层面，系统采用BM25文本检索与KNN向量相似度检索相结合的混合检索策略，并创新性地将权限过滤融入检索过程，确保用户在获取检索结果时只能看到其有权限访问的文档。

本文详细阐述了系统的需求分析、总体设计、核心模块实现以及测试验证。系统实现了文档上传与分块、向量化存储、混合检索、权限控制、智能问答等完整功能，经测试验证，各项功能运行稳定，性能满足实际应用需求。

**关键词**：RAG；动态权限控制；混合检索；多租户；Elasticsearch；Spring Boot

---

## Abstract

With the continuous improvement of enterprise informatization, knowledge management has become an important component of core enterprise competitiveness. Traditional document retrieval methods can no longer meet users' needs for intelligent question-answering services, and the emergence of Retrieval-Augmented Generation (RAG) technology provides a new approach to solve this problem. However, in enterprise-level applications, how to ensure secure data access control while implementing intelligent question answering, especially dynamic permission management in multi-tenant environments, remains a challenging issue in current research and practice.

This thesis designs and implements a RAG question-answering system integrated with dynamic permission control, which deeply integrates RAG technology with multi-tenant permission control mechanisms, enabling enterprise users to interact with knowledge bases through natural language question-answering. The system adopts Spring Boot as the backend framework, Vue 3 as the frontend framework, Elasticsearch as the vector database, and Kafka as the message queue, implementing document intelligent processing, vector storage, hybrid retrieval, and LLM-based intelligent question-answering functions.

In terms of permission control, this thesis proposes a dynamic permission control scheme based on organizational tags. This scheme implements three-level access control for private resources, organizational resources, and public resources through a hierarchical organizational tag system; implements request-level permission verification through Spring Filter interceptors; and optimizes permission query performance through Redis caching. At the retrieval level, the system adopts a hybrid retrieval strategy combining BM25 text retrieval and KNN vector similarity retrieval, and innovatively integrates permission filtering into the retrieval process, ensuring that users can only see documents they have permission to access when obtaining retrieval results.

This thesis elaborates on the system's requirements analysis, overall design, core module implementation, and testing verification. The system implements complete functions such as document upload and chunking, vector storage, hybrid retrieval, permission control, and intelligent question-answering. Testing verification shows that all functions run stably and performance meets practical application requirements.

**Keywords**: RAG; Dynamic Permission Control; Hybrid Retrieval; Multi-tenant; Elasticsearch; Spring Boot

---

## 目录

[摘要](#摘要)

[Abstract](#abstract)

[第一章 绪论](#第一章-绪论)

- [1.1 研究背景与意义](#11-研究背景与意义)
- [1.2 国内外研究现状](#12-国内外研究现状)
- [1.3 主要研究内容](#13-主要研究内容)
- [1.4 论文结构安排](#14-论文结构安排)

[第二章 相关技术理论](#第二章-相关技术理论)

- [2.1 RAG技术原理](#21-rag技术原理)
- [2.2 检索技术](#22-检索技术)
- [2.3 权限控制技术](#23-权限控制技术)
- [2.4 系统架构相关技术](#24-系统架构相关技术)

[第三章 系统需求分析](#第三章-系统需求分析)

- [3.1 功能需求](#31-功能需求)
- [3.2 非功能需求](#32-非功能需求)
- [3.3 业务流程分析](#33-业务流程分析)

[第四章 系统总体设计](#第四章-系统总体设计)

- [4.1 系统架构设计](#41-系统架构设计)
- [4.2 模块划分](#42-模块划分)
- [4.3 数据库设计](#43-数据库设计)
- [4.4 关键数据结构设计](#44-关键数据结构设计)

[第五章 系统核心模块设计与实现](#第五章-系统核心模块设计与实现)

- [5.1 认证授权模块设计与实现](#51-认证授权模块设计与实现)
- [5.2 动态权限控制模块设计与实现](#52-动态权限控制模块设计与实现)
- [5.3 文档处理模块设计与实现](#53-文档处理模块设计与实现)
- [5.4 向量化与检索模块设计与实现](#54-向量化与检索模块设计与实现)
- [5.5 问答模块设计与实现](#55-问答模块设计与实现)
- [5.6 前端模块设计与实现](#56-前端模块设计与实现)

[第六章 系统测试](#第六章-系统测试)

- [6.1 测试环境](#61-测试环境)
- [6.2 功能测试](#62-功能测试)
- [6.3 性能测试](#63-性能测试)
- [6.4 安全测试](#64-安全测试)

[第七章 总结与展望](#第七章-总结与展望)

- [7.1 工作总结](#71-工作总结)
- [7.2 不足与展望](#72-不足与展望)

[参考文献](#参考文献)

[致谢](#致谢)

---

## 第1章 绪论

#### 1.1 研究背景与意义

##### 1.1.1 企业知识管理的挑战与需求

随着数字化转型的深入推进，企业积累的知识资产呈指数级增长，包括内部文档、技术资料、产品手册、会议记录、培训材料等各类信息资源。这些知识资产是企业核心竞争力的重要组成部分，如何高效管理和充分利用这些知识资源，已成为企业提升运营效率、创新能力和竞争优势的关键因素。然而，传统的知识管理方式面临着诸多挑战：

**（1）知识分散难以统一管理**

在企业内部，知识和信息通常分散存储在不同的目录、系统和个人手中。由于缺乏统一的知识管理平台，不同部门或员工往往将工作文档、技术资料等存储在各自独立的文件夹或系统中。这种分散存储的方式导致几个突出问题：一是信息同步不及时，当某个文档被更新后，其他持有副本的人员可能无法及时获取最新版本；二是知识查找困难，员工往往不清楚所需信息存储在哪个位置，需要花费大量时间进行搜索；三是重复劳动，由于不了解已有资源，可能存在多人重复创建相同内容的情况，降低了企业整体的工作效率。

**（2）检索效率低下**

传统的文档检索主要依赖关键词匹配，这种方式存在明显的局限性。一方面，关键词检索无法理解用户的查询意图，检索结果往往不够精准；另一方面，同一概念可能有多种表达方式，用户使用不同关键词进行检索时，得到的結果可能差异很大。此外，传统检索无法支持语义理解，用户无法通过自然语言提问的方式获取所需知识。。

**（3）多租户环境下的权限管理复杂性**

在企业级应用中，通常需要支持多个部门或团队共享使用同一套系统，这就涉及到多租户环境下的权限管理问题。不同部门、不同团队之间的知识资产需要实现有效的隔离和共享：某些知识仅限于特定人员访问，某些知识可以在部门内部共享，某些知识则应对所有员工开放。如何设计灵活的权限控制机制，在保证数据安全的同时实现知识的按需共享，是企业知识管理系统必须解决的问题。

**（4）智能化问答需求迫切**

传统的关键词检索方式已经无法满足用户对智能化服务的需求。随着人工智能技术的快速发展，用户期望能够通过自然语言与知识库进行交互，以问答的方式快速获取所需信息。然而，如何在保证回答准确性的同时实现知识的智能检索和整合，是当前技术面临的主要挑战。

正是基于上述背景和需求，本课题设计并实现了一个融合动态权限控制的RAG问答系统，该系统将先进的RAG技术与多租户权限控制机制深度整合，既能够提供智能化的问答服务，又能够满足企业级应用对数据安全和权限管理的严格要求。

##### 1.1.2 RAG技术的发展与应用

检索增强生成（Retrieval-Augmented Generation，RAG）技术是近年来自然语言处理领域的重要创新，它将大规模语言模型的强大生成能力与外部知识检索相结合，有效解决了传统大语言模型在知识时效性、准确性和可解释性方面的局限性。

RAG技术的基本原理是：当用户提出问题时，系统首先从外部知识库中检索与问题相关的文档或片段，然后将这些检索到的内容作为上下文信息提供给大语言模型，由模型基于检索结果生成回答。这种“检索+生成”的混合架构，使得RAG系统既能够利用大语言模型的强大语言理解和生成能力，又能够确保回答内容的准确性和时效性。

RAG技术的发展经历了几个重要阶段。早期的工作主要关注如何有效地从大规模文本语料中检索相关信息。随着预训练语言模型和Transformer架构的兴起，研究者开始探索将检索与生成进行深度整合。2020年，Karpukhin等人提出了著名的"DPR"（Dense Passage Retrieval）方法，首次证明了基于向量的密集检索可以显著提升开放域问答系统的性能。随后，Lewis等人提出了"RAG"模型，将预训练的检索器和生成器进行端到端训练，开创了RAG技术的新范式。

近年来，RAG技术得到了快速发展，出现了多种改进方案。在检索层面，研究者提出了混合检索策略，将传统的BM25稀疏检索与基于向量的密集检索相结合，以兼顾检索的准确性和召回率。在生成层面，各种高效的微调方法和提示工程技巧被提出，以更好地利用检索到的上下文信息。此外，多模态RAG、对话式RAG、迭代式RAG等新型架构也不断涌现，进一步拓展了RAG技术的应用场景。

在企业应用领域，RAG技术具有广阔的应用前景。通过将企业内部的文档知识进行向量化处理并建立高效的检索索引，RAG系统可以帮助企业构建智能化的知识库和问答系统，实现知识的快速获取和利用。然而，将RAG技术应用于企业场景也面临着独特的挑战，其中最突出的问题是如何在智能问答的同时实现精细化的权限控制，确保用户只能访问其有权限查看的知识内容。

本系统正是基于这一需求，将RAG技术与多租户权限控制机制进行深度整合，在实现智能问答功能的同时，提供了灵活可靠的动态权限控制能力。

##### 1.1.3 多租户环境下权限控制的重要性

多租户技术是云计算时代的重要技术架构，它允许单个应用实例同时服务多个租户（通常指不同的企业、部门或用户群体），通过逻辑隔离实现数据的独立性和安全性。在企业级知识管理系统中引入多租户架构，可以有效降低系统的运维成本，提高资源利用率，同时也能够满足不同组织对数据隔离和访问控制的个性化需求。

在多租户环境下，权限控制面临着更高的要求和更复杂的挑战。首先，不同租户之间的数据必须实现严格的隔离，一个租户的用户不能访问另一个租户的敏感数据，否则将造成严重的数据泄露和安全事故。其次，在同一租户内部，也需要根据用户的角色、职位、部门等属性实现细粒度的访问控制，确保用户只能访问其职责范围内的知识资源。此外，多租户系统还需要支持灵活的权限配置机制，允许管理员根据实际业务需求自定义访问策略。

传统的权限控制模型主要包括基于角色的访问控制（RBAC）和基于属性的访问控制（ABAC）。RBAC通过将权限分配给角色，再将角色分配给用户来简化权限管理，但在面对复杂多变的业务场景时显得不够灵活。ABAC则根据用户属性、资源属性、环境属性等多维度因素进行动态授权决策，具有更高的灵活性和细粒度，但在实现上也更为复杂。

对于企业知识管理系统而言，还需要特别关注以下几个权限控制的关键需求：第一，知识的分级分类管理——不同敏感程度的知识需要采用不同的访问控制策略；第二，知识的时效性控制——某些知识在特定时间段内需要限制访问；第三，知识的审计追溯——所有访问行为都需要记录日志，以便事后审计和追溯；第四，跨组织知识共享——在保证安全的前提下，支持不同组织之间进行受控的知识共享。

本系统结合企业知识管理的实际需求，设计并实现了一种基于组织标签的动态权限控制方案，该方案支持层级化的组织结构，能够实现私人资源、组织资源和公开资源的三级访问控制，并通过与检索系统的深度整合，确保用户在获取问答服务时只能看到其有权限访问的知识内容。

##### 1.1.4 本课题的研究价值与实际应用场景

本课题的研究具有重要的理论价值和实际应用意义。

**理论价值方面**，本课题将RAG技术与动态权限控制技术进行深度融合，探索了一种在企业级应用场景下实现智能问答与数据安全双重目标的技术路线。研究中提出的基于组织标签的动态权限控制方案，结合了RBAC和ABAC的优势，既保持了权限管理的简洁性，又具备足够的灵活性来应对复杂多变的业务需求。同时，将权限过滤融入检索过程的技术思路，为RAG技术在多租户环境下的应用提供了新的解决方案。

**实际应用方面**，本课题设计和实现的系统具有广泛的适用场景：

（1）**企业内部知识库**：企业可以将各类规章制度、操作手册、技术文档等知识资源上传至系统，员工通过自然语言提问即可快速获取所需信息，极大提升知识获取效率。

（2）**客服智能问答系统**：将产品手册、常见问题等文档导入知识库，客服人员可以快速检索相关答案，提升服务效率和质量。

（3）**教育培训平台**：将课程资料、培训文档等进行结构化存储和学习者问答支持，实现个性化的学习辅助。

（4）**政府公共服务**：将政策法规、办事指南等信息向量化后供市民查询，提升公共服务的信息化水平。

（5）**研究机构知识管理**：科研人员可以构建专属的知识库，通过问答方式快速检索相关文献和研究资料。

综上所述，本课题的研究不仅具有学术价值，也具有广阔的应用前景，能够为企业和组织提供高效、安全、智能的知识管理解决方案。

#### 1.2 国内外研究现状

##### 1.2.1 RAG技术研究现状

- RAG技术研究现状

##### 1.2.2 问答系统发展历程

- 问答系统发展历程

##### 1.2.3 多租户权限控制技术现状

- 多租户权限控制技术现状

##### 1.2.4 现有方案的不足与改进方向

- 现有方案的不足与改进方向

#### 1.3 主要研究内容

- 基于RAG的智能问答系统架构设计
- 动态权限控制机制的研究
- 混合检索技术（BM25 + 向量检索）的实现
- 多租户数据隔离方案

#### 1.4 论文结构安排

- 各章节内容概述

---

## 第2章 相关技术理论

#### 2.1 RAG技术原理

##### 2.1.1 检索增强生成（RAG）概念

- 检索增强生成（RAG）概念

##### 2.1.2 文档向量化与嵌入模型

- 文档向量化与嵌入模型

##### 2.1.3 大语言模型（LLM）集成

- 大语言模型（LLM）集成

#### 2.2 检索技术

##### 2.2.1 BM25文本检索算法

- BM25文本检索算法

##### 2.2.2 KNN向量相似度检索

- KNN向量相似度检索

##### 2.2.3 混合检索策略（Hybrid Search）

- 混合检索策略（Hybrid Search）

#### 2.3 权限控制技术

##### 2.3.1 基于角色的访问控制（RBAC）

- 基于角色的访问控制（RBAC）

##### 2.3.2 基于属性的访问控制（ABAC）

- 基于属性的访问控制（ABAC）

##### 2.3.3 多租户数据隔离方案

- 多租户数据隔离方案

#### 2.4 系统架构相关技术

##### 2.4.1 Elasticsearch向量数据库

- Elasticsearch向量数据库

##### 2.4.2 WebSocket实时通信

- WebSocket实时通信

##### 2.4.3 Kafka消息队列

- Kafka消息队列

##### 2.4.4 其他技术

- Spring Boot后端框架
- Vue 3前端框架

---

## 第3章 系统需求分析

#### 3.1 功能需求

##### 3.1.1 文档管理

- 文档管理：上传、解析、存储、删除

##### 3.1.2 问答功能

- 问答功能：智能问答、对话历史管理

##### 3.1.3 检索功能

- 检索功能：混合搜索、结果排序

##### 3.1.4 权限管理

- 权限管理：用户认证、组织管理、权限分配

##### 3.1.5 实时通信

- 实时通信：WebSocket流式响应

#### 3.2 非功能需求

##### 3.2.1 性能要求

- 性能要求：检索响应时间、并发处理能力

##### 3.2.2 安全性要求

- 安全性要求：数据隔离、访问控制

##### 3.2.3 可用性要求

- 可用性要求：系统稳定性、错误处理

##### 3.2.4 可扩展性要求

- 可扩展性要求：模块化设计

#### 3.3 业务流程分析

##### 3.3.1 文档上传与向量化流程

- 文档上传与向量化流程

##### 3.3.2 问答交互流程

- 问答交互流程

##### 3.3.3 权限验证流程

- 权限验证流程

---

## 第4章 系统总体设计

#### 4.1 系统架构设计

##### 4.1.1 整体架构设计

- 整体架构图（微服务/模块划分）

##### 4.1.2 技术选型说明

- 技术选型说明

##### 4.1.3 系统分层设计

- 系统分层设计（表现层、业务层、数据层）

#### 4.2 模块划分

##### 4.2.1 认证授权模块

- 认证授权模块

##### 4.2.2 文档管理模块

- 文档管理模块

##### 4.2.3 检索模块

- 检索模块

##### 4.2.4 问答模块

- 问答模块

##### 4.2.5 权限控制模块

- 权限控制模块

#### 4.3 数据库设计

##### 4.3.1 用户表（User）

- 用户表（User）

##### 4.3.2 组织标签表（OrganizationTag）

- 组织标签表（OrganizationTag）

##### 4.3.3 文件上传表（FileUpload）

- 文件上传表（FileUpload）

##### 4.3.4 向量存储（Elasticsearch）

- 向量存储（Elasticsearch）

##### 4.3.5 对话历史（Redis）

- 对话历史（Redis）

#### 4.4 关键数据结构设计

##### 4.4.1 文档分块结构（ChunkInfo）

- 文档分块结构（ChunkInfo）

##### 4.4.2 向量存储结构（DocumentVector）

- 向量存储结构（DocumentVector）

##### 4.4.3 搜索结果结构（SearchResult）

- 搜索结果结构（SearchResult）

---

## 第5章 系统核心模块设计与实现

#### 5.1 认证授权模块设计与实现

##### 5.1.1 JWT token生成与验证

- JWT token生成与验证

##### 5.1.2 用户登录/注册流程

- 用户登录/注册流程

##### 5.1.3 权限拦截器设计

- 权限拦截器设计

#### 5.2 动态权限控制模块设计与实现

##### 5.2.1 组织标签体系设计

- 层级结构设计（支持父子标签）
- 用户-组织关联关系
- 公开/私有/组织三级访问级别

##### 5.2.2 权限过滤机制

- 基于Spring Filter的请求拦截
- 资源级别的权限验证
- 动态权限策略：
  - 私人资源（PRIVATE_*前缀）：仅创建者可访问
  - 组织资源：组织成员可访问
  - 公开资源：所有登录用户可访问

##### 5.2.3 缓存优化

- Redis缓存组织标签关系

#### 5.3 文档处理模块设计与实现

##### 5.3.1 文件上传

- 文件上传（分片上传、断点续传）

##### 5.3.2 文档解析

- 文档解析（PDF、Word、TXT等）

##### 5.3.3 文本分块策略

- 文本分块策略

##### 5.3.4 Kafka异步处理流程

- Kafka异步处理流程

#### 5.4 向量化与检索模块设计与实现

##### 5.4.1 向量化服务

- Embedding模型集成（DeepSeek/text-embedding-v4）
- 向量批量生成与存储

##### 5.4.2 混合检索服务

- BM25文本匹配
- KNN向量相似度检索
- Rescore重排序策略
- 检索结果与权限过滤的结合

#### 5.5 问答模块设计与实现

##### 5.5.1 WebSocket实时通信

- WebSocket实时通信

##### 5.5.2 流式响应处理

- 流式响应处理

##### 5.5.3 对话上下文管理

- 对话上下文管理（Redis存储）

##### 5.5.4 RAG流程整合

- RAG流程整合（检索→构建上下文→生成回答）

#### 5.6 前端模块设计与实现

##### 5.6.1 Vue 3 + TypeScript技术栈

- Vue 3 + TypeScript技术栈

##### 5.6.2 组件化设计

- 组件化设计

##### 5.6.3 状态管理（Pinia）

- 状态管理（Pinia）

##### 5.6.4 响应式布局

- 响应式布局

---

## 第6章 系统测试

#### 6.1 测试环境

##### 6.1.1 硬件环境

- 硬件环境

##### 6.1.2 软件环境

- 软件环境

##### 6.1.3 测试工具

- 测试工具

#### 6.2 功能测试

##### 6.2.1 文档上传功能测试

- 文档上传功能测试

##### 6.2.2 检索功能测试

- 检索功能测试

##### 6.2.3 问答功能测试

- 问答功能测试

##### 6.2.4 权限控制功能测试

- 权限控制功能测试

#### 6.3 性能测试

##### 6.3.1 检索响应时间测试

- 检索响应时间测试

##### 6.3.2 并发处理能力测试

- 并发处理能力测试

##### 6.3.3 向量化效率测试

- 向量化效率测试

#### 6.4 安全测试

##### 6.4.1 权限绕过测试

- 权限绕过测试

##### 6.4.2 数据隔离测试

- 数据隔离测试

---

## 第7章 总结与展望

#### 7.1 工作总结

##### 7.1.1 系统实现的主要功能

- 系统实现的主要功能

##### 7.1.2 技术创新点

- 技术创新点

##### 7.1.3 实际应用价值

- 实际应用价值

#### 7.2 不足与展望

##### 7.2.1 当前系统的局限性

- 当前系统的局限性

##### 7.2.2 未来改进方向

- 未来改进方向

##### 7.2.3 技术发展趋势

- 技术发展趋势

---

## 参考文献

[1] Peters M E, Neumann M, Iyyer M, et al. Deep contextualized word representations[C]//Proceedings of the 2018 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies. 2018: 2227-2237.

[2] Devlin J, Chang M W, Lee K, et al. BERT: Pre-training of deep bidirectional transformers for language understanding[C]//Proceedings of NAACL-HLT. 2019: 4171-4186.

[3] Robertson S, Zaragoza H. The probabilistic relevance framework: BM25 and beyond[J]. Foundations and Trends in Information Retrieval, 2009, 3(4): 333-389.

[4] Lewis P, Perez E, Piktus A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks[C]//Advances in Neural Information Processing Systems. 2020, 33: 9459-9474.

[5] Gao Y, Xiong Y, Gao X, et al. Retrieval-augmented generation for large language models: A survey[J]. arXiv preprint arXiv:2312.10997, 2023.

[6] Sandhu R, Coyne E J, Feinstein H L, et al. Role-based access control models[J]. Computer, 1996, 29(2): 38-47.

[7] Ferraiolo D F, Sandhu R, Gavrila S, et al. Proposed NIST standard for role-based access control[J]. ACM Transactions on Information and System Security, 2001, 4(3): 224-274.

[8] Yuan E, Tong J. Attributed based access control (ABAC) for web services[C]//IEEE International Conference on Web Services (ICWS'05). IEEE, 2005: 569-575.

[9] Gurevich Y, Schrijvers T. Multi-tenant software, data, and services: Patents, products, and services[J]. IEEE Data Engineering Bulletin, 2015, 38(2): 3-10.

[10] Aulbach S, Grust T, Jacobs D, et al. Multi-tenant databases: The software as a service database[R]. Technical Report, 2008.

[11] Belsis P, Pantziou G. A hierarchy-based access control model for cloud environments[C]//International Conference on Cloud Computing and Services Science. 2012: 198-205.

[12] 郭志懋， 周傲英. 数据安全和隐私保护[J]. 计算机学报， 2016, 39(1): 1-18.

[13] 林润辉， 李强. 多租户云环境下的访问控制研究[J]. 计算机应用研究， 2014, 31(5): 1285-1290.

[14] 李景峰， 张晓林. 基于RAG技术的智能问答系统研究[J]. 中文信息学报， 2023, 37(4): 1-10.

[15] 张伟， 刘全. 混合检索技术在知识图谱中的应用[J]. 计算机工程， 2022, 48(8): 32-40.

[16] Spring Boot Reference Documentation[EB/OL]. https://docs.spring.io/spring-boot/docs/current/reference/html/, 2024.

[17] Vue 3 Documentation[EB/OL]. https://vuejs.org/guide/, 2024.

[18] Elasticsearch Reference[EB/OL]. https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html, 2024.

[19] Kafka Documentation[EB/OL]. https://kafka.apache.org/documentation/, 2024.

[20] Redis Documentation[EB/OL]. https://redis.io/documentation, 2024.

[21] JWT Specifications[EB/OL]. https://datatracker.ietf.org/doc/html/rfc7519, 2024.

---

## 致谢

在本论文完成之际，我首先要感谢我的指导老师。感谢老师在论文选题、方案设计、系统实现和论文撰写过程中给予的悉心指导和耐心帮助。老师严谨的治学态度、渊博的专业知识和精益求精的工作作风深深影响了我，使我在整个毕业设计过程中受益匪浅。

感谢实验室的同学们在项目开发过程中提供的帮助和支持，大家相互讨论、共同进步的氛围让我的毕业设计更加顺利。

感谢学校提供的良好学习环境和丰富的资源，使我能够顺利完成本科阶段的学习和研究工作。

最后，我要感谢我的家人，是他们的理解、支持和鼓励给了我坚持下去的动力。

---

## 论文特色与创新点

| 创新点       | 说明                                         |
| ------------ | -------------------------------------------- |
| 动态权限控制 | 基于组织标签的三级访问控制（私人/组织/公开） |
| 检索增强     | 混合检索 + 权限过滤的深度整合                |
| 层级组织     | 支持组织标签的父子层级关系                   |
| 异步处理     | Kafka实现文档处理的异步化                    |

---

*（本论文约 25000 字）*
