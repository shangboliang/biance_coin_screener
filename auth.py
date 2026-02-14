# """
# @author beck
# Authentication module for Streamlit Web Dashboard
# Web界面访问控制模块
# """
# import os
# import hashlib
# import hmac
# import streamlit as st
# from typing import Optional
# from datetime import datetime, timedelta
#
#
# class WebAuthenticator:
#     """Web界面认证器"""
#
#     def __init__(self):
#         """初始化认证器"""
#         self.password_hash = self._get_password_hash()
#         self.session_timeout = int(os.getenv("WEB_SESSION_TIMEOUT", "3600"))  # 默认1小时
#
#     def _get_password_hash(self) -> Optional[str]:
#         """获取密码哈希值"""
#         password = os.getenv("WEB_PASSWORD", "")
#         if not password:
#             return None
#         # 使用SHA256哈希
#         return hashlib.sha256(password.encode()).hexdigest()
#
#     def _verify_password(self, password: str) -> bool:
#         """验证密码"""
#         if not self.password_hash:
#             # 如果未设置密码，默认允许访问（开发模式）
#             return True
#
#         input_hash = hashlib.sha256(password.encode()).hexdigest()
#         # 使用恒定时间比较，防止时序攻击
#         return hmac.compare_digest(input_hash, self.password_hash)
#
#     def _is_session_valid(self) -> bool:
#         """检查会话是否有效"""
#         if "authenticated" not in st.session_state:
#             return False
#
#         if "auth_time" not in st.session_state:
#             return False
#
#         # 检查会话是否超时
#         auth_time = st.session_state["auth_time"]
#         elapsed = (datetime.now() - auth_time).total_seconds()
#
#         if elapsed > self.session_timeout:
#             # 会话超时
#             self._logout()
#             return False
#
#         return st.session_state["authenticated"]
#
#     def _login(self, password: str) -> bool:
#         """登录"""
#         if self._verify_password(password):
#             st.session_state["authenticated"] = True
#             st.session_state["auth_time"] = datetime.now()
#             st.session_state["login_attempts"] = 0
#             return True
#         else:
#             # 记录失败尝试
#             if "login_attempts" not in st.session_state:
#                 st.session_state["login_attempts"] = 0
#             st.session_state["login_attempts"] += 1
#             return False
#
#     def _logout(self):
#         """登出"""
#         st.session_state["authenticated"] = False
#         if "auth_time" in st.session_state:
#             del st.session_state["auth_time"]
#
#     def _show_login_page(self):
#         """显示登录页面"""
#         st.markdown("""
#         <style>
#         .login-container {
#             max-width: 400px;
#             margin: 100px auto;
#             padding: 40px;
#             background-color: #f0f2f6;
#             border-radius: 10px;
#             box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
#         }
#         </style>
#         """, unsafe_allow_html=True)
#
#         col1, col2, col3 = st.columns([1, 2, 1])
#
#         with col2:
#             st.markdown("### 🔐 币安POC监控工具")
#             st.markdown("---")
#
#             # 显示登录表单
#             with st.form("login_form"):
#                 password = st.text_input("请输入访问密码", type="password", key="password_input")
#                 submit = st.form_submit_button("登录", use_container_width=True)
#
#                 if submit:
#                     if password:
#                         if self._login(password):
#                             st.success("✓ 登录成功！")
#                             st.rerun()
#                         else:
#                             attempts = st.session_state.get("login_attempts", 0)
#                             st.error(f"✗ 密码错误 (尝试次数: {attempts})")
#
#                             # 防暴力破解：超过5次失败后显示警告
#                             if attempts >= 5:
#                                 st.warning("⚠️ 多次登录失败，请确认密码是否正确")
#                     else:
#                         st.warning("请输入密码")
#
#             # 显示提示信息
#             st.markdown("---")
#             # st.info("💡 **默认密码**: `beck`")
#             # st.caption("建议：首次登录后请通过环境变量 WEB_PASSWORD 修改密码")
#
#     def require_authentication(self) -> bool:
#         """
#         要求认证，返回是否已认证
#
#         使用方法：
#         ```python
#         auth = WebAuthenticator()
#         if not auth.require_authentication():
#             st.stop()
#         ```
#         """
#         # 检查会话是否有效
#         if self._is_session_valid():
#             # 显示登出按钮（在侧边栏）
#             with st.sidebar:
#                 st.markdown("---")
#                 auth_time = st.session_state.get("auth_time")
#                 if auth_time:
#                     elapsed = int((datetime.now() - auth_time).total_seconds() / 60)
#                     remaining = int((self.session_timeout - elapsed * 60) / 60)
#                     st.caption(f"🔓 已登录 | 会话剩余: {remaining}分钟")
#
#                 if st.button("🚪 登出", use_container_width=True):
#                     self._logout()
#                     st.rerun()
#
#             return True
#         else:
#             # 显示登录页面
#             self._show_login_page()
#             return False
#
#
# def check_ip_whitelist() -> bool:
#     """
#     检查IP白名单（可选功能）
#
#     在环境变量中设置 IP_WHITELIST，格式：192.168.1.1,10.0.0.1
#     如果未设置，则不进行IP限制
#     """
#     whitelist = os.getenv("IP_WHITELIST", "")
#     if not whitelist:
#         return True
#
#     # 获取客户端IP（Streamlit Cloud环境）
#     # 注意：本地运行时可能无法获取真实IP
#     try:
#         import streamlit.web.server.websocket_headers as ws_headers
#         client_ip = ws_headers.get_websocket_headers().get("X-Forwarded-For", "")
#
#         allowed_ips = [ip.strip() for ip in whitelist.split(",")]
#         return client_ip in allowed_ips
#     except:
#         # 如果无法获取IP，默认允许（避免锁死）
#         return True
#
#
# def get_rate_limiter():
#     """
#     获取速率限制器（防止暴力破解）
#
#     TODO: 可以使用Redis或内存缓存实现更强大的速率限制
#     """
#     if "rate_limit" not in st.session_state:
#         st.session_state["rate_limit"] = {
#             "attempts": 0,
#             "last_attempt": datetime.now()
#         }
#
#     rate_limit = st.session_state["rate_limit"]
#
#     # 重置计数器（每小时）
#     if (datetime.now() - rate_limit["last_attempt"]).total_seconds() > 3600:
#         rate_limit["attempts"] = 0
#
#     return rate_limit
