import json
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.system_setting import SystemSetting
from app.db.session import SessionLocal

# 哨兵值，用于区分 "配置不存在" 和 "配置值为 None/null"
NOT_FOUND = object()

class SettingsService:
    @staticmethod
    def _convert_value(value: str, value_type: str) -> Any:
        if value_type == "int":
            return int(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "float":
            return float(value)
        elif value_type == "json":
            return json.loads(value)
        return value  # default to string

    @staticmethod
    def _format_value(value: Any, value_type: str) -> str:
        if value_type == "json":
            return json.dumps(value)
        if value_type == "bool":
            return "true" if value else "false"
        return str(value)

    @classmethod
    def get_setting(cls, db: Session, group_name: str, key: str, default: Any = None) -> Any:
        """
        获取单个配置项。
        如果配置不存在，返回 default（默认为 None）。
        建议使用 NOT_FOUND 哨兵值区分 "不存在" 和 "值为 None"。
        """
        setting = db.query(SystemSetting).filter_by(group_name=group_name, key=key).first()
        if not setting:
            return default
        return cls._convert_value(setting.value, setting.value_type)

    @classmethod
    def get_settings_by_group(cls, db: Session, group_name: str) -> Dict[str, Any]:
        settings = db.query(SystemSetting).filter_by(group_name=group_name).all()
        return {s.key: cls._convert_value(s.value, s.value_type) for s in settings}

    @classmethod
    def set_setting(
        cls, 
        db: Session, 
        group_name: str, 
        key: str, 
        value: Any, 
        value_type: Optional[str] = None,
        description: Optional[str] = None
    ) -> SystemSetting:
        setting = db.query(SystemSetting).filter_by(group_name=group_name, key=key).first()
        
        # If value_type not provided, try to infer it if setting doesn't exist
        if not value_type:
            if setting:
                value_type = setting.value_type
            else:
                if isinstance(value, bool): value_type = "bool"
                elif isinstance(value, int): value_type = "int"
                elif isinstance(value, float): value_type = "float"
                elif isinstance(value, (dict, list)): value_type = "json"
                else: value_type = "string"

        formatted_value = cls._format_value(value, value_type)

        if setting:
            setting.value = formatted_value
            setting.value_type = value_type
            if description:
                setting.description = description
        else:
            setting = SystemSetting(
                group_name=group_name,
                key=key,
                value=formatted_value,
                value_type=value_type,
                description=description
            )
            db.add(setting)
        
        db.commit()
        db.refresh(setting)
        return setting

    @classmethod
    def initialize_defaults(cls):
        """Initialize default settings if they don't exist."""
        db = SessionLocal()
        try:
            defaults = [
                ("session", "passive_timeout", 1800, "int", "会话判定过期的非活跃时长 (秒)"),
            ]
            for group, key, val, vtype, desc in defaults:
                try:
                    # 直接尝试插入，利用唯一约束判断是否已存在
                    existing = db.query(SystemSetting).filter_by(group_name=group, key=key).first()
                    if not existing:
                        cls.set_setting(db, group, key, val, vtype, desc)
                except IntegrityError:
                    # 并发场景下可能有竞态，忽略
                    db.rollback()
        finally:
            db.close()
