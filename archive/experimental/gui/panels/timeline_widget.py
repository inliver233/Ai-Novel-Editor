"""
现代化时间线组件
提供优秀的进展可视化用户体验
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from PyQt6.QtCore import (Qt, QTimer, QRect, QSize, QPoint, pyqtSignal, 
                         QPropertyAnimation, QEasingCurve, QParallelAnimationGroup)
from PyQt6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QPixmap, 
                        QKeySequence, QShortcut, QAction, QCursor)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QPushButton, 
                           QSlider, QLabel, QComboBox, QCheckBox, QGroupBox, 
                           QSplitter, QFrame, QScrollArea, QListWidget, QListWidgetItem,
                           QTextEdit, QDateTimeEdit, QSpinBox, QTabWidget, 
                           QMessageBox, QFileDialog, QProgressDialog, QMenu,
                           QSizePolicy, QSpacerItem)

from gui.panels.timeline_engine import (TimelineEngine, TimelineEvent, TimelineTrack, 
                             TimelineViewMode, TimeScale, EventType)

logger = logging.getLogger(__name__)


class TimelineCanvas(QWidget):
    """时间线画布组件"""
    
    # 信号定义
    eventClicked = pyqtSignal(str)  # event_id
    eventDoubleClicked = pyqtSignal(str)
    rangeChanged = pyqtSignal(datetime, datetime)
    
    def __init__(self, timeline_engine: TimelineEngine):
        super().__init__()
        
        self.engine = timeline_engine
        self.current_view_range = None
        self.zoom_factor = 1.0
        self.pan_offset = 0.0
        self.is_dragging = False
        self.last_mouse_x = 0
        self.hover_event = None
        
        # UI设置
        self.setMinimumSize(800, 400)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 连接信号
        self._connect_signals()
        self._setup_shortcuts()
        
        # 样式
        self.setStyleSheet("""
            TimelineCanvas {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        
        logger.info("Timeline canvas initialized")
    
    def _connect_signals(self):
        """连接信号"""
        self.engine.dataChanged.connect(self.update)
        self.engine.viewRangeChanged.connect(self._on_view_range_changed)
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        shortcuts = [
            (QKeySequence.StandardKey.ZoomIn, self.zoom_in),
            (QKeySequence.StandardKey.ZoomOut, self.zoom_out),
            (QKeySequence(Qt.Key.Key_Home), self.reset_view),
            (QKeySequence(Qt.Key.Key_Left), lambda: self.pan(-50)),
            (QKeySequence(Qt.Key.Key_Right), lambda: self.pan(50)),
        ]
        
        for key_sequence, callback in shortcuts:
            shortcut = QShortcut(key_sequence, self)
            shortcut.activated.connect(callback)
    
    def _on_view_range_changed(self, start_time: datetime, end_time: datetime):
        """视图范围变化处理"""
        self.current_view_range = (start_time, end_time)
        self.update()
    
    def zoom_in(self):
        """放大"""
        self._zoom(1.2)
    
    def zoom_out(self):
        """缩小"""
        self._zoom(0.8)
    
    def _zoom(self, factor: float):
        """缩放"""
        self.zoom_factor *= factor
        self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))
        self._update_view_range()
        self.update()
    
    def pan(self, offset: float):
        """平移"""
        self.pan_offset += offset
        self._update_view_range()
        self.update()
    
    def reset_view(self):
        """重置视图"""
        self.zoom_factor = 1.0
        self.pan_offset = 0.0
        if hasattr(self.engine, '_auto_calculate_view_range'):
            self.engine._auto_calculate_view_range()
        self.update()
    
    def _update_view_range(self):
        """更新视图范围"""
        if not self.current_view_range:
            return
        
        start_time, end_time = self.current_view_range
        duration = (end_time - start_time).total_seconds()
        
        # 应用缩放
        new_duration = duration / self.zoom_factor
        center_time = start_time + timedelta(seconds=duration/2)
        
        # 应用平移
        pan_duration = self.pan_offset * (duration / self.width())
        center_time += timedelta(seconds=pan_duration)
        
        # 计算新范围
        new_start = center_time - timedelta(seconds=new_duration/2)
        new_end = center_time + timedelta(seconds=new_duration/2)
        
        self.engine.set_view_range(new_start, new_end)
    
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        
        try:
            if not self.current_view_range:
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                               "无时间线数据")
                return
            
            # 渲染时间线
            visible_tracks = [track for track in self.engine.tracks.values() if track.visible]
            if visible_tracks:
                self.engine.renderer.render_timeline(
                    painter, self.rect(), visible_tracks, 
                    self.current_view_range, self.engine.time_scale
                )
            else:
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                               "请选择要显示的轨道")
                
            # 绘制悬停提示
            if self.hover_event:
                self._draw_hover_tooltip(painter)
                
        except Exception as e:
            logger.error(f"Timeline paint error: {e}")
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                           f"渲染错误: {str(e)}")
        finally:
            painter.end()
    
    def _draw_hover_tooltip(self, painter: QPainter):
        """绘制悬停提示"""
        if not self.hover_event:
            return
        
        # 创建提示文本
        tooltip_text = f"{self.hover_event.title}\n{self.hover_event.formatted_timestamp}"
        if self.hover_event.description:
            tooltip_text += f"\n{self.hover_event.description[:50]}..."
        
        # 计算提示框位置
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        tooltip_rect = QRect(cursor_pos.x() + 10, cursor_pos.y() - 50, 200, 60)
        
        # 绘制背景
        painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
        painter.setPen(QPen(QColor("#333"), 1))
        painter.drawRoundedRect(tooltip_rect, 5, 5)
        
        # 绘制文本
        painter.setPen(QPen(QColor("#333")))
        painter.drawText(tooltip_rect.adjusted(5, 5, -5, -5), 
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        tooltip_text)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.last_mouse_x = event.position().x()
            
            # 检查是否点击了事件
            clicked_event = self._find_event_at_position(event.position())
            if clicked_event:
                self.eventClicked.emit(clicked_event.id)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.position())
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.is_dragging:
            # 拖拽平移
            delta = event.position().x() - self.last_mouse_x
            self.pan(delta * -1)  # 反向平移
            self.last_mouse_x = event.position().x()
        else:
            # 悬停检测
            hover_event = self._find_event_at_position(event.position())
            if hover_event != self.hover_event:
                self.hover_event = hover_event
                self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self.is_dragging = False
    
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            clicked_event = self._find_event_at_position(event.position())
            if clicked_event:
                self.eventDoubleClicked.emit(clicked_event.id)
    
    def wheelEvent(self, event):
        """滚轮事件"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
    
    def _find_event_at_position(self, pos) -> Optional[TimelineEvent]:
        """查找位置上的事件"""
        if not self.current_view_range:
            return None
        
        # 简化实现：遍历所有可见事件
        for track in self.engine.tracks.values():
            if not track.visible:
                continue
            
            for event in track.events:
                # 计算事件在屏幕上的位置
                event_screen_pos = self._world_to_screen_pos(event)
                if event_screen_pos and self._point_near_event(pos, event_screen_pos):
                    return event
        
        return None
    
    def _world_to_screen_pos(self, event: TimelineEvent) -> Optional[QPoint]:
        """将事件世界坐标转换为屏幕坐标"""
        if not self.current_view_range:
            return None
        
        start_time, end_time = self.current_view_range
        duration = (end_time - start_time).total_seconds()
        
        if duration <= 0:
            return None
        
        # 计算X位置
        event_offset = (event.timestamp - start_time).total_seconds()
        x_ratio = event_offset / duration
        x = self.rect().x() + 50 + x_ratio * (self.rect().width() - 100)
        
        # 计算Y位置（简化版本）
        track_index = 0
        for i, (track_id, track) in enumerate(self.engine.tracks.items()):
            if track.visible and track_id == event.codex_id:
                track_index = i
                break
        
        y = self.rect().y() + 70 + track_index * 50 + 25
        
        return QPoint(int(x), int(y))
    
    def _point_near_event(self, pos, event_pos: QPoint, threshold: int = 10) -> bool:
        """检查点是否接近事件"""
        dx = pos.x() - event_pos.x()
        dy = pos.y() - event_pos.y()
        return (dx * dx + dy * dy) <= threshold * threshold
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        menu.addAction("重置视图", self.reset_view)
        menu.addAction("放大", self.zoom_in)
        menu.addAction("缩小", self.zoom_out)
        menu.addSeparator()
        
        # 时间刻度选择
        scale_menu = menu.addMenu("时间刻度")
        for scale in TimeScale:
            action = scale_menu.addAction(scale.value)
            action.triggered.connect(lambda checked, s=scale: self.engine.set_time_scale(s))
        
        menu.exec(self.mapToGlobal(pos.toPoint()))


class TimelineControlPanel(QWidget):
    """时间线控制面板"""
    
    def __init__(self, timeline_engine: TimelineEngine):
        super().__init__()
        
        self.engine = timeline_engine
        self.track_checkboxes = {}
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 视图模式选择
        mode_group = QGroupBox("视图模式")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_combo = QComboBox()
        for mode in TimelineViewMode:
            self.mode_combo.addItem(mode.name, mode)
        mode_layout.addWidget(self.mode_combo)
        
        layout.addWidget(mode_group)
        
        # 时间刻度选择
        scale_group = QGroupBox("时间刻度")
        scale_layout = QVBoxLayout(scale_group)
        
        self.scale_combo = QComboBox()
        for scale in TimeScale:
            self.scale_combo.addItem(scale.value, scale)
        scale_layout.addWidget(self.scale_combo)
        
        layout.addWidget(scale_group)
        
        # 轨道控制
        track_group = QGroupBox("轨道显示")
        track_layout = QVBoxLayout(track_group)
        
        self.track_list = QWidget()
        self.track_list_layout = QVBoxLayout(self.track_list)
        
        track_scroll = QScrollArea()
        track_scroll.setWidget(self.track_list)
        track_scroll.setWidgetResizable(True)
        track_scroll.setMaximumHeight(200)
        track_layout.addWidget(track_scroll)
        
        layout.addWidget(track_group)
        
        # 分析面板
        analysis_group = QGroupBox("分析")
        analysis_layout = QVBoxLayout(analysis_group)
        
        self.analysis_text = QTextEdit()
        self.analysis_text.setMaximumHeight(150)
        self.analysis_text.setReadOnly(True)
        analysis_layout.addWidget(self.analysis_text)
        
        refresh_btn = QPushButton("刷新分析")
        refresh_btn.clicked.connect(self._update_analysis)
        analysis_layout.addWidget(refresh_btn)
        
        layout.addWidget(analysis_group)
        
        # 弹簧
        layout.addStretch()
        
        # 样式
        self.setStyleSheet("""
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
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAF50, stop:1 #45a049);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5CBF60, stop:1 #55b059);
            }
        """)
    
    def _connect_signals(self):
        """连接信号"""
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        self.engine.dataChanged.connect(self._update_track_list)
    
    def _on_mode_changed(self, index: int):
        """视图模式变化"""
        mode = self.mode_combo.itemData(index)
        if mode:
            self.engine.set_view_mode(mode)
    
    def _on_scale_changed(self, index: int):
        """时间刻度变化"""
        scale = self.scale_combo.itemData(index)
        if scale:
            self.engine.set_time_scale(scale)
    
    def _update_track_list(self):
        """更新轨道列表"""
        # 清除现有控件
        for checkbox in self.track_checkboxes.values():
            checkbox.setParent(None)
        self.track_checkboxes.clear()
        
        # 添加新的轨道控件
        for track_id, track in self.engine.tracks.items():
            checkbox = QCheckBox(f"{track.codex_title} ({track.event_count} 事件)")
            checkbox.setChecked(track.visible)
            checkbox.toggled.connect(
                lambda checked, tid=track_id: self.engine.toggle_track_visibility(tid, checked)
            )
            
            # 设置颜色指示
            color_indicator = f"QCheckBox {{ color: {track.color.name()}; font-weight: bold; }}"
            checkbox.setStyleSheet(color_indicator)
            
            self.track_list_layout.addWidget(checkbox)
            self.track_checkboxes[track_id] = checkbox
    
    def _update_analysis(self):
        """更新分析信息"""
        try:
            analysis = self.engine.get_analysis()
            
            text_parts = []
            
            # 总体统计
            if 'cross_analysis' in analysis:
                cross = analysis['cross_analysis']
                text_parts.append("📊 总体统计:")
                text_parts.append(f"  总事件数: {cross.get('total_events', 0)}")
                
                if 'date_range' in cross:
                    start, end = cross['date_range']
                    text_parts.append(f"  时间跨度: {start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}")
            
            # 轨道摘要
            if 'track_summaries' in analysis:
                text_parts.append("\n🎯 轨道分析:")
                for summary in analysis['track_summaries'][:3]:  # 只显示前3个
                    text_parts.append(f"  {summary['track_title']}: {summary['total_events']} 事件")
                    if 'avg_interval_days' in summary:
                        text_parts.append(f"    平均间隔: {summary['avg_interval_days']:.1f} 天")
            
            # 同步点
            if 'synchronization_points' in analysis:
                sync_points = analysis['synchronization_points']
                if sync_points:
                    text_parts.append(f"\n🔗 同步事件: {len(sync_points)} 个")
                    for sync in sync_points[:2]:  # 只显示前2个
                        involved = ', '.join(sync['involved_tracks'][:2])
                        text_parts.append(f"  {sync['timestamp'].strftime('%Y-%m-%d')}: {involved}")
            
            self.analysis_text.setPlainText('\n'.join(text_parts))
            
        except Exception as e:
            self.analysis_text.setPlainText(f"分析错误: {e}")
            logger.error(f"Analysis update error: {e}")


class TimelineWidget(QWidget):
    """完整的时间线组件"""
    
    # 信号定义
    eventSelected = pyqtSignal(str, dict)  # event_id, event_data
    eventDoubleClicked = pyqtSignal(str, dict)
    
    def __init__(self, codex_manager, parent=None):
        super().__init__(parent)
        
        self.codex_manager = codex_manager
        
        # 创建时间线引擎
        self.engine = TimelineEngine(codex_manager)
        
        self._setup_ui()
        self._connect_signals()
        self._load_data()
        
        logger.info("Timeline widget initialized")
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 主要区域
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 时间线画布
        self.canvas = TimelineCanvas(self.engine)
        splitter.addWidget(self.canvas)
        
        # 控制面板
        self.control_panel = TimelineControlPanel(self.engine)
        self.control_panel.setMaximumWidth(300)
        splitter.addWidget(self.control_panel)
        
        # 设置比例
        splitter.setSizes([800, 300])
        
        # 状态栏
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 4, 8, 4)
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        self.zoom_label = QLabel("缩放: 100%")
        status_layout.addWidget(self.zoom_label)
        
        layout.addWidget(status_frame)
        
        # 样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
            }
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f0f0f0);
                border-top: 1px solid #ddd;
            }
        """)
    
    def _create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # 基本操作
        toolbar.addAction("🔄", "刷新", self._load_data)
        toolbar.addAction("🏠", "重置视图", self.canvas.reset_view)
        toolbar.addAction("🔍+", "放大", self.canvas.zoom_in)
        toolbar.addAction("🔍-", "缩小", self.canvas.zoom_out)
        toolbar.addSeparator()
        
        # 导出
        toolbar.addAction("📊", "导出分析", self._export_analysis)
        toolbar.addAction("📷", "导出图片", self._export_image)
        toolbar.addSeparator()
        
        # 帮助
        toolbar.addAction("❓", "帮助", self._show_help)
        
        # 样式
        toolbar.setStyleSheet("""
            QToolBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f0f0f0);
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px;
            }
            QAction {
                padding: 4px 8px;
                margin: 2px;
                border-radius: 3px;
            }
            QAction:hover {
                background: #e9ecef;
            }
        """)
        
        return toolbar
    
    def _connect_signals(self):
        """连接信号"""
        # 画布信号
        self.canvas.eventClicked.connect(self._on_event_clicked)
        self.canvas.eventDoubleClicked.connect(self._on_event_double_clicked)
        
        # 引擎信号
        self.engine.dataChanged.connect(self._update_status)
        
        # Codex管理器信号
        if self.codex_manager:
            try:
                self.codex_manager.entryUpdated.connect(self._on_codex_changed)
                self.codex_manager.entryDeleted.connect(self._on_codex_changed)
            except AttributeError:
                logger.warning("CodexManager signals not available")
    
    def _load_data(self):
        """加载数据"""
        try:
            self.engine.load_progression_data()
            self.status_label.setText(f"已加载 {len(self.engine.tracks)} 个轨道")
        except Exception as e:
            self.status_label.setText(f"加载失败: {e}")
            logger.error(f"Failed to load timeline data: {e}")
    
    def _update_status(self):
        """更新状态"""
        visible_tracks = len([t for t in self.engine.tracks.values() if t.visible])
        total_tracks = len(self.engine.tracks)
        self.status_label.setText(f"显示 {visible_tracks}/{total_tracks} 个轨道")
        
        # 更新缩放标签
        zoom_percent = int(self.canvas.zoom_factor * 100)
        self.zoom_label.setText(f"缩放: {zoom_percent}%")
    
    def _on_event_clicked(self, event_id: str):
        """事件点击处理"""
        event_data = self._find_event_by_id(event_id)
        if event_data:
            self.eventSelected.emit(event_id, event_data)
            self.status_label.setText(f"选中事件: {event_data.get('title', event_id)}")
    
    def _on_event_double_clicked(self, event_id: str):
        """事件双击处理"""
        event_data = self._find_event_by_id(event_id)
        if event_data:
            self.eventDoubleClicked.emit(event_id, event_data)
    
    def _find_event_by_id(self, event_id: str) -> Optional[Dict]:
        """根据ID查找事件"""
        for track in self.engine.tracks.values():
            for event in track.events:
                if event.id == event_id:
                    return {
                        'id': event.id,
                        'title': event.title,
                        'description': event.description,
                        'type': event.event_type.value,
                        'timestamp': event.timestamp,
                        'codex_id': event.codex_id,
                        'importance': event.importance,
                        'metadata': event.metadata
                    }
        return None
    
    def _on_codex_changed(self):
        """Codex数据变化处理"""
        self._load_data()
    
    def _export_analysis(self):
        """导出分析"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出分析报告", "timeline_analysis.json",
                "JSON Files (*.json);;All Files (*)"
            )
            
            if file_path:
                import json
                analysis_data = self.engine.export_timeline_data()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)
                
                QMessageBox.information(self, "导出成功", f"分析报告已保存到:\n{file_path}")
                
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出失败: {e}")
            logger.error(f"Analysis export error: {e}")
    
    def _export_image(self):
        """导出图片"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出图片", "timeline.png",
                "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
            )
            
            if file_path:
                # 创建高分辨率图像
                pixmap = QPixmap(self.canvas.size() * 2)  # 2倍分辨率
                pixmap.fill(Qt.GlobalColor.white)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # 缩放绘制
                painter.scale(2.0, 2.0)
                self.canvas.render(painter)
                painter.end()
                
                pixmap.save(file_path)
                QMessageBox.information(self, "导出成功", f"图片已保存到:\n{file_path}")
                
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出失败: {e}")
            logger.error(f"Image export error: {e}")
    
    def _show_help(self):
        """显示帮助"""
        help_text = """
        <h3>时间线功能帮助</h3>
        
        <h4>基本操作：</h4>
        <ul>
        <li><b>鼠标滚轮</b>：缩放时间线</li>
        <li><b>左键拖拽</b>：平移时间线</li>
        <li><b>单击事件</b>：选择事件</li>
        <li><b>双击事件</b>：编辑事件</li>
        </ul>
        
        <h4>快捷键：</h4>
        <ul>
        <li><b>Ctrl +/-</b>：缩放</li>
        <li><b>Home</b>：重置视图</li>
        <li><b>左右箭头</b>：平移</li>
        </ul>
        
        <h4>功能说明：</h4>
        <ul>
        <li><b>轨道</b>：每个Codex条目对应一条轨道</li>
        <li><b>事件</b>：轨道上的点表示进展事件</li>
        <li><b>分析</b>：自动分析进展趋势和关联</li>
        </ul>
        """
        
        QMessageBox.information(self, "帮助", help_text)
    
    # 公共接口
    def refresh(self):
        """刷新数据"""
        self._load_data()
    
    def set_visible_tracks(self, track_ids: List[str]):
        """设置可见轨道"""
        for track_id in self.engine.tracks:
            visible = track_id in track_ids
            self.engine.toggle_track_visibility(track_id, visible)
    
    def focus_on_event(self, event_id: str):
        """聚焦到特定事件"""
        # 找到事件并调整视图
        for track in self.engine.tracks.values():
            for event in track.events:
                if event.id == event_id:
                    # 设置视图范围以包含该事件
                    margin = timedelta(days=30)
                    start_time = event.timestamp - margin
                    end_time = event.timestamp + margin
                    self.engine.set_view_range(start_time, end_time)
                    
                    # 选择事件
                    self.engine.select_event(event_id)
                    return True
        return False