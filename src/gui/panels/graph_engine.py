"""
图形引擎核心组件
实现职责分离的现代化架构
"""

import math
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Protocol, Callable
from enum import Enum

from PyQt6.QtCore import QPointF, QRectF, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class LayoutAlgorithm(Enum):
    """布局算法类型"""
    FORCE_DIRECTED = "force_directed"
    SPRING_EMBEDDER = "spring_embedder"
    CIRCULAR = "circular"
    HIERARCHICAL = "hierarchical"
    RANDOM = "random"


@dataclass
class GraphConfig:
    """图形配置类 - 集中管理所有配置参数"""
    # 物理参数
    force_strength: float = 30.0
    link_distance: float = 100.0
    charge_strength: float = -300.0
    damping: float = 0.9
    center_force: float = 0.1
    
    # 视觉参数
    node_size_range: Tuple[float, float] = (20.0, 50.0)
    edge_width_range: Tuple[float, float] = (1.0, 5.0)
    
    # 性能参数
    max_fps: int = 60
    simulation_threshold: float = 0.1
    max_nodes_for_realtime: int = 100
    
    # UI参数
    enable_animations: bool = True
    show_labels: bool = True
    anti_aliasing: bool = True
    
    # 主题参数
    background_color: QColor = field(default_factory=lambda: QColor("#f8f9fa"))
    node_colors: Dict[str, QColor] = field(default_factory=lambda: {
        'CHARACTER': QColor("#3498DB"),
        'LOCATION': QColor("#2ECC71"),
        'OBJECT': QColor("#F39C12"),
        'LORE': QColor("#9B59B6"),
        'SUBPLOT': QColor("#E74C3C"),
        'OTHER': QColor("#95A5A6")
    })
    edge_color: QColor = field(default_factory=lambda: QColor("#BDC3C7"))
    text_color: QColor = field(default_factory=lambda: QColor("#2C3E50"))
    
    def __post_init__(self):
        """配置验证"""
        if self.force_strength <= 0:
            raise ValueError("Force strength must be positive")
        if self.damping < 0 or self.damping > 1:
            raise ValueError("Damping must be between 0 and 1")


@dataclass
class GraphNode:
    """优化的图节点类"""
    id: str
    label: str
    node_type: str = "OTHER"
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    size: float = 30.0
    fixed: bool = False
    selected: bool = False
    highlighted: bool = False
    weight: float = 1.0
    metadata: Dict = field(default_factory=dict)
    
    def distance_to(self, other: 'GraphNode') -> float:
        """计算到另一个节点的距离"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)
    
    def apply_force(self, fx: float, fy: float):
        """应用力到节点"""
        if not self.fixed:
            self.vx += fx
            self.vy += fy
    
    def update_position(self, damping: float = 0.9):
        """更新节点位置"""
        if not self.fixed:
            self.x += self.vx
            self.y += self.vy
            self.vx *= damping
            self.vy *= damping
    
    def get_kinetic_energy(self) -> float:
        """获取动能"""
        return 0.5 * (self.vx ** 2 + self.vy ** 2)


@dataclass
class GraphEdge:
    """优化的图边类"""
    source: str
    target: str
    label: str = ""
    weight: float = 1.0
    edge_type: str = "default"
    bidirectional: bool = False
    metadata: Dict = field(default_factory=dict)
    
    def get_source_node(self, nodes: Dict[str, GraphNode]) -> Optional[GraphNode]:
        """获取源节点"""
        return nodes.get(self.source)
    
    def get_target_node(self, nodes: Dict[str, GraphNode]) -> Optional[GraphNode]:
        """获取目标节点"""
        return nodes.get(self.target)


class LayoutEngine(ABC):
    """布局算法抽象基类"""
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.iteration_count = 0
    
    @abstractmethod
    def calculate_forces(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]) -> bool:
        """
        计算力并更新节点位置
        
        Returns:
            bool: 是否达到稳定状态
        """
        pass
    
    @abstractmethod
    def initialize_positions(self, nodes: Dict[str, GraphNode]):
        """初始化节点位置"""
        pass


class ForceDirectedEngine(LayoutEngine):
    """力导向布局引擎 - 优化版本"""
    
    def __init__(self, config: GraphConfig):
        super().__init__(config)
        self.quadtree = None  # 未来可以添加四叉树优化
    
    def initialize_positions(self, nodes: Dict[str, GraphNode]):
        """随机初始化节点位置"""
        import random
        radius = 100
        
        for i, node in enumerate(nodes.values()):
            if not node.fixed:
                angle = 2 * math.pi * i / len(nodes)
                node.x = radius * math.cos(angle)
                node.y = radius * math.sin(angle)
                node.vx = 0
                node.vy = 0
    
    def calculate_forces(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]) -> bool:
        """优化的力计算"""
        self.iteration_count += 1
        
        # 重置力
        for node in nodes.values():
            if not node.fixed:
                node.vx = node.vy = 0
        
        # 1. 计算斥力（库仑力）
        self._calculate_repulsive_forces(nodes)
        
        # 2. 计算引力（弹簧力）
        self._calculate_attractive_forces(nodes, edges)
        
        # 3. 计算中心引力
        self._calculate_center_force(nodes)
        
        # 4. 更新位置
        total_energy = 0
        for node in nodes.values():
            if not node.fixed:
                # 限制最大速度防止震荡
                max_velocity = 10.0
                velocity = math.sqrt(node.vx ** 2 + node.vy ** 2)
                if velocity > max_velocity:
                    node.vx = (node.vx / velocity) * max_velocity
                    node.vy = (node.vy / velocity) * max_velocity
                
                node.update_position(self.config.damping)
                total_energy += node.get_kinetic_energy()
        
        # 检查是否达到稳定状态
        avg_energy = total_energy / len(nodes) if nodes else 0
        return avg_energy < self.config.simulation_threshold
    
    def _calculate_repulsive_forces(self, nodes: Dict[str, GraphNode]):
        """计算节点间斥力"""
        node_list = list(nodes.values())
        
        for i in range(len(node_list)):
            node_a = node_list[i]
            if node_a.fixed:
                continue
            
            for j in range(i + 1, len(node_list)):
                node_b = node_list[j]
                
                dx = node_a.x - node_b.x
                dy = node_a.y - node_b.y
                distance = math.sqrt(dx ** 2 + dy ** 2)
                
                if distance > 0:
                    # 库仑定律：F = k * q1 * q2 / r²
                    force = self.config.charge_strength / (distance ** 2)
                    fx = (dx / distance) * force
                    fy = (dy / distance) * force
                    
                    node_a.apply_force(fx, fy)
                    if not node_b.fixed:
                        node_b.apply_force(-fx, -fy)
    
    def _calculate_attractive_forces(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]):
        """计算边的引力"""
        for edge in edges:
            source = nodes.get(edge.source)
            target = nodes.get(edge.target)
            
            if not source or not target:
                continue
            
            dx = target.x - source.x
            dy = target.y - source.y
            distance = math.sqrt(dx ** 2 + dy ** 2)
            
            if distance > 0:
                # 胡克定律：F = k * (x - x0)
                force = self.config.force_strength * (distance - self.config.link_distance) * edge.weight
                fx = (dx / distance) * force
                fy = (dy / distance) * force
                
                if not source.fixed:
                    source.apply_force(fx, fy)
                if not target.fixed:
                    target.apply_force(-fx, -fy)
    
    def _calculate_center_force(self, nodes: Dict[str, GraphNode]):
        """计算向中心的引力"""
        for node in nodes.values():
            if not node.fixed:
                fx = -node.x * self.config.center_force
                fy = -node.y * self.config.center_force
                node.apply_force(fx, fy)


class CircularLayoutEngine(LayoutEngine):
    """圆形布局引擎"""
    
    def initialize_positions(self, nodes: Dict[str, GraphNode]):
        """圆形布局初始化"""
        if not nodes:
            return
        
        radius = max(100, len(nodes) * 15)  # 根据节点数量调整半径
        angle_step = 2 * math.pi / len(nodes)
        
        for i, node in enumerate(nodes.values()):
            angle = i * angle_step
            node.x = radius * math.cos(angle)
            node.y = radius * math.sin(angle)
            node.vx = node.vy = 0
            node.fixed = True  # 圆形布局固定位置
    
    def calculate_forces(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]) -> bool:
        """圆形布局不需要力计算"""
        return True  # 立即达到稳定状态


class GraphPhysicsEngine(QObject):
    """图形物理引擎 - 统一管理布局算法"""
    
    # 信号定义
    layoutChanged = pyqtSignal()
    stabilityChanged = pyqtSignal(bool)  # 稳定性变化
    
    def __init__(self, config: GraphConfig):
        super().__init__()
        self.config = config
        self.current_algorithm = LayoutAlgorithm.FORCE_DIRECTED
        self.engines = {
            LayoutAlgorithm.FORCE_DIRECTED: ForceDirectedEngine(config),
            LayoutAlgorithm.CIRCULAR: CircularLayoutEngine(config)
        }
        self.is_stable = False
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_step)
        
    def set_algorithm(self, algorithm: LayoutAlgorithm):
        """设置布局算法"""
        if algorithm in self.engines:
            self.current_algorithm = algorithm
            logger.info(f"Layout algorithm changed to: {algorithm.value}")
    
    def start_simulation(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]):
        """开始模拟"""
        if not nodes:
            return
        
        self.nodes = nodes
        self.edges = edges
        
        # 初始化位置
        engine = self.engines[self.current_algorithm]
        engine.initialize_positions(nodes)
        
        # 启动定时器
        interval = 1000 // self.config.max_fps
        self.timer.start(interval)
        
        self.is_stable = False
        self.stabilityChanged.emit(False)
        logger.info(f"Physics simulation started with {len(nodes)} nodes")
    
    def stop_simulation(self):
        """停止模拟"""
        self.timer.stop()
        
    def _update_step(self):
        """执行一步物理更新"""
        engine = self.engines[self.current_algorithm]
        
        try:
            is_stable = engine.calculate_forces(self.nodes, self.edges)
            
            if is_stable != self.is_stable:
                self.is_stable = is_stable
                self.stabilityChanged.emit(is_stable)
                
                if is_stable:
                    self.timer.stop()
                    logger.info("Physics simulation reached stability")
            
            self.layoutChanged.emit()
            
        except Exception as e:
            logger.error(f"Physics simulation error: {e}")
            self.timer.stop()
    
    def get_engine_info(self) -> Dict:
        """获取引擎信息"""
        engine = self.engines[self.current_algorithm]
        return {
            'algorithm': self.current_algorithm.value,
            'iteration_count': engine.iteration_count,
            'is_stable': self.is_stable,
            'node_count': len(self.nodes) if hasattr(self, 'nodes') else 0,
            'edge_count': len(self.edges) if hasattr(self, 'edges') else 0
        }


class RenderingEngine:
    """专门的渲染引擎"""
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.render_cache = {}
        self.last_viewport = None
        
    def render(self, painter: QPainter, viewport: QRectF, 
               nodes: Dict[str, GraphNode], edges: List[GraphEdge]):
        """主渲染方法"""
        if self.config.anti_aliasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 渲染顺序：边 -> 节点 -> 标签
        self._render_edges(painter, viewport, nodes, edges)
        self._render_nodes(painter, viewport, nodes)
        
        if self.config.show_labels:
            self._render_labels(painter, viewport, nodes)
    
    def _render_edges(self, painter: QPainter, viewport: QRectF,
                     nodes: Dict[str, GraphNode], edges: List[GraphEdge]):
        """渲染边"""
        pen = QPen(self.config.edge_color, 2)
        painter.setPen(pen)
        
        for edge in edges:
            source = nodes.get(edge.source)
            target = nodes.get(edge.target)
            
            if not source or not target:
                continue
            
            # 视锥剔除
            if not self._is_edge_visible(viewport, source, target):
                continue
            
            # 绘制边
            painter.drawLine(source.x, source.y, target.x, target.y)
            
            # 如果是有向边，绘制箭头
            if not edge.bidirectional:
                self._draw_arrow(painter, source, target)
    
    def _render_nodes(self, painter: QPainter, viewport: QRectF,
                     nodes: Dict[str, GraphNode]):
        """渲染节点"""
        for node in nodes.values():
            if not self._is_node_visible(viewport, node):
                continue
            
            # 选择颜色
            color = self.config.node_colors.get(node.node_type, 
                                               self.config.node_colors['OTHER'])
            
            if node.selected:
                color = color.lighter(120)
            elif node.highlighted:
                color = color.darker(120)
            
            # 绘制节点
            brush = QBrush(color)
            painter.setBrush(brush)
            painter.setPen(QPen(color.darker(130), 2))
            
            painter.drawEllipse(
                node.x - node.size/2, node.y - node.size/2,
                node.size, node.size
            )
    
    def _render_labels(self, painter: QPainter, viewport: QRectF,
                      nodes: Dict[str, GraphNode]):
        """渲染标签"""
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.setPen(QPen(self.config.text_color))
        
        for node in nodes.values():
            if not self._is_node_visible(viewport, node):
                continue
            
            # 绘制标签
            label_rect = QRectF(
                node.x - 50, node.y + node.size/2 + 5,
                100, 20
            )
            painter.drawText(label_rect, 0x84, node.label)  # AlignCenter | AlignVCenter
    
    def _draw_arrow(self, painter: QPainter, source: GraphNode, target: GraphNode):
        """绘制箭头"""
        # 计算箭头位置
        dx = target.x - source.x
        dy = target.y - source.y
        length = math.sqrt(dx**2 + dy**2)
        
        if length == 0:
            return
        
        # 单位向量
        ux = dx / length
        uy = dy / length
        
        # 箭头起点（目标节点边缘）
        arrow_start_x = target.x - ux * target.size/2
        arrow_start_y = target.y - uy * target.size/2
        
        # 箭头大小
        arrow_size = 8
        arrow_angle = math.pi / 6  # 30度
        
        # 箭头两个端点
        cos_angle = math.cos(arrow_angle)
        sin_angle = math.sin(arrow_angle)
        
        # 旋转向量
        tip1_x = arrow_start_x - arrow_size * (ux * cos_angle - uy * sin_angle)
        tip1_y = arrow_start_y - arrow_size * (uy * cos_angle + ux * sin_angle)
        
        tip2_x = arrow_start_x - arrow_size * (ux * cos_angle + uy * sin_angle)
        tip2_y = arrow_start_y - arrow_size * (uy * cos_angle - ux * sin_angle)
        
        # 绘制箭头
        painter.drawLine(arrow_start_x, arrow_start_y, tip1_x, tip1_y)
        painter.drawLine(arrow_start_x, arrow_start_y, tip2_x, tip2_y)
    
    def _is_node_visible(self, viewport: QRectF, node: GraphNode) -> bool:
        """检查节点是否在视口内"""
        margin = node.size
        return (viewport.left() - margin <= node.x <= viewport.right() + margin and
                viewport.top() - margin <= node.y <= viewport.bottom() + margin)
    
    def _is_edge_visible(self, viewport: QRectF, source: GraphNode, target: GraphNode) -> bool:
        """检查边是否在视口内"""
        # 简单的边界框检查
        min_x = min(source.x, target.x)
        max_x = max(source.x, target.x)
        min_y = min(source.y, target.y)
        max_y = max(source.y, target.y)
        
        return not (max_x < viewport.left() or min_x > viewport.right() or
                   max_y < viewport.top() or min_y > viewport.bottom())


class InteractionManager(QObject):
    """交互管理器 - 处理用户输入"""
    
    # 信号定义
    nodeSelected = pyqtSignal(str)  # 节点选择
    nodeDoubleClicked = pyqtSignal(str)  # 节点双击
    viewChanged = pyqtSignal()  # 视图变化
    
    def __init__(self, config: GraphConfig):
        super().__init__()
        self.config = config
        self.is_dragging = False
        self.is_panning = False
        self.drag_node = None
        self.last_mouse_pos = None
        self.selected_nodes = set()
        
    def handle_mouse_press(self, pos: QPointF, nodes: Dict[str, GraphNode]) -> bool:
        """处理鼠标按下事件"""
        # 查找点击的节点
        clicked_node = self._find_node_at_position(pos, nodes)
        
        if clicked_node:
            # 开始拖拽
            self.is_dragging = True
            self.drag_node = clicked_node
            clicked_node.fixed = True
            
            # 选择节点
            if clicked_node.id not in self.selected_nodes:
                self.clear_selection(nodes)
                self.select_node(clicked_node)
            
            self.nodeSelected.emit(clicked_node.id)
            return True
        else:
            # 开始平移
            self.is_panning = True
            self.last_mouse_pos = pos
            self.clear_selection(nodes)
            return False
    
    def handle_mouse_move(self, pos: QPointF, nodes: Dict[str, GraphNode]):
        """处理鼠标移动事件"""
        if self.is_dragging and self.drag_node:
            # 拖拽节点
            self.drag_node.x = pos.x()
            self.drag_node.y = pos.y()
            self.viewChanged.emit()
            
        elif self.is_panning and self.last_mouse_pos:
            # 平移视图
            delta = pos - self.last_mouse_pos
            # 这里应该通知视图进行平移
            # 具体实现需要在Widget中处理
            self.last_mouse_pos = pos
            self.viewChanged.emit()
    
    def handle_mouse_release(self, pos: QPointF, nodes: Dict[str, GraphNode]):
        """处理鼠标释放事件"""
        if self.is_dragging and self.drag_node:
            self.drag_node.fixed = False
            self.drag_node = None
        
        self.is_dragging = False
        self.is_panning = False
        self.last_mouse_pos = None
    
    def handle_double_click(self, pos: QPointF, nodes: Dict[str, GraphNode]):
        """处理双击事件"""
        clicked_node = self._find_node_at_position(pos, nodes)
        if clicked_node:
            self.nodeDoubleClicked.emit(clicked_node.id)
    
    def select_node(self, node: GraphNode):
        """选择节点"""
        node.selected = True
        self.selected_nodes.add(node.id)
    
    def clear_selection(self, nodes: Dict[str, GraphNode]):
        """清除选择"""
        for node_id in self.selected_nodes:
            if node_id in nodes:
                nodes[node_id].selected = False
        self.selected_nodes.clear()
    
    def _find_node_at_position(self, pos: QPointF, nodes: Dict[str, GraphNode]) -> Optional[GraphNode]:
        """查找指定位置的节点"""
        for node in nodes.values():
            distance = math.sqrt((node.x - pos.x())**2 + (node.y - pos.y())**2)
            if distance <= node.size / 2:
                return node
        return None


# 工厂类
class GraphEngineFactory:
    """图形引擎工厂"""
    
    @staticmethod
    def create_config(theme: str = "light") -> GraphConfig:
        """创建配置"""
        config = GraphConfig()
        
        if theme == "dark":
            config.background_color = QColor("#2C3E50")
            config.text_color = QColor("#ECF0F1")
            config.edge_color = QColor("#7F8C8D")
            # 调整节点颜色为深色主题
            for key in config.node_colors:
                config.node_colors[key] = config.node_colors[key].lighter(150)
        
        return config
    
    @staticmethod
    def create_physics_engine(config: GraphConfig) -> GraphPhysicsEngine:
        """创建物理引擎"""
        return GraphPhysicsEngine(config)
    
    @staticmethod
    def create_rendering_engine(config: GraphConfig) -> RenderingEngine:
        """创建渲染引擎"""
        return RenderingEngine(config)
    
    @staticmethod
    def create_interaction_manager(config: GraphConfig) -> InteractionManager:
        """创建交互管理器"""
        return InteractionManager(config)