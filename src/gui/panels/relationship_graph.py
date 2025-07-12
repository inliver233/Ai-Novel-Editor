"""
关系网络可视化组件
提供交互式的关系图展示，支持力导向布局、节点拖拽、缩放等功能
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QSlider, QCheckBox, QGroupBox,
    QGridLayout, QToolBar, QSplitter, QTextEdit,
    QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, 
    QMouseEvent, QWheelEvent, QPainterPath, QPolygonF,
    QTransform, QCursor, QAction
)
import math
import random
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class GraphNode:
    """图节点数据"""
    id: str
    label: str
    x: float
    y: float
    vx: float = 0.0  # 速度x
    vy: float = 0.0  # 速度y
    color: QColor = None
    size: float = 30.0
    fixed: bool = False
    entry_type: str = ""
    
@dataclass 
class GraphEdge:
    """图边数据"""
    source: str
    target: str
    label: str = ""
    weight: float = 1.0
    color: QColor = None
    
class ForceDirectedGraph(QWidget):
    """力导向图组件"""
    
    # 信号
    node_clicked = pyqtSignal(str)  # 节点点击信号
    node_double_clicked = pyqtSignal(str)  # 节点双击信号
    
    def __init__(self):
        super().__init__()
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.selected_node: Optional[str] = None
        self.dragging_node: Optional[str] = None
        self.hover_node: Optional[str] = None
        
        # 视图参数
        self.scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.last_mouse_pos = None
        
        # 力导向参数
        self.force_strength = 30.0
        self.link_distance = 100.0
        self.charge_strength = -300.0
        self.damping = 0.9
        
        # 动画
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_physics)
        self.animation_running = False
        
        # 样式
        self.node_colors = {
            'CHARACTER': QColor(52, 152, 219),   # 蓝色
            'LOCATION': QColor(46, 204, 113),    # 绿色
            'OBJECT': QColor(241, 196, 15),      # 黄色
            'LORE': QColor(155, 89, 182),        # 紫色
            'SUBPLOT': QColor(231, 76, 60),      # 红色
            'OTHER': QColor(149, 165, 166)       # 灰色
        }
        
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        
    def set_data(self, nodes: List[Dict], edges: List[Dict]):
        """设置图数据"""
        self.nodes.clear()
        self.edges.clear()
        
        # 创建节点
        for node_data in nodes:
            node = GraphNode(
                id=node_data['id'],
                label=node_data.get('label', node_data['id']),
                x=random.uniform(-200, 200),
                y=random.uniform(-200, 200),
                entry_type=node_data.get('type', 'OTHER')
            )
            node.color = self.node_colors.get(node.entry_type, self.node_colors['OTHER'])
            node.size = 20 + min(node_data.get('weight', 1) * 5, 30)
            self.nodes[node.id] = node
            
        # 创建边
        for edge_data in edges:
            if edge_data['source'] in self.nodes and edge_data['target'] in self.nodes:
                edge = GraphEdge(
                    source=edge_data['source'],
                    target=edge_data['target'],
                    label=edge_data.get('label', ''),
                    weight=edge_data.get('weight', 1.0)
                )
                self.edges.append(edge)
                
        # 启动物理模拟
        self.start_animation()
        
    def start_animation(self):
        """启动动画"""
        if not self.animation_running:
            self.animation_running = True
            self.animation_timer.start(16)  # 约60fps
            
    def stop_animation(self):
        """停止动画"""
        self.animation_running = False
        self.animation_timer.stop()
        
    def _update_physics(self):
        """更新物理模拟"""
        if not self.nodes:
            return
            
        # 应用库仑斥力
        for n1_id, n1 in self.nodes.items():
            if n1.fixed:
                continue
                
            fx = 0
            fy = 0
            
            # 计算斥力
            for n2_id, n2 in self.nodes.items():
                if n1_id == n2_id:
                    continue
                    
                dx = n1.x - n2.x
                dy = n1.y - n2.y
                dist_sq = dx * dx + dy * dy
                
                if dist_sq > 0:
                    dist = math.sqrt(dist_sq)
                    force = self.charge_strength / (dist_sq + 1)
                    fx += force * dx / dist
                    fy += force * dy / dist
                    
            n1.vx += fx
            n1.vy += fy
            
        # 应用弹簧力
        for edge in self.edges:
            source = self.nodes.get(edge.source)
            target = self.nodes.get(edge.target)
            
            if not source or not target:
                continue
                
            dx = target.x - source.x
            dy = target.y - source.y
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist > 0:
                force = (dist - self.link_distance) * self.force_strength / 1000
                fx = force * dx / dist
                fy = force * dy / dist
                
                if not source.fixed:
                    source.vx += fx
                    source.vy += fy
                if not target.fixed:
                    target.vx -= fx
                    target.vy -= fy
                    
        # 应用中心引力
        center_x = self.width() / 2 / self.scale - self.pan_x
        center_y = self.height() / 2 / self.scale - self.pan_y
        
        for node in self.nodes.values():
            if not node.fixed:
                dx = center_x - node.x
                dy = center_y - node.y
                node.vx += dx * 0.01
                node.vy += dy * 0.01
                
        # 更新位置
        max_velocity = 5.0
        for node in self.nodes.values():
            if not node.fixed:
                # 应用阻尼
                node.vx *= self.damping
                node.vy *= self.damping
                
                # 限制最大速度
                velocity = math.sqrt(node.vx * node.vx + node.vy * node.vy)
                if velocity > max_velocity:
                    node.vx = node.vx / velocity * max_velocity
                    node.vy = node.vy / velocity * max_velocity
                    
                # 更新位置
                node.x += node.vx
                node.y += node.vy
                
        # 检查是否稳定
        total_velocity = sum(math.sqrt(n.vx * n.vx + n.vy * n.vy) 
                           for n in self.nodes.values() if not n.fixed)
        
        if total_velocity < 0.1:
            self.stop_animation()
            
        self.update()
        
    def paintEvent(self, event):
        """绘制图形"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(self.rect(), QColor(250, 250, 250))
        
        # 应用变换
        transform = QTransform()
        transform.translate(self.width() / 2, self.height() / 2)
        transform.scale(self.scale, self.scale)
        transform.translate(self.pan_x, self.pan_y)
        painter.setTransform(transform)
        
        # 绘制边
        for edge in self.edges:
            source = self.nodes.get(edge.source)
            target = self.nodes.get(edge.target)
            
            if not source or not target:
                continue
                
            # 边的颜色和宽度
            color = edge.color if edge.color else QColor(200, 200, 200)
            width = 1 + edge.weight
            
            painter.setPen(QPen(color, width))
            painter.drawLine(QPointF(source.x, source.y), 
                           QPointF(target.x, target.y))
                           
            # 绘制箭头
            if edge.label:
                self._draw_arrow(painter, source, target)
                
            # 绘制标签
            if edge.label:
                mid_x = (source.x + target.x) / 2
                mid_y = (source.y + target.y) / 2
                painter.setPen(QPen(Qt.GlobalColor.black))
                painter.setFont(QFont("Arial", 8))
                painter.drawText(QPointF(mid_x, mid_y), edge.label)
                
        # 绘制节点
        for node_id, node in self.nodes.items():
            # 节点颜色
            if node_id == self.selected_node:
                color = node.color.darker(120)
            elif node_id == self.hover_node:
                color = node.color.lighter(120)
            else:
                color = node.color
                
            # 绘制节点圆圈
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(QPointF(node.x, node.y), node.size, node.size)
            
            # 绘制标签
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            # 计算文本边界
            text_rect = painter.fontMetrics().boundingRect(node.label)
            text_rect.moveCenter(QPointF(node.x, node.y + node.size + 15).toPoint())
            
            # 绘制文本背景
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(text_rect.adjusted(-2, -2, 2, 2), 3, 3)
            
            # 绘制文本
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, node.label)
            
    def _draw_arrow(self, painter: QPainter, source: GraphNode, target: GraphNode):
        """绘制箭头"""
        # 计算箭头位置
        dx = target.x - source.x
        dy = target.y - source.y
        length = math.sqrt(dx * dx + dy * dy)
        
        if length == 0:
            return
            
        # 标准化方向
        dx /= length
        dy /= length
        
        # 箭头终点（考虑节点半径）
        end_x = target.x - dx * target.size
        end_y = target.y - dy * target.size
        
        # 箭头大小
        arrow_length = 10
        arrow_angle = math.pi / 6
        
        # 计算箭头两个点
        angle = math.atan2(dy, dx)
        x1 = end_x - arrow_length * math.cos(angle - arrow_angle)
        y1 = end_y - arrow_length * math.sin(angle - arrow_angle)
        x2 = end_x - arrow_length * math.cos(angle + arrow_angle)
        y2 = end_y - arrow_length * math.sin(angle + arrow_angle)
        
        # 绘制箭头
        arrow = QPolygonF([
            QPointF(end_x, end_y),
            QPointF(x1, y1),
            QPointF(x2, y2)
        ])
        
        painter.setBrush(QBrush(QColor(150, 150, 150)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow)
        
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 转换坐标
            pos = self._screen_to_world(event.position())
            
            # 查找点击的节点
            clicked_node = self._get_node_at(pos)
            
            if clicked_node:
                self.selected_node = clicked_node
                self.dragging_node = clicked_node
                self.nodes[clicked_node].fixed = True
                self.node_clicked.emit(clicked_node)
            else:
                self.selected_node = None
                
            self.last_mouse_pos = event.position()
            self.update()
            
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.last_mouse_pos = event.position()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if self.dragging_node:
            self.nodes[self.dragging_node].fixed = False
            self.dragging_node = None
            self.start_animation()
            
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.last_mouse_pos = None
        
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """鼠标双击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._screen_to_world(event.position())
            clicked_node = self._get_node_at(pos)
            
            if clicked_node:
                self.node_double_clicked.emit(clicked_node)
                
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        pos = self._screen_to_world(event.position())
        
        # 更新悬停节点
        old_hover = self.hover_node
        self.hover_node = self._get_node_at(pos)
        
        if old_hover != self.hover_node:
            self.update()
            
        # 拖拽节点
        if self.dragging_node and event.buttons() & Qt.MouseButton.LeftButton:
            node = self.nodes[self.dragging_node]
            node.x = pos.x()
            node.y = pos.y()
            node.vx = 0
            node.vy = 0
            self.update()
            
        # 平移视图
        elif event.buttons() & Qt.MouseButton.MiddleButton and self.last_mouse_pos:
            delta = event.position() - self.last_mouse_pos
            self.pan_x += delta.x() / self.scale
            self.pan_y += delta.y() / self.scale
            self.last_mouse_pos = event.position()
            self.update()
            
    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮事件"""
        # 缩放
        scale_factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale *= scale_factor
        self.scale = max(0.1, min(5.0, self.scale))
        self.update()
        
    def _screen_to_world(self, pos: QPointF) -> QPointF:
        """屏幕坐标转世界坐标"""
        x = (pos.x() - self.width() / 2) / self.scale - self.pan_x
        y = (pos.y() - self.height() / 2) / self.scale - self.pan_y
        return QPointF(x, y)
        
    def _get_node_at(self, pos: QPointF) -> Optional[str]:
        """获取指定位置的节点"""
        for node_id, node in self.nodes.items():
            dx = pos.x() - node.x
            dy = pos.y() - node.y
            if dx * dx + dy * dy <= node.size * node.size:
                return node_id
        return None
        
    def reset_view(self):
        """重置视图"""
        self.scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update()
        
    def fit_to_view(self):
        """适应视图"""
        if not self.nodes:
            return
            
        # 计算边界
        min_x = min(n.x - n.size for n in self.nodes.values())
        max_x = max(n.x + n.size for n in self.nodes.values())
        min_y = min(n.y - n.size for n in self.nodes.values())
        max_y = max(n.y + n.size for n in self.nodes.values())
        
        width = max_x - min_x
        height = max_y - min_y
        
        if width > 0 and height > 0:
            # 计算缩放
            scale_x = (self.width() - 100) / width
            scale_y = (self.height() - 100) / height
            self.scale = min(scale_x, scale_y, 2.0)
            
            # 计算平移
            self.pan_x = -(min_x + max_x) / 2
            self.pan_y = -(min_y + max_y) / 2
            
            self.update()


class RelationshipGraphWidget(QWidget):
    """关系图可视化面板"""
    
    # 信号
    entry_selected = pyqtSignal(str)
    
    def __init__(self, codex_manager):
        super().__init__()
        self.codex_manager = codex_manager
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 先创建图形视图
        self.graph = ForceDirectedGraph()
        self.graph.node_clicked.connect(self._on_node_clicked)
        self.graph.node_double_clicked.connect(self._on_node_double_clicked)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 主布局使用分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧控制面板
        control_panel = self._create_control_panel()
        splitter.addWidget(control_panel)
        
        # 右侧图形视图
        splitter.addWidget(self.graph)
        
        # 设置分割比例
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # 初始加载
        self.refresh_graph()
        
    def _create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()
        
        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_graph)
        toolbar.addAction(refresh_action)
        
        # 重置视图
        reset_action = QAction("重置视图", self)
        reset_action.triggered.connect(self.graph.reset_view)
        toolbar.addAction(reset_action)
        
        # 适应视图
        fit_action = QAction("适应视图", self)
        fit_action.triggered.connect(self.graph.fit_to_view)
        toolbar.addAction(fit_action)
        
        toolbar.addSeparator()
        
        # 播放/暂停动画
        self.play_pause_action = QAction("暂停", self)
        self.play_pause_action.triggered.connect(self._toggle_animation)
        toolbar.addAction(self.play_pause_action)
        
        # 导出
        export_action = QAction("导出图片", self)
        export_action.triggered.connect(self._export_image)
        toolbar.addAction(export_action)
        
        return toolbar
        
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 显示选项
        display_group = QGroupBox("显示选项")
        display_layout = QVBoxLayout(display_group)
        
        # 关系类型筛选
        display_layout.addWidget(QLabel("关系类型:"))
        self.relation_types = QComboBox()
        self.relation_types.addItems(["全部", "师徒", "亲属", "朋友", "敌对", "组织", "其他"])
        self.relation_types.currentIndexChanged.connect(self.refresh_graph)
        display_layout.addWidget(self.relation_types)
        
        # 节点类型筛选
        display_layout.addWidget(QLabel("节点类型:"))
        self.node_types = QComboBox()
        self.node_types.addItems(["全部", "角色", "地点", "物品", "背景", "支线", "其他"])
        self.node_types.currentIndexChanged.connect(self.refresh_graph)
        display_layout.addWidget(self.node_types)
        
        # 显示设置
        self.show_labels = QCheckBox("显示标签")
        self.show_labels.setChecked(True)
        self.show_labels.toggled.connect(self.refresh_graph)
        display_layout.addWidget(self.show_labels)
        
        self.show_weights = QCheckBox("显示权重")
        self.show_weights.setChecked(False)
        self.show_weights.toggled.connect(self.refresh_graph)
        display_layout.addWidget(self.show_weights)
        
        layout.addWidget(display_group)
        
        # 物理参数
        physics_group = QGroupBox("物理参数")
        physics_layout = QGridLayout(physics_group)
        
        # 斥力强度
        physics_layout.addWidget(QLabel("斥力:"), 0, 0)
        self.charge_slider = QSlider(Qt.Orientation.Horizontal)
        self.charge_slider.setRange(0, 100)
        self.charge_slider.setValue(50)
        self.charge_slider.valueChanged.connect(self._update_physics_params)
        physics_layout.addWidget(self.charge_slider, 0, 1)
        
        # 连接距离
        physics_layout.addWidget(QLabel("距离:"), 1, 0)
        self.distance_slider = QSlider(Qt.Orientation.Horizontal)
        self.distance_slider.setRange(50, 200)
        self.distance_slider.setValue(100)
        self.distance_slider.valueChanged.connect(self._update_physics_params)
        physics_layout.addWidget(self.distance_slider, 1, 1)
        
        # 阻尼
        physics_layout.addWidget(QLabel("阻尼:"), 2, 0)
        self.damping_slider = QSlider(Qt.Orientation.Horizontal)
        self.damping_slider.setRange(0, 100)
        self.damping_slider.setValue(90)
        self.damping_slider.valueChanged.connect(self._update_physics_params)
        physics_layout.addWidget(self.damping_slider, 2, 1)
        
        layout.addWidget(physics_group)
        
        # 节点信息
        info_group = QGroupBox("节点信息")
        info_layout = QVBoxLayout(info_group)
        
        self.node_info = QTextEdit()
        self.node_info.setReadOnly(True)
        self.node_info.setMaximumHeight(200)
        info_layout.addWidget(self.node_info)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        return panel
        
    def refresh_graph(self):
        """刷新图形"""
        try:
            # 获取筛选条件
            relation_filter = self.relation_types.currentText()
            node_filter = self.node_types.currentText()
            
            # 构建节点数据
            nodes = []
            node_ids = set()
            
            # 获取关系数据
            relationships = []
            for entry in self.codex_manager._entries.values():
                # 节点类型过滤
                if node_filter != "全部":
                    type_map = {
                        "角色": "CHARACTER",
                        "地点": "LOCATION", 
                        "物品": "OBJECT",
                        "背景": "LORE",
                        "支线": "SUBPLOT",
                        "其他": "OTHER"
                    }
                    if entry.entry_type.value != type_map.get(node_filter, "OTHER"):
                        continue
                        
                # 收集关系
                for rel in entry.relationships:
                    if relation_filter != "全部" and rel.get('type', '') != relation_filter:
                        continue
                        
                    target_id = rel.get('target_id', '')
                    if target_id and target_id in self.codex_manager._entries:
                        relationships.append({
                            'source': entry.id,
                            'target': target_id,
                            'type': rel.get('type', ''),
                            'description': rel.get('description', '')
                        })
                        node_ids.add(entry.id)
                        node_ids.add(target_id)
                        
            # 构建节点列表
            for node_id in node_ids:
                entry = self.codex_manager._entries.get(node_id)
                if entry:
                    # 计算节点权重（基于关系数量）
                    weight = sum(1 for r in relationships 
                               if r['source'] == node_id or r['target'] == node_id)
                    
                    nodes.append({
                        'id': node_id,
                        'label': entry.title,
                        'type': entry.entry_type.value,
                        'weight': weight
                    })
                    
            # 构建边列表
            edges = []
            for rel in relationships:
                label = rel['type'] if self.show_labels.isChecked() else ""
                if self.show_weights.isChecked() and rel['description']:
                    label += f" ({rel['description']})"
                    
                edges.append({
                    'source': rel['source'],
                    'target': rel['target'],
                    'label': label,
                    'weight': 1.0
                })
                
            # 更新图形
            self.graph.set_data(nodes, edges)
            
            # 更新信息
            self._update_graph_info(len(nodes), len(edges))
            
        except Exception as e:
            logger.error(f"Error refreshing graph: {e}")
            
    def _update_physics_params(self):
        """更新物理参数"""
        self.graph.charge_strength = -self.charge_slider.value() * 10
        self.graph.link_distance = self.distance_slider.value()
        self.graph.damping = self.damping_slider.value() / 100.0
        
        if self.graph.animation_running:
            self.graph.start_animation()
            
    def _toggle_animation(self):
        """切换动画状态"""
        if self.graph.animation_running:
            self.graph.stop_animation()
            self.play_pause_action.setText("播放")
        else:
            self.graph.start_animation()
            self.play_pause_action.setText("暂停")
            
    def _on_node_clicked(self, node_id: str):
        """处理节点点击"""
        entry = self.codex_manager.get_entry(node_id)
        if entry:
            # 更新节点信息
            info_text = f"<b>{entry.title}</b><br>"
            info_text += f"类型: {entry.entry_type.value}<br>"
            if entry.description:
                info_text += f"描述: {entry.description}<br>"
            info_text += f"<br>关系数: {len(entry.relationships)}"
            
            self.node_info.setHtml(info_text)
            
    def _on_node_double_clicked(self, node_id: str):
        """处理节点双击"""
        self.entry_selected.emit(node_id)
        
    def _update_graph_info(self, node_count: int, edge_count: int):
        """更新图形信息"""
        info_text = f"节点数: {node_count}<br>边数: {edge_count}"
        self.node_info.setHtml(info_text)
        
    def _export_image(self):
        """导出图片"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            from PyQt6.QtGui import QPixmap
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出关系图", "", "PNG图片 (*.png);;JPEG图片 (*.jpg)"
            )
            
            if file_path:
                # 创建图片
                pixmap = QPixmap(self.graph.size())
                pixmap.fill(Qt.GlobalColor.white)
                
                # 绘制到图片
                painter = QPainter(pixmap)
                self.graph.render(painter)
                painter.end()
                
                # 保存
                pixmap.save(file_path)
                
                QMessageBox.information(self, "导出成功", f"关系图已导出到:\n{file_path}")
                
        except Exception as e:
            logger.error(f"Error exporting image: {e}")
            QMessageBox.critical(self, "导出失败", f"导出图片时出错:\n{str(e)}")