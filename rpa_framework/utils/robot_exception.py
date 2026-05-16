class RobotsException(Exception):
    """RPA机器人相关自定义异常"""
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message
    
    def __str__(self):
        # if self.original_exception:
        #     return f"{self.message} : {str(self.original_exception)}"
        return self.message
    
    def get_full_message(self):
        """获取完整的错误信息"""
        if self.original_exception:
            return f"{self.message} : {str(self.original_exception)}"
        return self.message 