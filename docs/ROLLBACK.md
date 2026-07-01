# 回滚预案 (Rollback Plan)

## 触发条件
- 测试通过率 < 100%
- 核心分句功能失败
- 安装报错

## 回滚命令
```bash
git tag -l                    # 查看可用版本
git checkout v0.5.0           # 回滚到上一版本
pip install -e .              # 重新安装
python -m pytest tests/       # 验证
```

## 检查清单
- [ ] 确认回滚版本号
- [ ] 执行回滚命令
- [ ] 运行测试验证
- [ ] 通知相关方
- [ ] 记录回滚原因
