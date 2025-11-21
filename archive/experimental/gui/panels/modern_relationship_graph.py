"""
现代化关系图组件
基于新的图形引擎架构，提供优秀的用户体验
"""

import logging
import math
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from PyQt6.QtCore import (Qt, QPointF, QRectF, QTimer, pyqtSignal, QPropertyAnimation, 
                         QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup)
from PyQt6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, 
                        QKeySequence, QShortcut, QAction, QIcon)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QPushButton, 
                           QSlider, QLabel, QComboBox, QCheckBox, QGroupBox, 
                           QSplitter, QFrame, QButtonGroup, QSpacerItem, QSizePolicy,
                           QMenu, QMessageBox, QFileDialog, QProgressBar, QStatusBar)

from gui.panels.graph_engine import (GraphConfig, GraphNode, GraphEdge, GraphPhysicsEngine, 
                          RenderingEngine, InteractionManager, LayoutAlgorithm,
                          GraphEngineFactory)

logger = logging.getLogger(__name__)


class ViewMode(Enum):
    """视图模式"""
    INTERACTIVE = "interactive"  # 交互模式
    PRESENTATION = "presentation"  # 演示模式
    ANALYSIS = "analysis"  # 分析模式


class ModernGraphCanvas(QWidget):
    """现代化图形画布"""
    
    # 信号定义
    nodeSelected = pyqtSignal(str)
    nodeDoubleClicked = pyqtSignal(str) 
    viewportChanged = pyqtSignal(QRectF)
    layoutStabilized = pyqtSignal()
    
    def __init__(self, config: GraphConfig):
        super().__init__()
        
        # 核心组件
        self.config = config
        self.physics_engine = GraphEngineFactory.create_physics_engine(config)
        self.rendering_engine = GraphEngineFactory.create_rendering_engine(config)
        self.interaction_manager = GraphEngineFactory.create_interaction_manager(config)
        
        # 数据
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        
        # 视图状态
        self.viewport = QRectF(-300, -300, 600, 600)
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.view_mode = ViewMode.INTERACTIVE
        
        # UI状态
        self.is_fullscreen = False
        self.show_grid = False
        self.show_stats = True
        
        # 性能优化
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.update)
        
        self._setup_canvas()
        self._connect_signals()
        self._setup_shortcuts()
        
        logger.info("Modern graph canvas initialized")
    
    def _setup_canvas(self):
        """设置画布"""
        # 基本设置
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # 现代化样式
        self.setStyleSheet(f"""
            ModernGraphCanvas {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.config.background_color.lighter(105).name()}, 
                    stop:1 {self.config.background_color.name()});
                border: 1px solid {self.config.edge_color.name()};
                border-radius: 8px;
            }}
        """)
    
    def _connect_signals(self):
        """连接信号"""
        # 物理引擎信号
        self.physics_engine.layoutChanged.connect(self._schedule_render)
        self.physics_engine.stabilityChanged.connect(self._on_stability_changed)
        
        # 交互管理器信号
        self.interaction_manager.nodeSelected.connect(self.nodeSelected.emit)
        self.interaction_manager.nodeDoubleClicked.connect(self.nodeDoubleClicked.emit)
        self.interaction_manager.viewChanged.connect(self._schedule_render)
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        shortcuts = [
            (QKeySequence.StandardKey.ZoomIn, self.zoom_in),
            (QKeySequence.StandardKey.ZoomOut, self.zoom_out),
            (QKeySequence(Qt.Key.Key_Home), self.reset_view),
            (QKeySequence(Qt.Key.Key_Space), self.toggle_simulation),
            (QKeySequence(Qt.Key.Key_G), self.toggle_grid),
            (QKeySequence(Qt.Key.Key_F11), self.toggle_fullscreen),
            (QKeySequence(Qt.Key.Key_R), self.refresh_layout),
            (QKeySequence(Qt.Key.Key_S), self.toggle_stats),
        ]
        
        for key_sequence, callback in shortcuts:
            shortcut = QShortcut(key_sequence, self)
            shortcut.activated.connect(callback)
    
    def set_data(self, nodes: List[Dict], edges: List[Dict]):
        """设置图形数据"""
        try:
            # 转换数据格式
            self.nodes.clear()
            self.edges.clear()
            
            # 创建节点
            for node_data in nodes:
                node = GraphNode(
                    id=node_data['id'],
                    label=node_data.get('title', node_data['id']),
                    node_type=node_data.get('type', 'OTHER'),
                    size=self._calculate_node_size(node_data),
                    weight=node_data.get('weight', 1.0),
                    metadata=node_data
                )
                self.nodes[node.id] = node
            
            # 创建边
            for edge_data in edges:
                edge = GraphEdge(
                    source=edge_data['source'],
                    target=edge_data['target'],
                    label=edge_data.get('label', ''),
                    weight=edge_data.get('weight', 1.0),
                    edge_type=edge_data.get('type', 'default'),
                    bidirectional=edge_data.get('bidirectional', False),
                    metadata=edge_data
                )
                self.edges.append(edge)
            
            # 启动物理模拟
            self.physics_engine.start_simulation(self.nodes, self.edges)
            
            # 适应视图
            self.fit_to_content()
            
            logger.info(f"Graph data loaded: {len(self.nodes)} nodes, {len(self.edges)} edges")
            
        except Exception as e:
            logger.error(f"Failed to set graph data: {e}")
            raise
    
    def _calculate_node_size(self, node_data: Dict) -> float:
        """计算节点大小"""
        base_size = 30.0
        weight = node_data.get('weight', 1.0)
        
        # 根据权重调整大小
        min_size, max_size = self.config.node_size_range
        size = base_size + (weight - 1.0) * 10.0
        
        return max(min_size, min(max_size, size))
    
    def set_layout_algorithm(self, algorithm: LayoutAlgorithm):
        """设置布局算法"""
        self.physics_engine.set_algorithm(algorithm)
        if self.nodes:
            self.physics_engine.start_simulation(self.nodes, self.edges)
    
    def set_view_mode(self, mode: ViewMode):
        """设置视图模式"""
        self.view_mode = mode
        
        if mode == ViewMode.PRESENTATION:
            # 演示模式：隐藏控制器，优化视觉效果
            self.config.show_labels = True
            self.config.anti_aliasing = True
        elif mode == ViewMode.ANALYSIS:
            # 分析模式：显示详细信息
            self.show_stats = True
            
        self.update()
    
    # 视图控制方法
    def zoom_in(self):
        """放大"""
        self._zoom(1.2)
    
    def zoom_out(self):
        """缩小"""
        self._zoom(0.8)
    
    def _zoom(self, factor: float):
        """缩放"""
        old_zoom = self.zoom_factor
        self.zoom_factor *= factor
        self.zoom_factor = max(0.1, min(5.0, self.zoom_factor))  # 限制缩放范围
        
        if old_zoom != self.zoom_factor:
            self._update_viewport()
            self.update()
    
    def reset_view(self):
        """重置视图"""
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.fit_to_content()
    
    def fit_to_content(self):
        """适应内容"""
        if not self.nodes:
            return
        
        # 计算边界
        min_x = min(node.x for node in self.nodes.values())
        max_x = max(node.x for node in self.nodes.values())
        min_y = min(node.y for node in self.nodes.values())
        max_y = max(node.y for node in self.nodes.values())
        
        # 添加边距
        margin = 50
        content_rect = QRectF(min_x - margin, min_y - margin,
                             max_x - min_x + 2*margin, max_y - min_y + 2*margin)
        
        # 计算适应的缩放和偏移
        widget_rect = self.rect()
        if content_rect.width() > 0 and content_rect.height() > 0:
            scale_x = widget_rect.width() / content_rect.width()
            scale_y = widget_rect.height() / content_rect.height()
            self.zoom_factor = min(scale_x, scale_y) * 0.9  # 留一些边距
            
            # 计算中心偏移
            content_center = content_rect.center()
            widget_center = QPointF(widget_rect.width()/2, widget_rect.height()/2)
            self.pan_offset = widget_center - QPointF(content_center.x() * self.zoom_factor,
                                                     content_center.y() * self.zoom_factor)
        
        self._update_viewport()
        self.update()
    
    def toggle_simulation(self):
        """切换模拟状态"""
        if self.physics_engine.timer.isActive():
            self.physics_engine.stop_simulation()
        else:
            self.physics_engine.start_simulation(self.nodes, self.edges)
    
    def toggle_grid(self):
        """切换网格显示"""
        self.show_grid = not self.show_grid
        self.update()
    
    def toggle_fullscreen(self):
        """切换全屏"""
        if self.is_fullscreen:
            self.showNormal()
        else:
            self.showFullScreen()
        self.is_fullscreen = not self.is_fullscreen
    
    def toggle_stats(self):
        """切换统计信息显示"""
        self.show_stats = not self.show_stats
        self.update()
    
    def refresh_layout(self):
        """刷新布局"""
        if self.nodes:
            self.physics_engine.start_simulation(self.nodes, self.edges)
    
    def export_image(self, file_path: str, width: int = 1920, height: int = 1080):
        """导出图片"""
        try:
            # 创建高分辨率图像
            pixmap = QPixmap(width, height)
            pixmap.fill(self.config.background_color)
            
            painter = QPainter(pixmap)
            
            # 保存当前状态
            old_viewport = self.viewport
            
            # 计算导出视口
            if self.nodes:
                # 适应所有内容
                min_x = min(node.x for node in self.nodes.values())
                max_x = max(node.x for node in self.nodes.values())
                min_y = min(node.y for node in self.nodes.values())
                max_y = max(node.y for node in self.nodes.values())
                
                margin = 100
                export_viewport = QRectF(min_x - margin, min_y - margin,
                                       max_x - min_x + 2*margin, max_y - min_y + 2*margin)
            else:
                export_viewport = QRectF(-300, -300, 600, 600)
            
            # 设置变换
            painter.setViewport(0, 0, width, height)
            painter.setWindow(export_viewport.toRect())
            
            # 渲染
            self.rendering_engine.render(painter, export_viewport, self.nodes, self.edges)
            
            painter.end()
            
            # 保存文件
            pixmap.save(file_path)
            
            # 恢复状态
            self.viewport = old_viewport
            
            logger.info(f"Graph exported to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export image: {e}")
            return False
    
    # 事件处理
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        
        try:
            # 设置变换
            painter.setViewport(self.rect())
            painter.setWindow(self.viewport.toRect())
            
            # 绘制网格
            if self.show_grid:
                self._draw_grid(painter)
            
            # 渲染图形
            self.rendering_engine.render(painter, self.viewport, self.nodes, self.edges)
            
            # 绘制统计信息
            if self.show_stats:
                self._draw_stats(painter)
            
        except Exception as e:
            logger.error(f"Paint error: {e}")
        finally:
            painter.end()
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._screen_to_world(event.position())
            self.interaction_manager.handle_mouse_press(pos, self.nodes)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.position())
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        pos = self._screen_to_world(event.position())
        self.interaction_manager.handle_mouse_move(pos, self.nodes)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        pos = self._screen_to_world(event.position())
        self.interaction_manager.handle_mouse_release(pos, self.nodes)
    
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._screen_to_world(event.position())
            self.interaction_manager.handle_double_click(pos, self.nodes)
    
    def wheelEvent(self, event):
        """滚轮事件"""
        # 缩放
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom(1.1)
        else:
            self._zoom(0.9)
    
    def keyPressEvent(self, event):
        """键盘事件"""
        # 这里可以添加额外的键盘处理
        super().keyPressEvent(event)
    
    # 辅助方法
    def _screen_to_world(self, screen_pos) -> QPointF:
        """屏幕坐标转世界坐标"""
        # 移除平移偏移
        adjusted_pos = screen_pos - self.pan_offset
        # 应用缩放
        world_pos = QPointF(adjusted_pos.x() / self.zoom_factor,
                           adjusted_pos.y() / self.zoom_factor)
        # 转换到视口坐标系
        return QPointF(world_pos.x() + self.viewport.left(),
                      world_pos.y() + self.viewport.top())
    
    def _world_to_screen(self, world_pos: QPointF) -> QPointF:
        """世界坐标转屏幕坐标"""
        # 从视口坐标系转换
        local_pos = QPointF(world_pos.x() - self.viewport.left(),
                           world_pos.y() - self.viewport.top())
        # 应用缩放
        scaled_pos = QPointF(local_pos.x() * self.zoom_factor,
                           local_pos.y() * self.zoom_factor)
        # 添加平移偏移
        return scaled_pos + self.pan_offset
    
    def _update_viewport(self):
        """更新视口"""
        widget_rect = self.rect()
        if widget_rect.isValid():
            viewport_width = widget_rect.width() / self.zoom_factor
            viewport_height = widget_rect.height() / self.zoom_factor
            
            center_x = -self.pan_offset.x() / self.zoom_factor
            center_y = -self.pan_offset.y() / self.zoom_factor
            
            self.viewport = QRectF(
                center_x - viewport_width/2, center_y - viewport_height/2,
                viewport_width, viewport_height
            )
            
            self.viewportChanged.emit(self.viewport)
    
    def _schedule_render(self):
        """延迟渲染"""
        if not self.render_timer.isActive():
            self.render_timer.start(16)  # ~60fps
    
    def _on_stability_changed(self, is_stable: bool):
        """稳定性变化处理"""
        if is_stable:
            self.layoutStabilized.emit()
    
    def _draw_grid(self, painter: QPainter):
        """绘制网格"""
        grid_size = 50
        pen = QPen(self.config.edge_color.lighter(180), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        
        # 计算网格范围
        left = int(self.viewport.left() // grid_size) * grid_size
        right = int(self.viewport.right() // grid_size + 1) * grid_size
        top = int(self.viewport.top() // grid_size) * grid_size
        bottom = int(self.viewport.bottom() // grid_size + 1) * grid_size
        
        # 绘制垂直线
        x = left
        while x <= right:
            painter.drawLine(x, self.viewport.top(), x, self.viewport.bottom())
            x += grid_size
        
        # 绘制水平线
        y = top
        while y <= bottom:
            painter.drawLine(self.viewport.left(), y, self.viewport.right(), y)
            y += grid_size
    
    def _draw_stats(self, painter: QPainter):
        """绘制统计信息"""
        # 恢复屏幕坐标系
        painter.resetTransform()
        
        # 设置字体和颜色
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.setPen(QPen(self.config.text_color))
        
        # 获取引擎信息
        engine_info = self.physics_engine.get_engine_info()
        
        stats_text = [
            f"节点: {len(self.nodes)}",
            f"边: {len(self.edges)}",
            f"算法: {engine_info['algorithm']}",
            f"迭代: {engine_info['iteration_count']}",
            f"状态: {'稳定' if engine_info['is_stable'] else '运行中'}",
            f"缩放: {self.zoom_factor:.2f}x",
        ]
        
        # 绘制统计信息
        y = 20
        for text in stats_text:
            painter.drawText(10, y, text)
            y += 20
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 视图操作
        menu.addAction("重置视图", self.reset_view)
        menu.addAction("适应内容", self.fit_to_content)
        menu.addSeparator()
        
        # 布局算法
        layout_menu = menu.addMenu("布局算法")
        for algorithm in LayoutAlgorithm:
            action = layout_menu.addAction(algorithm.value)
            action.triggered.connect(lambda checked, alg=algorithm: self.set_layout_algorithm(alg))
        
        menu.addSeparator()
        
        # 显示选项
        menu.addAction("切换网格", self.toggle_grid)
        menu.addAction("切换统计", self.toggle_stats)
        menu.addSeparator()
        
        # 导出
        menu.addAction("导出图片", self._export_dialog)
        
        menu.exec(self.mapToGlobal(pos.toPoint()))
    
    def _export_dialog(self):
        """导出对话框"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出图片", "graph.png", 
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            if self.export_image(file_path):
                QMessageBox.information(self, "导出成功", f"图片已保存到:\n{file_path}")
            else:
                QMessageBox.warning(self, "导出失败", "图片导出失败，请检查路径和权限。")


class ModernRelationshipGraphWidget(QWidget):
    """现代化关系图组件 - 完整版本"""
    
    # 信号定义
    nodeSelected = pyqtSignal(str)
    nodeDoubleClicked = pyqtSignal(str)
    
    def __init__(self, codex_manager, parent=None):
        super().__init__(parent)
        
        self.codex_manager = codex_manager
        
        # 创建配置和画布
        self.config = GraphEngineFactory.create_config("light")  # 可以根据主题切换
        self.canvas = ModernGraphCanvas(self.config)
        
        self._setup_ui()
        self._connect_signals()
        self._load_graph_data()
        
        logger.info("Modern relationship graph widget initialized")
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 创建工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 创建主要区域
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 添加画布
        splitter.addWidget(self.canvas)
        
        # 添加控制面板
        control_panel = self._create_control_panel()
        splitter.addWidget(control_panel)
        
        # 设置比例
        splitter.setSizes([800, 200])
        
        # 现代化样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
            }
            QToolBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f0f0f0);
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAF50, stop:1 #45a049);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5CBF60, stop:1 #55b059);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d8b40, stop:1 #357a38);
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
    
    def _create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # 视图控制
        toolbar.addAction("🔄", "刷新", self.canvas.refresh_layout)
        toolbar.addAction("🎯", "适应", self.canvas.fit_to_content)
        toolbar.addAction("🏠", "重置", self.canvas.reset_view)
        toolbar.addSeparator()
        
        # 模拟控制
        toolbar.addAction("⏯️", "模拟", self.canvas.toggle_simulation)
        toolbar.addAction("📷", "截图", self.canvas._export_dialog)
        toolbar.addSeparator()
        
        # 布局算法选择
        algorithm_combo = QComboBox()
        for algorithm in LayoutAlgorithm:
            algorithm_combo.addItem(algorithm.value, algorithm)
        algorithm_combo.currentIndexChanged.connect(self._on_algorithm_changed)
        toolbar.addWidget(QLabel("布局:"))
        toolbar.addWidget(algorithm_combo)
        
        return toolbar
    
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        panel.setMaximumWidth(250)
        layout = QVBoxLayout(panel)
        
        # 物理参数组
        physics_group = QGroupBox("物理参数")
        physics_layout = QVBoxLayout(physics_group)
        
        # 力强度
        physics_layout.addWidget(QLabel("力强度:"))
        force_slider = QSlider(Qt.Orientation.Horizontal)
        force_slider.setRange(1, 100)
        force_slider.setValue(int(self.config.force_strength))
        force_slider.valueChanged.connect(self._on_force_changed)
        physics_layout.addWidget(force_slider)
        
        # 斥力强度
        physics_layout.addWidget(QLabel("斥力强度:"))
        charge_slider = QSlider(Qt.Orientation.Horizontal)
        charge_slider.setRange(100, 1000)
        charge_slider.setValue(int(-self.config.charge_strength))
        charge_slider.valueChanged.connect(self._on_charge_changed)
        physics_layout.addWidget(charge_slider)
        
        layout.addWidget(physics_group)
        
        # 显示选项组
        display_group = QGroupBox("显示选项")
        display_layout = QVBoxLayout(display_group)
        
        # 显示标签
        labels_check = QCheckBox("显示标签")
        labels_check.setChecked(self.config.show_labels)
        labels_check.toggled.connect(self._on_labels_toggled)
        display_layout.addWidget(labels_check)
        
        # 显示网格
        grid_check = QCheckBox("显示网格")
        grid_check.setChecked(self.canvas.show_grid)
        grid_check.toggled.connect(self.canvas.toggle_grid)
        display_layout.addWidget(grid_check)
        
        # 显示统计
        stats_check = QCheckBox("显示统计")
        stats_check.setChecked(self.canvas.show_stats)
        stats_check.toggled.connect(self.canvas.toggle_stats)
        display_layout.addWidget(stats_check)
        
        layout.addWidget(display_group)
        
        # 添加弹簧
        layout.addStretch()
        
        return panel
    
    def _connect_signals(self):
        """连接信号"""
        self.canvas.nodeSelected.connect(self.nodeSelected.emit)
        self.canvas.nodeDoubleClicked.connect(self.nodeDoubleClicked.emit)
        
        # 监听Codex数据变化
        if self.codex_manager:
            try:
                self.codex_manager.entryAdded.connect(self._on_codex_changed)
                self.codex_manager.entryUpdated.connect(self._on_codex_changed)
                self.codex_manager.entryDeleted.connect(self._on_codex_changed)
            except AttributeError:
                logger.warning("CodexManager signals not available")
    
    def _load_graph_data(self):
        """加载图形数据"""
        try:
            if not self.codex_manager:
                return
            
            # 获取所有条目
            entries = self.codex_manager.get_all_entries()
            
            # 转换为节点数据
            nodes = []
            for entry in entries:
                nodes.append({
                    'id': entry.id,
                    'title': entry.title,
                    'type': entry.entry_type.value,
                    'weight': len(entry.aliases) + 1 if entry.aliases else 1,
                    'description': entry.description,
                    'is_global': entry.is_global
                })
            
            # 生成边数据（基于关系）
            edges = []
            for entry in entries:
                if entry.relationships:
                    for relationship in entry.relationships:
                        target_id = relationship.get('target_id')
                        if target_id:
                            edges.append({
                                'source': entry.id,
                                'target': target_id,
                                'label': relationship.get('type', ''),
                                'weight': 1.0,
                                'type': relationship.get('type', 'default')
                            })
            
            # 设置数据到画布
            self.canvas.set_data(nodes, edges)
            
            logger.info(f"Graph data loaded: {len(nodes)} nodes, {len(edges)} edges")
            
        except Exception as e:
            logger.error(f"Failed to load graph data: {e}")
    
    # 事件处理方法
    def _on_algorithm_changed(self, index: int):
        """布局算法改变"""
        combo = self.sender()
        algorithm = combo.itemData(index)
        if algorithm:
            self.canvas.set_layout_algorithm(algorithm)
    
    def _on_force_changed(self, value: int):
        """力强度改变"""
        self.config.force_strength = float(value)
    
    def _on_charge_changed(self, value: int):
        """斥力强度改变"""
        self.config.charge_strength = -float(value)
    
    def _on_labels_toggled(self, checked: bool):
        """标签显示切换"""
        self.config.show_labels = checked
        self.canvas.update()
    
    def _on_codex_changed(self):
        """Codex数据变化"""
        self._load_graph_data()
    
    # 公共接口
    def set_theme(self, theme: str):
        """设置主题"""
        self.config = GraphEngineFactory.create_config(theme)
        self.canvas.config = self.config
        self.canvas.rendering_engine = GraphEngineFactory.create_rendering_engine(self.config)
        self.canvas.update()
    
    def refresh(self):
        """刷新数据"""
        self._load_graph_data()
        
    def export_graph(self, file_path: str) -> bool:
        """导出图形"""
        return self.canvas.export_image(file_path)