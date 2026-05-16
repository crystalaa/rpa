CREATE TABLE work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键ID
    work_order_number TEXT NOT NULL UNIQUE,  -- 工单编号
    status TEXT,  -- 工单状态（待接单/处理中等）
    process_status TEXT,  -- 处理状态（新增字段，用于细化工单处理进度）
    reporter TEXT,  -- 报修人
    title TEXT,  -- 工单标题
    content TEXT,  -- 内容
    company TEXT,  -- 单位
    department TEXT,  -- 部门
    operation_group TEXT,  -- 运维组
    operator TEXT,  -- 运维人
    acceptor TEXT,  -- 受理人
    is_key_supervision TEXT,  -- 重点督办（是/否）
    report_time TEXT,  -- 报修时间
    urgency_level TEXT,  -- 紧急程度
    source TEXT,  -- 工单来源
    work_order_type TEXT,  -- 工单类型
    process_time TEXT,  -- 处理时间
    callback_time TEXT,  -- 回访时间
    evaluation_type TEXT,  -- 评价类型
    callback_person TEXT,  -- 回访人
    is_callback TEXT,  -- 是否回访（是/否）
    user_evaluation TEXT,  -- 用户评价（ICS）
    archive_status TEXT,  -- 归档（ICS）
    is_contact_user TEXT,  -- 是否联系用户（是/否）
    is_resolved TEXT,  -- 是否已解决（是/否）
    archiver TEXT,  -- 归档人
    archive_content TEXT,  -- 归档内容
    is_workday_calculated TEXT,  -- 是否计算工作日（是/否）
    operations TEXT,  -- 操作（详情、需求转换、处理等）
    attachment TEXT,  -- 附件
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- 创建索引以提高查询性能
CREATE INDEX idx_work_order_number ON work_orders(work_order_number);  -- 工单编号索引
CREATE INDEX idx_status ON work_orders(status);  -- 工单状态索引
CREATE INDEX idx_process_status ON work_orders(process_status);  -- 处理状态索引（新增）
CREATE INDEX idx_reporter ON work_orders(reporter);  -- 报修人索引
CREATE INDEX idx_company ON work_orders(company);  -- 单位索引
CREATE INDEX idx_department ON work_orders(department);  -- 部门索引
CREATE INDEX idx_operation_group ON work_orders(operation_group);  -- 运维组索引
CREATE INDEX idx_report_time ON work_orders(report_time);  -- 报修时间索引

