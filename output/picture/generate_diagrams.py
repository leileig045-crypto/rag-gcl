# -*- coding: utf-8 -*-
"""
GuaiSmart 图表生成器 - 规范整齐的网格布局
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
OUTPUT_DIR = Path(__file__).parent

# ============ 通用绘制函数 ============

def draw_box(ax, x, y, w, h, text, facecolor, fontsize=9, textcolor='black'):
    """绘制圆角矩形框 - 居中文字"""
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                         boxstyle='round,pad=0.02,rounding_size=0.08',
                         facecolor=facecolor, edgecolor='#444444', linewidth=1.2)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize, color=textcolor,
            multialignment='center', wrap=True)

def draw_text(ax, x, y, text, fontsize=9, bold=False, color='black'):
    """绘制纯文本"""
    weight = 'bold' if bold else 'normal'
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            fontweight=weight, color=color)

def draw_arrow(ax, x1, y1, x2, y2):
    """绘制箭头"""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color='#555555', lw=1.5))

def draw_layer_box(ax, x, y, w, h, label, label_color, facecolor):
    """绘制层背景框 - 左上角标签"""
    box = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.1',
                        facecolor=facecolor, edgecolor='#888888', linewidth=1)
    ax.add_patch(box)
    ax.text(x + 0.15, y + h - 0.15, label, fontsize=10, fontweight='bold', color=label_color)

# ============ 01 系统架构图 ============
def create_01_system_architecture():
    """
    四层架构：接入层 → 处理层 → 服务层 → 数据层
    每层内部元素左右网格排列
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('GuaiSmart 系统架构图', fontsize=16, fontweight='bold', pad=15)

    # 画布参数
    left, right = 0.3, 13.7
    layer_h = 1.8  # 每层高度
    gap = 0.3      # 层间距
    box_w = 2.8    # 所有模块统一宽度
    # 三列均匀分布的x坐标（模块中心）
    x_centers = [2.5, 6.8, 11.1]

    # ===== 第1层：接入层 (y=8.7 ~ 10.5) =====
    y1_top = 9.5
    draw_layer_box(ax, left, y1_top - layer_h, right - left, layer_h, '接入层', '#1565C0', '#E3F2FD')

    # 接入层元素 - 3个均匀分布
    items_l1 = ['Vue 3 Web应用', '移动端 H5页面', 'WebSocket 即时通信']
    for xi, text in zip(x_centers, items_l1):
        draw_box(ax, xi, y1_top - layer_h/2, box_w, 0.9, text, '#90CAF9', 9)

    # ===== 第2层：处理层 (y=6.6 ~ 8.4) =====
    y2_top = y1_top - layer_h - gap
    draw_layer_box(ax, left, y2_top - layer_h, right - left, layer_h, '处理层', '#E65100', '#FFF3E0')

    # 处理层元素 - 6个，2行3列，统一大小
    items_l2 = [
        ('文档处理服务', '检索服务', '问答服务'),
        ('权限控制服务', '文件管理服务', '会话管理')
    ]
    for row_idx, row in enumerate(items_l2):
        y_pos = y2_top - layer_h/2 - (row_idx - 0.5) * 0.7
        for col_idx, text in enumerate(row):
            draw_box(ax, x_centers[col_idx], y_pos, box_w, 0.6, text, '#FFCC80', 8)

    # ===== 第3层：服务层 (y=4.5 ~ 6.3) =====
    y3_top = y2_top - layer_h - gap
    draw_layer_box(ax, left, y3_top - layer_h, right - left, layer_h, '服务层（外部服务）', '#2E7D32', '#E8F5E9')

    # 服务层元素 - 6个，2行3列，统一大小
    items_l3 = [
        ('DeepSeek API', 'Embedding API', 'Kafka 消息队列'),
        ('MinIO 文件存储', 'Redis 缓存', 'MySQL 关系数据库')
    ]
    for row_idx, row in enumerate(items_l3):
        y_pos = y3_top - layer_h/2 - (row_idx - 0.5) * 0.7
        for col_idx, text in enumerate(row):
            draw_box(ax, x_centers[col_idx], y_pos, box_w, 0.6, text, '#A5D6A7', 8)

    # ===== 第4层：数据层 (y=2.4 ~ 4.2) =====
    y4_top = y3_top - layer_h - gap
    draw_layer_box(ax, left, y4_top - layer_h, right - left, layer_h, '数据层', '#7B1FA2', '#F3E5F5')

    # 数据层元素 - 3个均匀分布，统一宽度
    items_l4 = ['Elasticsearch\n知识库向量存储', 'Redis 会话存储', 'MySQL 元数据存储']
    for xi, text in zip(x_centers, items_l4):
        draw_box(ax, xi, y4_top - layer_h/2, box_w, 0.9, text, '#CE93D8', 9)

    # ===== 层间箭头 =====
    draw_arrow(ax, 7, y1_top - layer_h, 7, y2_top)
    draw_arrow(ax, 7, y2_top - layer_h, 7, y3_top)
    draw_arrow(ax, 7, y3_top - layer_h, 7, y4_top)

    # 协议标注
    ax.text(7, (y1_top + y2_top - layer_h) / 2, 'HTTPS / WSS', fontsize=8, ha='center', color='#666')

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '01_system_architecture.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 01_system_architecture.png')
    plt.close()

# ============ 02 文档上传与向量化流程 ============
def create_02_document_upload():
    """
    垂直四层流程：用户操作层 → 后端处理层 → 文档解析与分块层 → 向量化存储层
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 12))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.set_title('GuaiSmart 文档上传与向量化流程', fontsize=16, fontweight='bold', pad=15)

    left, right = 0.5, 13.5
    layer_h = 2.0
    gap = 0.4
    box_w = 2.8  # 统一模块宽度
    x_centers = [2.8, 7, 11.2]  # 三列统一x坐标

    # ===== 第1层：用户操作层 =====
    y1 = 10.8
    draw_layer_box(ax, left, y1 - layer_h, right - left, layer_h, '用户操作层', '#1565C0', '#E3F2FD')

    items1 = [('用户上传文档', '#90CAF9'), ('前端格式校验', '#90CAF9')]
    x_pos = [3.5, 9.5]
    for (text, color), xi in zip(items1, x_pos):
        draw_box(ax, xi, y1 - layer_h/2, 3.5, 0.9, text, color, 9)

    # ===== 第2层：后端处理层 =====
    y2 = y1 - layer_h - gap
    draw_layer_box(ax, left, y2 - layer_h, right - left, layer_h, '后端处理层', '#E65100', '#FFF3E0')

    items2 = [
        ('文件接收\n分片上传', 'MinIO\n文件存储', 'MySQL\n保存元数据'),
        ('Kafka\n发送消息', 'FileProcessing\nConsumer', '状态更新\n"处理中"')
    ]
    for row_idx, row in enumerate(items2):
        y_pos = y2 - layer_h/2 - (row_idx - 0.5) * 0.75
        for col_idx, text in enumerate(row):
            draw_box(ax, x_centers[col_idx], y_pos, box_w, 0.65, text, '#FFCC80', 8)

    # ===== 第3层：文档解析与分块层 =====
    y3 = y2 - layer_h - gap
    draw_layer_box(ax, left, y3 - layer_h, right - left, layer_h, '文档解析与分块层', '#7B1FA2', '#F3E5F5')

    items3 = [
        ('Apache Tika\n文档解析', 'HanLP\n智能分词', '父子分块策略\n父块:1MB 子块:500字'),
        ('DocumentVector\n保存到MySQL', '', '')
    ]
    for row_idx, row in enumerate(items3):
        y_pos = y3 - layer_h/2 - (row_idx - 0.5) * 0.75
        for col_idx, text in enumerate(row):
            if text:
                draw_box(ax, x_centers[col_idx], y_pos, box_w, 0.65, text, '#CE93D8', 8)

    # ===== 第4层：向量化存储层 =====
    y4 = y3 - layer_h - gap
    draw_layer_box(ax, left, y4 - layer_h, right - left, layer_h, '向量化存储层', '#2E7D32', '#E8F5E9')

    items4 = [
        ('Embedding\nClient', 'text-embedding-v4\n模型', 'EsDocument\n构建索引文档'),
        ('Elasticsearch\n批量索引', '状态更新\n"已完成"', '')
    ]
    for row_idx, row in enumerate(items4):
        y_pos = y4 - layer_h/2 - (row_idx - 0.5) * 0.75
        for col_idx, text in enumerate(row):
            if text:
                draw_box(ax, x_centers[col_idx], y_pos, box_w, 0.65, text, '#A5D6A7', 8)

    # ===== 层间箭头 =====
    for y_top, y_bot in [(y1, y2), (y2, y3), (y3, y4)]:
        draw_arrow(ax, 7, y_top - layer_h, 7, y_bot)

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '02_document_upload_vectorize.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 02_document_upload_vectorize.png')
    plt.close()

# ============ 03 问答交互流程 ============
def create_03_qa_interaction():
    """
    垂直五层流程：用户交互 → 认证授权 → 混合检索 → RAG增强生成 → 会话管理
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 12))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.set_title('GuaiSmart 问答交互流程', fontsize=16, fontweight='bold', pad=15)

    left, right = 0.5, 13.5
    layer_h = 1.7
    gap = 0.35
    # 三列统一居中，模块左右间距相等
    box_w = 2.8
    x_centers = [3.0, 7.0, 11.0]  # [left+1.1+1.4, center, right-1.1-1.4]

    # ===== 第1层：用户交互 =====
    y1 = 10.6
    draw_layer_box(ax, left, y1 - layer_h, right - left, layer_h, '用户交互', '#1565C0', '#E3F2FD')
    items1 = ['用户输入问题', 'WebSocket连接建立']
    for text, xi in zip(items1, [4.0, 10.0]):
        draw_box(ax, xi, y1 - layer_h/2, 3.5, 0.9, text, '#90CAF9', 9)

    # ===== 第2层：认证授权 =====
    y2 = y1 - layer_h - gap
    draw_layer_box(ax, left, y2 - layer_h, right - left, layer_h, '认证授权', '#E65100', '#FFF3E0')
    items2 = ['JWT Token验证', '提取用户身份OrgTag权限验证']
    for text, xi in zip(items2, [4.0, 10.0]):
        draw_box(ax, xi, y2 - layer_h/2, 3.5, 0.9, text, '#FFCC80', 9)

    # ===== 第3层：混合检索 =====
    y3 = y2 - layer_h - gap
    draw_layer_box(ax, left, y3 - layer_h, right - left, layer_h, '混合检索', '#7B1FA2', '#F3E5F5')

    items3 = [
        ('Embedding生成查询向量', 'KNN向量相似度检索', 'BM25文本匹配'),
        ('Rescore重排序', '权限过滤私人/组织/公开', '返回Top5结果')
    ]
    for row_idx, row in enumerate(items3):
        y_pos = y3 - layer_h/2 - (row_idx - 0.5) * 0.65
        for col_idx, text in enumerate(row):
            draw_box(ax, x_centers[col_idx], y_pos, box_w, 0.55, text, '#CE93D8', 8)

    # ===== 第4层：RAG增强生成 =====
    y4 = y3 - layer_h - gap
    draw_layer_box(ax, left, y4 - layer_h, right - left, layer_h, 'RAG增强生成', '#2E7D32', '#E8F5E9')
    # 4个均匀分布的小模块，左右间距相等
    rag_box_w = 2.0
    rag_gap = 1.0
    total_rag_w = 4 * rag_box_w + 3 * rag_gap  # 8.0 + 3.0 = 11.0
    rag_start = left + (right - left - total_rag_w) / 2 + rag_box_w / 2  # 0.5 + (13-11)/2 + 1.0 = 2.5
    x_starts_rag = [rag_start + i * (rag_box_w + rag_gap) for i in range(4)]
    items4 = ['构建上下文', '构建Prompt', 'DeepSeek API', '流式响应']
    for col_idx, text in enumerate(items4):
        draw_box(ax, x_starts_rag[col_idx], y4 - layer_h/2, rag_box_w, 0.7, text, '#A5D6A7', 8)

    # ===== 第5层：会话管理 =====
    y5 = y4 - layer_h - gap
    draw_layer_box(ax, left, y5 - layer_h, right - left, layer_h, '会话管理', '#1565C0', '#E3F2FD')
    items5 = ['保存对话历史到Redis', '返回完成通知']
    for text, xi in zip(items5, [4.0, 10.0]):
        draw_box(ax, xi, y5 - layer_h/2, 3.5, 0.9, text, '#90CAF9', 9)

    # ===== 层间箭头 =====
    for y_top, y_bot in [(y1, y2), (y2, y3), (y3, y4), (y4, y5)]:
        draw_arrow(ax, 7, y_top - layer_h, 7, y_bot)

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '03_qa_interaction.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 03_qa_interaction.png')
    plt.close()

# ============ 04 混合检索流程 ============
def create_04_hybrid_search():
    """
    6个步骤垂直排列，每步占一个水平带
    """
    fig, ax = plt.subplots(1, 1, figsize=(12, 11))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 11)
    ax.axis('off')
    ax.set_title('GuaiSmart 混合检索流程（KNN + BM25 + Rescore）', fontsize=14, fontweight='bold', pad=15)

    steps = [
        (9.5, 'Step 1: 查询向量生成', '#E3F2FD', '#1565C0',
         'Embedding Client\ntext-embedding-v4\n生成768维向量'),
        (7.8, 'Step 2: KNN向量检索 (Top-150)', '#FFF3E0', '#E65100',
         'Elasticsearch\nKNN Query\nk=150, numCandidates=150'),
        (6.1, 'Step 3: BM25关键词过滤', '#F3E5F5', '#7B1FA2',
         'must: match\ntextContent\n关键词必须命中'),
        (4.4, 'Step 4: 权限过滤 (私人/组织/公开)', '#E8F5E9', '#2E7D32',
         'filter: bool\nshould: userId/public/orgTag\n三选一满足'),
        (2.7, 'Step 5: Rescore重排序 (综合评分)', '#FFEBEE', '#C62828',
         'queryWeight: 0.2\nrescoreWeight: 1.0\n综合评分 = 0.2*KNN + 1.0*BM25'),
        (1.0, 'Step 6: 返回Top-5结果封装', '#E3F2FD', '#1565C0',
         '[1] 技术文档.pdf\n[2] 使用手册.docx\n[3] FAQ.txt...'),
    ]

    step_h = 1.4

    for y_center, title, bg, fg, detail in steps:
        y_top = y_center + step_h/2 - 0.1
        y_bot = y_center - step_h/2 + 0.1

        # 步骤背景框 - 左半部分
        ax.add_patch(FancyBboxPatch((0.3, y_bot), 6.5, step_h - 0.1,
                                    boxstyle='round,pad=0.01,rounding_size=0.08',
                                    facecolor=bg, edgecolor=fg, linewidth=1.5))
        ax.text(3.5, y_center, title, ha='center', va='center',
                fontsize=11, fontweight='bold', color=fg)

        # 详情框 - 右半部分
        ax.add_patch(FancyBboxPatch((7, y_bot), 4.5, step_h - 0.1,
                                    boxstyle='round,pad=0.01,rounding_size=0.05',
                                    facecolor='#F5F5F5', edgecolor='#888', linewidth=1))
        ax.text(9.25, y_center, detail, ha='center', va='center',
                fontsize=8, color='#333', multialignment='center')

    # 步骤间箭头
    for i in range(len(steps) - 1):
        y_bot_step = steps[i][0] - step_h/2 + 0.1
        y_top_next = steps[i+1][0] + step_h/2 - 0.1
        draw_arrow(ax, 3.5, y_bot_step, 3.5, y_top_next - 0.05)

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '04_hybrid_search.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 04_hybrid_search.png')
    plt.close()

# ============ 05 组织标签层级结构 ============
def create_05_org_structure():
    """
    树形结构：ROOT → 部门 → 小组
    下部访问控制规则
    """
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('GuaiSmart 组织标签层级结构', fontsize=16, fontweight='bold', pad=15)

    # ===== 树形结构 =====
    node_w, node_h = 2.6, 0.85

    # ROOT - 居中
    root_x, root_y = 6, 9
    draw_box(ax, root_x, root_y, node_w, node_h, '根组织 (ROOT)\ntagId: ROOT', '#FFE0B2', 10)

    # Level 1 - 三个部门均匀分布
    dept_y = 7
    dept_data = [
        (2.5, '技术部\nDEPT_TECH', '#B3E5FC'),
        (6, '运营部\nDEPT_OPS', '#B3E5FC'),
        (9.5, '市场部\nDEPT_MKT', '#B3E5FC')
    ]

    for dx, text, color in dept_data:
        ax.annotate('', xy=(dx, dept_y + node_h/2), xytext=(root_x, root_y - node_h/2),
                    arrowprops=dict(arrowstyle='->', color='#555', lw=1.2))
        draw_box(ax, dx, dept_y, node_w, node_h, text, color, 9)

    # Level 2 - 各部门小组
    group_y = 4.5
    # 小组节点更小，确保间距不重叠
    gnode_w, gnode_h = 1.4, 0.7

    # 技术部小组 - 均匀分布，确保不重叠且有间距，且不与运营部重叠
    # 节点宽度1.4，需要0.3间距，中心距=1.7
    tech_groups = [(0.9, '后端组\nTECH_BE'), (2.6, '前端组\nTECH_FE'), (4.3, 'AI组\nTECH_AI')]
    for gx, text in tech_groups:
        ax.annotate('', xy=(gx, group_y + gnode_h/2), xytext=(2.5, dept_y - node_h/2),
                    arrowprops=dict(arrowstyle='->', color='#555', lw=1))
        draw_box(ax, gx, group_y, gnode_w, gnode_h, text, '#C8E6C9', 8)

    # 运营部箭头
    ax.annotate('', xy=(6, group_y + gnode_h/2), xytext=(6, dept_y - node_h/2),
                arrowprops=dict(arrowstyle='->', color='#555', lw=1))
    draw_box(ax, 6, group_y, gnode_w, gnode_h, '行政组\nOPS_A', '#C8E6C9', 8)

    # 市场部箭头
    ax.annotate('', xy=(9.5, group_y + gnode_h/2), xytext=(9.5, dept_y - node_h/2),
                arrowprops=dict(arrowstyle='->', color='#555', lw=1))
    draw_box(ax, 9.5, group_y, gnode_w, gnode_h, '策划组\nMKT_PLAN', '#C8E6C9', 8)

    # ===== 访问控制规则 =====
    rule_y_top = 3.5
    rule_h = 1.5
    ax.add_patch(FancyBboxPatch((0.4, rule_y_top - rule_h), 11.2, rule_h,
                                boxstyle='round,pad=0.02,rounding_size=0.1',
                                facecolor='#FFF3E0', edgecolor='#E65100', linewidth=2))
    ax.text(0.6, rule_y_top - 0.15, '访问控制规则', fontsize=10, fontweight='bold', color='#E65100')

    # 四个规则框与第二层小组节点高度一致
    rule_box_w, rule_box_h = 2.3, 0.7
    rules = [
        ('PRIVATE_*\n私人资源\nuserId匹配', '#FFCC80', 1.9),
        ('普通组织标签\n组织资源\norgTag匹配', '#FFCC80', 4.6),
        ('DEFAULT\n默认组织\n直接放行', '#FFCC80', 7.3),
        ('PUBLIC\n公开资源\n直接放行', '#FFCC80', 10.0),
    ]
    for text, color, rx in rules:
        draw_box(ax, rx, rule_y_top - rule_h/2 - 0.05, rule_box_w, rule_box_h, text, color, 7)

    
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '05_org_structure.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 05_org_structure.png')
    plt.close()

# ============ 06 WebSocket通信流程 ============
def create_06_websocket_flow():
    """
    垂直流程图：前端 → Handler → 服务 → 响应
    """
    fig, ax = plt.subplots(1, 1, figsize=(12, 9))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.axis('off')
    ax.set_title('GuaiSmart WebSocket 实时通信流程', fontsize=16, fontweight='bold', pad=15)

    step_h = 1.2
    step_gap = 0.5
    start_y = 8.0
    box_w = 4.0

    steps = [
        (start_y, '#1565C0', '#E3F2FD', '步骤1: 前端连接',
         'Vue 3 WebSocket Client\n建立连接 → 身份认证'),
        (start_y - step_h - step_gap, '#E65100', '#FFF3E0', '步骤2: Token验证',
         'ChatWebSocketHandler\nJWT Token 解析验证'),
        (start_y - 2*(step_h + step_gap), '#7B1FA2', '#F3E5F5', '步骤3: 消息处理',
         'ChatHandler 接收消息\n构建检索上下文'),
        (start_y - 3*(step_h + step_gap), '#2E7D32', '#E8F5E9', '步骤4: RAG检索',
         'ES向量检索 + BM25\n混合检索 Top5'),
        (start_y - 4*(step_h + step_gap), '#0D47A1', '#E3F2FD', '步骤5: LLM生成',
         'DeepSeek API\n流式生成响应'),
        (start_y - 5*(step_h + step_gap), '#6A1B9A', '#F3E5F5', '步骤6: 流式响应',
         'WebSocket推送前端\n显示AI回复'),
    ]

    x_center = 6

    for y_center, bg, fg, title, detail in steps:
        y_top = y_center + step_h/2
        y_bot = y_center - step_h/2

        # 标题框 - 左半部分
        ax.add_patch(FancyBboxPatch((0.5, y_bot), 3.5, step_h,
                                    boxstyle='round,pad=0.02,rounding_size=0.1',
                                    facecolor=bg, edgecolor=fg, linewidth=1.5))
        ax.text(2.25, y_center, title, ha='center', va='center',
                fontsize=10, fontweight='bold', color='white')

        # 详情框 - 右半部分
        ax.add_patch(FancyBboxPatch((4.2, y_bot), 7.3, step_h,
                                    boxstyle='round,pad=0.02,rounding_size=0.08',
                                    facecolor='#F5F5F5', edgecolor='#888', linewidth=1))
        ax.text(7.85, y_center, detail, ha='center', va='center',
                fontsize=9, color='#333', multialignment='center')

    # 步骤间箭头
    for i in range(len(steps) - 1):
        y_bot_step = steps[i][0] - step_h/2
        y_top_next = steps[i+1][0] + step_h/2
        draw_arrow(ax, x_center, y_bot_step, x_center, y_top_next + 0.1)

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '06_websocket_flow.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 06_websocket_flow.png')
    plt.close()

# ============ 07 项目结构图 ============
def create_07_project_structure():
    """
    左右两栏：后端 | 前端
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('GuaiSmart 项目结构图', fontsize=16, fontweight='bold', pad=15)

    # ===== 后端区域 =====
    ax.add_patch(FancyBboxPatch((0.2, 0.5), 6.3, 9, boxstyle='round,pad=0.02,rounding_size=0.1',
                                facecolor='#FFF8E7', edgecolor='#E67E22', linewidth=2))
    ax.text(0.4, 9.2, '后端 (Spring Boot)', fontsize=12, fontweight='bold', color='#E67E22')

    backend = [
        (0.8, 8.3, 'client/', '外部API客户端'),
        (0.8, 7.5, 'config/', 'Security, JWT, Kafka, Redis'),
        (0.8, 6.7, 'consumer/', 'Kafka消费者'),
        (0.8, 5.9, 'controller/', 'REST API端点'),
        (0.8, 5.1, 'entity/', 'JPA实体'),
        (0.8, 4.3, 'service/', '业务逻辑'),
        (0.8, 3.5, 'repository/', '数据访问'),
        (0.8, 2.7, 'handler/', 'WebSocket处理器'),
        (0.8, 1.9, 'model/', '领域模型'),
        (0.8, 1.1, 'utils/', '工具类'),
    ]
    for x, y, name, desc in backend:
        ax.text(x, y, name, fontsize=9, fontweight='bold', color='#E67E22')
        ax.text(x + 1.3, y, desc, fontsize=8, color='#555')

    # ===== 前端区域 =====
    ax.add_patch(FancyBboxPatch((6.7, 0.5), 7, 9, boxstyle='round,pad=0.02,rounding_size=0.1',
                                facecolor='#E8F4FD', edgecolor='#4A90D9', linewidth=2))
    ax.text(6.9, 9.2, '前端 (Vue 3 + TypeScript)', fontsize=12, fontweight='bold', color='#4A90D9')

    frontend = [
        (7.2, 8.3, 'packages/', '@sa/axios, @sa/hooks, @sa/utils'),
        (7.2, 7.5, 'views/', '页面组件 (chat, kb, org-tag)'),
        (7.2, 6.7, 'store/', 'Pinia状态 (auth, chat, route)'),
        (7.2, 5.9, 'router/', 'Vue Router + elegant-router'),
        (7.2, 5.1, 'service/', 'API集成 (api/, request/)'),
        (7.2, 4.3, 'components/', 'Vue组件 (common, custom)'),
        (7.2, 3.5, 'layouts/', '页面布局'),
        (7.2, 2.7, 'hooks/', 'Vue composables'),
        (7.2, 1.9, 'locales/', 'i18n国际化'),
        (7.2, 1.1, 'plugins/', 'Vue插件'),
        (10.8, 8.3, 'assets/', '静态资源'),
        (10.8, 7.5, 'styles/', '全局样式'),
        (10.8, 6.7, 'theme/', '主题配置'),
        (10.8, 5.9, 'typings/', 'TypeScript类型'),
        (10.8, 5.1, 'utils/', '工具函数'),
        (10.8, 4.3, 'enum/', '枚举定义'),
        (10.8, 3.5, 'constants/', '常量定义'),
    ]
    for x, y, name, desc in frontend:
        ax.text(x, y, name, fontsize=8, fontweight='bold', color='#4A90D9')
        ax.text(x + 1.2, y, desc, fontsize=7, color='#555')

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / '07_project_structure.png', dpi=150, bbox_inches='tight', facecolor='white')
    print('Saved: 07_project_structure.png')
    plt.close()

# ============ 主函数 ============
if __name__ == '__main__':
    print('Generating GuaiSmart diagrams...')
    create_01_system_architecture()
    create_02_document_upload()
    create_03_qa_interaction()
    create_04_hybrid_search()
    create_05_org_structure()
    create_06_websocket_flow()
    create_07_project_structure()
    print('All diagrams generated!')
