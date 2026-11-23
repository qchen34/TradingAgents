# WebUI 区域命名（沟通用语）

便于产品 / 设计 / 开发对齐，不绑定 Streamlit 内部 `testid`。

| 名称 | 英文 | 说明 |
|------|------|------|
| **主画布** | AppCanvas | 整页底层，含 `.stApp` 的深色底 + 紫/青径向扫光。 |
| **导航轨** | NavRail | 左侧固定栏容器（`st.sidebar` 区域），底色略深于主画布，右侧细边与主区衔接。 |
| **主导航** | NavMenu | `streamlit-option-menu`：图标 + 文案 + 圆角选中态。 |
| **工作区** | WorkPane | 主栏 `.main .block-container`，各页面内容区。 |

可调参数见 `web/ui_shell.py`（侧栏宽度、导航色）。样式主入口：`web/theme.py` 的 `apply_theme()`。
