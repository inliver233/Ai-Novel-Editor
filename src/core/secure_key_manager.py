"""
安全密钥管理器 - 处理API密钥的加密存储和访问
"""

import os
import json
import base64
import platform
from typing import Optional, Dict, Any
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger


class SecureKeyManager:
    """
    安全密钥管理器，使用操作系统特定的密钥存储机制
    """
    
    def __init__(self, app_name: str = "AI-Novel-Editor"):
        self.app_name = app_name
        self.system = platform.system()
        self._cipher_suite = None
        self._init_encryption()
        
    def _init_encryption(self):
        """初始化加密系统"""
        # 获取或生成机器特定的密钥
        machine_key = self._get_machine_specific_key()
        
        # 使用PBKDF2从机器密钥派生加密密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'ai-novel-editor-salt',  # 固定盐值
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_key.encode()))
        self._cipher_suite = Fernet(key)
        
    def _get_machine_specific_key(self) -> str:
        """
        获取机器特定的密钥，用于派生加密密钥
        """
        if self.system == "Windows":
            # Windows：使用机器GUID
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Cryptography") as key:
                    machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                    return machine_guid
            except Exception as e:
                logger.warning(f"无法获取Windows机器GUID: {e}")
                
        elif self.system == "Darwin":  # macOS
            # macOS：使用硬件UUID
            try:
                import subprocess
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'IOPlatformUUID' in line:
                            uuid = line.split('"')[3]
                            return uuid
            except Exception as e:
                logger.warning(f"无法获取macOS硬件UUID: {e}")
                
        elif self.system == "Linux":
            # Linux：使用机器ID
            try:
                with open("/etc/machine-id", "r") as f:
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"无法获取Linux机器ID: {e}")
        
        # 后备方案：使用用户目录和应用名称的组合
        fallback_key = f"{os.path.expanduser('~')}-{self.app_name}-fallback"
        logger.warning("使用后备密钥方案")
        return fallback_key
    
    def encrypt_api_key(self, api_key: str) -> str:
        """
        加密API密钥
        
        Args:
            api_key: 明文API密钥
            
        Returns:
            加密后的API密钥（base64编码）
        """
        if not api_key:
            return ""
        
        try:
            encrypted = self._cipher_suite.encrypt(api_key.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"加密API密钥失败: {e}")
            return ""
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        解密API密钥
        
        Args:
            encrypted_key: 加密的API密钥（base64编码）
            
        Returns:
            解密后的明文API密钥
        """
        if not encrypted_key:
            return ""
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted = self._cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"解密API密钥失败: {e}")
            return ""
    
    def store_api_key(self, provider: str, api_key: str) -> bool:
        """
        安全存储API密钥
        
        Args:
            provider: 提供商名称（如 'openai', 'claude' 等）
            api_key: 明文API密钥
            
        Returns:
            是否存储成功
        """
        try:
            # 加密API密钥
            encrypted_key = self.encrypt_api_key(api_key)
            
            # 获取密钥存储路径
            key_store_path = self._get_key_store_path()
            
            # 读取现有密钥
            if key_store_path.exists():
                with open(key_store_path, 'r', encoding='utf-8') as f:
                    key_store = json.load(f)
            else:
                key_store = {}
            
            # 更新密钥
            key_store[provider] = encrypted_key
            
            # 保存密钥（设置适当的文件权限）
            key_store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(key_store_path, 'w', encoding='utf-8') as f:
                json.dump(key_store, f, indent=2)
            
            # 设置文件权限（仅限所有者读写）
            if self.system != "Windows":
                os.chmod(key_store_path, 0o600)
            
            logger.info(f"已安全存储 {provider} 的API密钥")
            return True
            
        except Exception as e:
            logger.error(f"存储API密钥失败: {e}")
            return False
    
    def retrieve_api_key(self, provider: str) -> Optional[str]:
        """
        获取存储的API密钥
        
        Args:
            provider: 提供商名称
            
        Returns:
            解密后的API密钥，如果不存在则返回None
        """
        try:
            key_store_path = self._get_key_store_path()
            
            if not key_store_path.exists():
                return None
            
            with open(key_store_path, 'r', encoding='utf-8') as f:
                key_store = json.load(f)
            
            encrypted_key = key_store.get(provider)
            if not encrypted_key:
                return None
            
            return self.decrypt_api_key(encrypted_key)
            
        except Exception as e:
            logger.error(f"获取API密钥失败: {e}")
            return None
    
    def remove_api_key(self, provider: str) -> bool:
        """
        删除存储的API密钥
        
        Args:
            provider: 提供商名称
            
        Returns:
            是否删除成功
        """
        try:
            key_store_path = self._get_key_store_path()
            
            if not key_store_path.exists():
                return True
            
            with open(key_store_path, 'r', encoding='utf-8') as f:
                key_store = json.load(f)
            
            if provider in key_store:
                del key_store[provider]
                
                with open(key_store_path, 'w', encoding='utf-8') as f:
                    json.dump(key_store, f, indent=2)
                
                logger.info(f"已删除 {provider} 的API密钥")
            
            return True
            
        except Exception as e:
            logger.error(f"删除API密钥失败: {e}")
            return False
    
    def _get_key_store_path(self) -> Path:
        """获取密钥存储文件路径"""
        if self.system == "Windows":
            base_dir = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
        else:
            base_dir = Path(os.path.expanduser('~/.config'))
        
        return base_dir / self.app_name / "secure" / "api_keys.json"
    
    def migrate_plaintext_keys(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从明文配置迁移API密钥到安全存储
        
        Args:
            config: 包含明文API密钥的配置字典
            
        Returns:
            移除API密钥后的配置字典
        """
        updated_config = config.copy()
        providers_to_check = ['openai', 'claude', 'qwen', 'zhipu', 'deepseek', 'groq', 'custom']
        
        for provider in providers_to_check:
            provider_config = updated_config.get('ai', {}).get(provider, {})
            if 'api_key' in provider_config and provider_config['api_key']:
                # 存储到安全存储
                self.store_api_key(provider, provider_config['api_key'])
                # 从配置中移除明文密钥
                provider_config['api_key'] = ""
                logger.info(f"已迁移 {provider} 的API密钥到安全存储")
        
        return updated_config


# 单例实例
_secure_key_manager = None


def get_secure_key_manager() -> SecureKeyManager:
    """获取安全密钥管理器的单例实例"""
    global _secure_key_manager
    if _secure_key_manager is None:
        _secure_key_manager = SecureKeyManager()
    return _secure_key_manager