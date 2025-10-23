"""
密码加密器

提供密码加密和解密功能
"""

import base64
from rpa_framework.utils.log import logger


class Encryptor:
    """简化的密码加密器"""
    
    def __init__(self, password: str = "RPA_DEFAULT_KEY"):
        """
        初始化加密器
        :param password: 主密码
        """
        self.password = password
        logger.debug("密码加密器初始化完成")
    
    def encrypt(self, text: str) -> str:
        """
        加密文本（使用简单的Base64编码）
        :param text: 要加密的文本
        :return: 加密后的文本
        """
        try:
            # 简单的异或加密 + Base64编码
            key_bytes = self.password.encode()
            text_bytes = text.encode()
            
            # 异或加密
            encrypted_bytes = bytes(
                text_bytes[i] ^ key_bytes[i % len(key_bytes)] 
                for i in range(len(text_bytes))
            )
            
            # Base64编码
            return base64.b64encode(encrypted_bytes).decode()
        except Exception as e:
            logger.error(f"加密失败: {str(e)}")
            raise Exception(f"加密失败: {str(e)}")
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        解密文本
        :param encrypted_text: 要解密的文本
        :return: 解密后的原始文本
        """
        try:
            # Base64解码
            encrypted_bytes = base64.b64decode(encrypted_text.encode())
            
            # 异或解密
            key_bytes = self.password.encode()
            decrypted_bytes = bytes(
                encrypted_bytes[i] ^ key_bytes[i % len(key_bytes)] 
                for i in range(len(encrypted_bytes))
            )
            
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"解密失败: {str(e)}")
            raise Exception(f"解密失败: {str(e)}")

# 使用示例
if __name__ == "__main__":
    # 创建加密器实例
    encryptor = Encryptor()
    
    # 测试不同长度的密码
    test_passwords = [
        "Cwzt@2025"
    ]
    
    print("密码长度比较：")
    print("-" * 50)
    print(f"{'原始密码':<30} {'原始长度':<10} {'加密后长度':<10} {'长度增加':<10}")
    print("-" * 50)
    
    for password in test_passwords:
        encrypted = encryptor.encrypt(password)
        original_len = len(password)
        encrypted_len = len(encrypted)
        increase = encrypted_len - original_len
        
        print(f"{password:<30} {original_len:<10} {encrypted_len:<10} {increase:<10}")
    
    print("-" * 50)
    print("\n加密解密测试：")
    for password in test_passwords:
        encrypted = encryptor.encrypt(password)
        decrypted = encryptor.decrypt(encrypted)
        print(f"原始密码: {password}")
        print(f"加密后: {encrypted}")
        print(f"解密后: {decrypted}")
        print(f"验证: {'成功' if decrypted == password else '失败'}")
        print("-" * 30) 