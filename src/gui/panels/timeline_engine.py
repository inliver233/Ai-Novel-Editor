"""
进展时间线引擎
提供高质量的时间线数据处理和可视化功能
"""

import logging
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any, Union
from enum import Enum, auto
from abc import ABC, abstractmethod

from PyQt6.QtCore import QObject, pyqtSignal, QRect, QRectF, QPointF, QDateTime, QDate
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QLinearGradient
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    CREATION = "creation"           # 创建
    DEVELOPMENT = "development"     # 发展
    RELATIONSHIP = "relationship"   # 关系变化
    CONFLICT = "conflict"          # 冲突
    RESOLUTION = "resolution"      # 解决
    MILESTONE = "milestone"        # 里程碑
    CUSTOM = "custom"              # 自定义


class TimelineViewMode(Enum):
    """时间线视图模式"""
    CHRONOLOGICAL = auto()   # 时间顺序
    GROUPED = auto()         # 分组显示
    COMPARISON = auto()      # 对比模式
    STATISTICAL = auto()     # 统计模式


class TimeScale(Enum):
    """时间刻度"""
    DAYS = "days"
    WEEKS = "weeks" 
    MONTHS = "months"
    YEARS = "years"
    AUTO = "auto"


@dataclass
class TimelineEvent:
    """时间线事件数据模型"""
    id: str
    codex_id: str
    title: str
    description: str = ""
    event_type: EventType = EventType.DEVELOPMENT
    timestamp: datetime = field(default_factory=datetime.now)
    chapter_id: str = ""
    scene_order: int = 0
    importance: int = 3  # 1-5 重要程度
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 可视化属性
    color: Optional[QColor] = None
    icon: str = ""
    duration: timedelta = field(default_factory=lambda: timedelta(0))
    
    def __post_init__(self):
        """初始化后处理"""
        if self.color is None:
            self.color = self._get_default_color()
        if not self.icon:
            self.icon = self._get_default_icon()
    
    def _get_default_color(self) -> QColor:
        """获取默认颜色"""
        color_map = {
            EventType.CREATION: QColor("#2ECC71"),      # 绿色
            EventType.DEVELOPMENT: QColor("#3498DB"),   # 蓝色
            EventType.RELATIONSHIP: QColor("#F39C12"),  # 橙色
            EventType.CONFLICT: QColor("#E74C3C"),      # 红色
            EventType.RESOLUTION: QColor("#9B59B6"),    # 紫色
            EventType.MILESTONE: QColor("#F1C40F"),     # 黄色
            EventType.CUSTOM: QColor("#95A5A6")         # 灰色
        }
        return color_map.get(self.event_type, QColor("#95A5A6"))
    
    def _get_default_icon(self) -> str:
        """获取默认图标"""
        icon_map = {
            EventType.CREATION: "✨",
            EventType.DEVELOPMENT: "📈",
            EventType.RELATIONSHIP: "🤝",
            EventType.CONFLICT: "⚔️",
            EventType.RESOLUTION: "✅",
            EventType.MILESTONE: "🎯",
            EventType.CUSTOM: "📌"
        }
        return icon_map.get(self.event_type, "📌")
    
    @property
    def formatted_timestamp(self) -> str:
        """格式化时间戳"""
        return self.timestamp.strftime("%Y-%m-%d %H:%M")
    
    @property
    def date_only(self) -> QDate:
        """仅日期"""
        return QDate(self.timestamp.year, self.timestamp.month, self.timestamp.day)


@dataclass 
class TimelineTrack:
    """时间线轨道 - 用于多条目对比"""
    codex_id: str
    codex_title: str
    codex_type: str
    events: List[TimelineEvent] = field(default_factory=list)
    color: QColor = field(default_factory=lambda: QColor("#3498DB"))
    visible: bool = True
    height: int = 40
    
    @property
    def event_count(self) -> int:
        """事件数量"""
        return len(self.events)
    
    @property
    def date_range(self) -> Tuple[datetime, datetime]:
        """日期范围"""
        if not self.events:
            now = datetime.now()
            return now, now
        
        dates = [event.timestamp for event in self.events]
        return min(dates), max(dates)
    
    def get_events_in_range(self, start: datetime, end: datetime) -> List[TimelineEvent]:
        """获取指定时间范围内的事件"""
        return [event for event in self.events 
                if start <= event.timestamp <= end]


class TimelineAnalyzer:
    """时间线分析器"""
    
    def __init__(self):
        self.cache = {}
    
    def analyze_progression_trend(self, events: List[TimelineEvent]) -> Dict[str, Any]:
        """分析进展趋势"""
        if not events:
            return {}
        
        # 按时间排序
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        # 计算时间间隔
        intervals = []
        for i in range(1, len(sorted_events)):
            delta = sorted_events[i].timestamp - sorted_events[i-1].timestamp
            intervals.append(delta.total_seconds() / 86400)  # 转换为天数
        
        # 统计事件类型
        type_counts = {}
        for event in events:
            type_counts[event.event_type.value] = type_counts.get(event.event_type.value, 0) + 1
        
        # 重要程度分布
        importance_dist = [0] * 5
        for event in events:
            if 1 <= event.importance <= 5:
                importance_dist[event.importance - 1] += 1
        
        return {
            'total_events': len(events),
            'date_range': (sorted_events[0].timestamp, sorted_events[-1].timestamp),
            'avg_interval_days': sum(intervals) / len(intervals) if intervals else 0,
            'event_type_distribution': type_counts,
            'importance_distribution': importance_dist,
            'activity_trend': self._calculate_activity_trend(sorted_events),
            'timeline_density': len(events) / (intervals[-1] if intervals else 1)
        }
    
    def _calculate_activity_trend(self, sorted_events: List[TimelineEvent]) -> List[Tuple[datetime, int]]:
        """计算活动趋势"""
        if not sorted_events:
            return []
        
        # 按月分组
        monthly_counts = {}
        for event in sorted_events:
            month_key = event.timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
        
        # 转换为列表
        trend = [(month, count) for month, count in sorted(monthly_counts.items())]
        return trend
    
    def compare_progressions(self, tracks: List[TimelineTrack]) -> Dict[str, Any]:
        """比较多个进展"""
        if not tracks:
            return {}
        
        comparison = {
            'track_summaries': [],
            'cross_analysis': {},
            'synchronization_points': []
        }
        
        # 各轨道分析
        for track in tracks:
            analysis = self.analyze_progression_trend(track.events)
            analysis['track_id'] = track.codex_id
            analysis['track_title'] = track.codex_title
            comparison['track_summaries'].append(analysis)
        
        # 交叉分析
        all_events = []
        for track in tracks:
            all_events.extend(track.events)
        
        if all_events:
            comparison['cross_analysis'] = {
                'total_events': len(all_events),
                'date_range': self._get_date_range(all_events),
                'correlation_matrix': self._calculate_correlation_matrix(tracks)
            }
            
            # 找到同步点
            comparison['synchronization_points'] = self._find_synchronization_points(tracks)
        
        return comparison
    
    def _get_date_range(self, events: List[TimelineEvent]) -> Tuple[datetime, datetime]:
        """获取事件的日期范围"""
        if not events:
            now = datetime.now()
            return now, now
        
        timestamps = [event.timestamp for event in events]
        return min(timestamps), max(timestamps)
    
    def _calculate_correlation_matrix(self, tracks: List[TimelineTrack]) -> Dict[str, Dict[str, float]]:
        """计算轨道间相关性矩阵"""
        # 简化实现：基于事件时间的相关性
        matrix = {}
        
        for i, track_a in enumerate(tracks):
            matrix[track_a.codex_id] = {}
            for j, track_b in enumerate(tracks):
                if i == j:
                    correlation = 1.0
                else:
                    correlation = self._calculate_temporal_correlation(track_a.events, track_b.events)
                matrix[track_a.codex_id][track_b.codex_id] = correlation
        
        return matrix
    
    def _calculate_temporal_correlation(self, events_a: List[TimelineEvent], 
                                      events_b: List[TimelineEvent]) -> float:
        """计算两个事件序列的时间相关性"""
        if not events_a or not events_b:
            return 0.0
        
        # 简化算法：计算时间窗口内的共现
        correlation_count = 0
        window = timedelta(days=7)  # 7天窗口
        
        for event_a in events_a:
            for event_b in events_b:
                if abs((event_a.timestamp - event_b.timestamp).total_seconds()) <= window.total_seconds():
                    correlation_count += 1
        
        # 归一化
        max_possible = min(len(events_a), len(events_b))
        return correlation_count / max_possible if max_possible > 0 else 0.0
    
    def _find_synchronization_points(self, tracks: List[TimelineTrack]) -> List[Dict[str, Any]]:
        """找到同步点（多个轨道同时有事件的时间点）"""
        sync_points = []
        window = timedelta(days=1)  # 1天窗口
        
        # 收集所有事件
        all_events = []
        for track in tracks:
            for event in track.events:
                all_events.append((event, track.codex_id))
        
        # 按时间排序
        all_events.sort(key=lambda x: x[0].timestamp)
        
        # 查找同步点
        i = 0
        while i < len(all_events):
            current_time = all_events[i][0].timestamp
            sync_group = []
            j = i
            
            # 收集窗口内的所有事件
            while j < len(all_events) and (all_events[j][0].timestamp - current_time) <= window:
                sync_group.append(all_events[j])
                j += 1
            
            # 如果有多个轨道参与，则为同步点
            involved_tracks = set(item[1] for item in sync_group)
            if len(involved_tracks) >= 2:
                sync_points.append({
                    'timestamp': current_time,
                    'involved_tracks': list(involved_tracks),
                    'events': [item[0] for item in sync_group],
                    'significance': len(involved_tracks) / len(tracks)
                })
            
            i = j
        
        return sync_points


class TimelineRenderer:
    """时间线渲染器"""
    
    def __init__(self):
        self.font = QFont("Arial", 10)
        self.metrics = QFontMetrics(self.font)
        
        # 样式配置
        self.colors = {
            'background': QColor("#FFFFFF"),
            'timeline_axis': QColor("#34495E"),
            'grid_major': QColor("#BDC3C7"),
            'grid_minor': QColor("#ECF0F1"),
            'text': QColor("#2C3E50"),
            'highlight': QColor("#3498DB"),
            'selection': QColor("#E74C3C")
        }
        
        self.dimensions = {
            'track_height': 40,
            'track_spacing': 10,
            'event_radius': 6,
            'timeline_margin': 50,
            'label_spacing': 20
        }
    
    def render_timeline(self, painter: QPainter, rect: QRect, 
                       tracks: List[TimelineTrack], view_range: Tuple[datetime, datetime],
                       time_scale: TimeScale = TimeScale.AUTO):
        """渲染整个时间线"""
        if not tracks or not view_range:
            return
        
        painter.setFont(self.font)
        
        # 绘制背景
        painter.fillRect(rect, self.colors['background'])
        
        # 计算布局
        timeline_rect = QRect(
            rect.x() + self.dimensions['timeline_margin'],
            rect.y() + self.dimensions['timeline_margin'],
            rect.width() - 2 * self.dimensions['timeline_margin'],
            rect.height() - 2 * self.dimensions['timeline_margin']
        )
        
        # 绘制时间轴
        self._render_time_axis(painter, timeline_rect, view_range, time_scale)
        
        # 绘制轨道
        y_offset = timeline_rect.y() + 40  # 为时间轴留空间
        for track in tracks:
            if track.visible:
                track_rect = QRect(
                    timeline_rect.x(), y_offset,
                    timeline_rect.width(), track.height
                )
                self._render_track(painter, track_rect, track, view_range)
                y_offset += track.height + self.dimensions['track_spacing']
    
    def _render_time_axis(self, painter: QPainter, rect: QRect, 
                         view_range: Tuple[datetime, datetime], time_scale: TimeScale):
        """渲染时间轴"""
        start_time, end_time = view_range
        duration = (end_time - start_time).total_seconds()
        
        if duration <= 0:
            return
        
        # 绘制主轴线
        axis_y = rect.y() + 30
        painter.setPen(QPen(self.colors['timeline_axis'], 2))
        painter.drawLine(rect.x(), axis_y, rect.right(), axis_y)
        
        # 确定时间刻度
        if time_scale == TimeScale.AUTO:
            time_scale = self._determine_auto_scale(duration)
        
        # 绘制刻度和标签
        tick_positions = self._calculate_tick_positions(start_time, end_time, time_scale, rect.width())
        
        painter.setPen(QPen(self.colors['text']))
        for pos, timestamp, is_major in tick_positions:
            x = rect.x() + pos
            
            if is_major:
                # 主刻度
                painter.drawLine(x, axis_y - 10, x, axis_y + 10)
                # 标签
                label = self._format_time_label(timestamp, time_scale)
                text_rect = self.metrics.boundingRect(label)
                painter.drawText(x - text_rect.width()//2, axis_y - 15, label)
                
                # 网格线
                painter.setPen(QPen(self.colors['grid_major'], 1, Qt.PenStyle.DotLine))
                painter.drawLine(x, rect.y(), x, rect.bottom())
                painter.setPen(QPen(self.colors['text']))
            else:
                # 次刻度
                painter.drawLine(x, axis_y - 5, x, axis_y + 5)
    
    def _render_track(self, painter: QPainter, rect: QRect, track: TimelineTrack, 
                     view_range: Tuple[datetime, datetime]):
        """渲染单个轨道"""
        start_time, end_time = view_range
        duration = (end_time - start_time).total_seconds()
        
        if duration <= 0:
            return
        
        # 绘制轨道背景
        track_bg = track.color.lighter(180)
        painter.fillRect(rect, track_bg)
        
        # 绘制轨道标签
        painter.setPen(QPen(self.colors['text']))
        label_rect = QRect(5, rect.y(), self.dimensions['timeline_margin'] - 10, rect.height())
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, 
                        track.codex_title)
        
        # 绘制事件
        events_in_range = track.get_events_in_range(start_time, end_time)
        for event in events_in_range:
            self._render_event(painter, rect, event, start_time, duration)
    
    def _render_event(self, painter: QPainter, track_rect: QRect, event: TimelineEvent,
                     start_time: datetime, duration: float):
        """渲染单个事件"""
        # 计算事件位置
        event_offset = (event.timestamp - start_time).total_seconds()
        x_ratio = event_offset / duration if duration > 0 else 0
        x = track_rect.x() + x_ratio * track_rect.width()
        y = track_rect.center().y()
        
        # 绘制事件点
        radius = self.dimensions['event_radius']
        painter.setBrush(QBrush(event.color))
        painter.setPen(QPen(event.color.darker(120), 2))
        painter.drawEllipse(QPointF(x, y), radius, radius)
        
        # 绘制重要程度指示
        if event.importance > 3:
            # 高重要程度用较大的圆圈
            painter.setPen(QPen(event.color, 3))
            painter.setBrush(QBrush())  # 透明填充
            painter.drawEllipse(QPointF(x, y), radius + 3, radius + 3)
        
        # 绘制图标（如果空间足够）
        if track_rect.width() > 200:  # 只在足够宽时显示图标
            icon_rect = QRect(x - 8, y - 20, 16, 16)
            painter.setPen(QPen(self.colors['text']))
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, event.icon)
    
    def _determine_auto_scale(self, duration_seconds: float) -> TimeScale:
        """自动确定时间刻度"""
        days = duration_seconds / 86400
        
        if days <= 7:
            return TimeScale.DAYS
        elif days <= 60:
            return TimeScale.WEEKS
        elif days <= 730:
            return TimeScale.MONTHS
        else:
            return TimeScale.YEARS
    
    def _calculate_tick_positions(self, start_time: datetime, end_time: datetime,
                                 time_scale: TimeScale, width: int) -> List[Tuple[float, datetime, bool]]:
        """计算刻度位置"""
        positions = []
        duration = (end_time - start_time).total_seconds()
        
        if duration <= 0:
            return positions
        
        # 根据时间刻度确定间隔
        if time_scale == TimeScale.DAYS:
            delta = timedelta(days=1)
            minor_delta = timedelta(hours=6)
        elif time_scale == TimeScale.WEEKS:
            delta = timedelta(weeks=1)
            minor_delta = timedelta(days=1)
        elif time_scale == TimeScale.MONTHS:
            delta = timedelta(days=30)
            minor_delta = timedelta(weeks=1)
        else:  # YEARS
            delta = timedelta(days=365)
            minor_delta = timedelta(days=30)
        
        # 生成主刻度
        current = start_time
        while current <= end_time:
            offset = (current - start_time).total_seconds()
            pos = (offset / duration) * width
            positions.append((pos, current, True))
            current += delta
        
        # 生成次刻度（简化版本）
        current = start_time
        while current <= end_time:
            offset = (current - start_time).total_seconds()
            pos = (offset / duration) * width
            # 只有当不与主刻度重叠时才添加次刻度
            if not any(abs(pos - p[0]) < 5 for p in positions):
                positions.append((pos, current, False))
            current += minor_delta
        
        return sorted(positions, key=lambda x: x[0])
    
    def _format_time_label(self, timestamp: datetime, time_scale: TimeScale) -> str:
        """格式化时间标签"""
        if time_scale == TimeScale.DAYS:
            return timestamp.strftime("%m-%d")
        elif time_scale == TimeScale.WEEKS:
            return timestamp.strftime("%m-%d")
        elif time_scale == TimeScale.MONTHS:
            return timestamp.strftime("%Y-%m")
        else:  # YEARS
            return timestamp.strftime("%Y")


class TimelineEngine(QObject):
    """时间线引擎 - 核心控制器"""
    
    # 信号定义
    dataChanged = pyqtSignal()
    viewRangeChanged = pyqtSignal(datetime, datetime)
    eventSelected = pyqtSignal(str)  # event_id
    trackToggled = pyqtSignal(str, bool)  # codex_id, visible
    
    def __init__(self, codex_manager=None):
        super().__init__()
        
        self.codex_manager = codex_manager
        self.tracks: Dict[str, TimelineTrack] = {}
        self.analyzer = TimelineAnalyzer()
        self.renderer = TimelineRenderer()
        
        # 视图状态
        self.view_mode = TimelineViewMode.CHRONOLOGICAL
        self.time_scale = TimeScale.AUTO
        self.view_range: Optional[Tuple[datetime, datetime]] = None
        self.selected_event_id: Optional[str] = None
        
        logger.info("Timeline engine initialized")
    
    def load_progression_data(self):
        """加载进展数据"""
        if not self.codex_manager:
            return
        
        try:
            self.tracks.clear()
            
            # 获取所有有进展的条目
            entries = self.codex_manager.get_all_entries()
            
            for entry in entries:
                if entry.progression:
                    track = TimelineTrack(
                        codex_id=entry.id,
                        codex_title=entry.title,
                        codex_type=entry.entry_type.value,
                        color=self._get_track_color(entry.entry_type.value)
                    )
                    
                    # 转换进展数据为事件
                    for i, prog_data in enumerate(entry.progression):
                        event = self._create_event_from_progression(entry.id, prog_data, i)
                        track.events.append(event)
                    
                    # 按时间排序
                    track.events.sort(key=lambda e: e.timestamp)
                    
                    self.tracks[entry.id] = track
            
            # 自动计算视图范围
            self._auto_calculate_view_range()
            
            self.dataChanged.emit()
            logger.info(f"Loaded {len(self.tracks)} timeline tracks")
            
        except Exception as e:
            logger.error(f"Failed to load progression data: {e}")
    
    def _create_event_from_progression(self, codex_id: str, prog_data: Dict, index: int) -> TimelineEvent:
        """从进展数据创建事件"""
        # 解析时间戳
        timestamp_str = prog_data.get('date', '')
        try:
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.now() - timedelta(days=index)  # 默认时间
        except:
            timestamp = datetime.now() - timedelta(days=index)
        
        # 确定事件类型
        title = prog_data.get('title', f'事件 {index + 1}')
        event_type = self._infer_event_type(title, prog_data.get('description', ''))
        
        return TimelineEvent(
            id=f"{codex_id}_prog_{index}",
            codex_id=codex_id,
            title=title,
            description=prog_data.get('description', ''),
            event_type=event_type,
            timestamp=timestamp,
            chapter_id=prog_data.get('chapter', ''),
            importance=self._calculate_importance(prog_data),
            metadata=prog_data
        )
    
    def _infer_event_type(self, title: str, description: str) -> EventType:
        """推断事件类型"""
        text = (title + " " + description).lower()
        
        if any(word in text for word in ['创建', '诞生', '建立', '初始']):
            return EventType.CREATION
        elif any(word in text for word in ['冲突', '战斗', '争执', '矛盾']):
            return EventType.CONFLICT
        elif any(word in text for word in ['解决', '完成', '达成', '成功']):
            return EventType.RESOLUTION
        elif any(word in text for word in ['关系', '结识', '相遇', '联盟']):
            return EventType.RELATIONSHIP
        elif any(word in text for word in ['里程碑', '重要', '转折', '关键']):
            return EventType.MILESTONE
        else:
            return EventType.DEVELOPMENT
    
    def _calculate_importance(self, prog_data: Dict) -> int:
        """计算重要程度"""
        # 基于描述长度和关键词确定重要程度
        description = prog_data.get('description', '')
        title = prog_data.get('title', '')
        
        importance = 3  # 默认中等重要
        
        # 基于长度调整
        if len(description) > 100:
            importance += 1
        elif len(description) < 20:
            importance -= 1
        
        # 基于关键词调整
        text = (title + " " + description).lower()
        if any(word in text for word in ['重要', '关键', '转折', '里程碑']):
            importance += 1
        elif any(word in text for word in ['微小', '轻微', '普通']):
            importance -= 1
        
        return max(1, min(5, importance))
    
    def _get_track_color(self, entry_type: str) -> QColor:
        """获取轨道颜色"""
        color_map = {
            'CHARACTER': QColor("#3498DB"),
            'LOCATION': QColor("#2ECC71"),
            'OBJECT': QColor("#F39C12"),
            'LORE': QColor("#9B59B6"),
            'SUBPLOT': QColor("#E74C3C"),
            'OTHER': QColor("#95A5A6")
        }
        return color_map.get(entry_type, QColor("#95A5A6"))
    
    def _auto_calculate_view_range(self):
        """自动计算视图范围"""
        if not self.tracks:
            return
        
        all_events = []
        for track in self.tracks.values():
            all_events.extend(track.events)
        
        if all_events:
            timestamps = [event.timestamp for event in all_events]
            start_time = min(timestamps)
            end_time = max(timestamps)
            
            # 添加一些边距
            margin = (end_time - start_time).total_seconds() * 0.1
            margin_delta = timedelta(seconds=max(margin, 86400))  # 至少1天
            
            self.view_range = (start_time - margin_delta, end_time + margin_delta)
            self.viewRangeChanged.emit(*self.view_range)
    
    # 公共接口
    def set_view_mode(self, mode: TimelineViewMode):
        """设置视图模式"""
        self.view_mode = mode
        self.dataChanged.emit()
    
    def set_time_scale(self, scale: TimeScale):
        """设置时间刻度"""
        self.time_scale = scale
        self.dataChanged.emit()
    
    def set_view_range(self, start_time: datetime, end_time: datetime):
        """设置视图范围"""
        self.view_range = (start_time, end_time)
        self.viewRangeChanged.emit(start_time, end_time)
        self.dataChanged.emit()
    
    def toggle_track_visibility(self, codex_id: str, visible: bool):
        """切换轨道可见性"""
        if codex_id in self.tracks:
            self.tracks[codex_id].visible = visible
            self.trackToggled.emit(codex_id, visible)
            self.dataChanged.emit()
    
    def select_event(self, event_id: str):
        """选择事件"""
        self.selected_event_id = event_id
        self.eventSelected.emit(event_id)
        self.dataChanged.emit()
    
    def get_analysis(self) -> Dict[str, Any]:
        """获取分析结果"""
        visible_tracks = [track for track in self.tracks.values() if track.visible]
        return self.analyzer.compare_progressions(visible_tracks)
    
    def export_timeline_data(self) -> Dict[str, Any]:
        """导出时间线数据"""
        export_data = {
            'tracks': [],
            'view_range': self.view_range,
            'analysis': self.get_analysis(),
            'export_timestamp': datetime.now().isoformat()
        }
        
        for track in self.tracks.values():
            track_data = {
                'codex_id': track.codex_id,
                'codex_title': track.codex_title,
                'codex_type': track.codex_type,
                'visible': track.visible,
                'events': []
            }
            
            for event in track.events:
                event_data = {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'type': event.event_type.value,
                    'timestamp': event.timestamp.isoformat(),
                    'importance': event.importance,
                    'chapter_id': event.chapter_id,
                    'tags': event.tags,
                    'metadata': event.metadata
                }
                track_data['events'].append(event_data)
            
            export_data['tracks'].append(track_data)
        
        return export_data