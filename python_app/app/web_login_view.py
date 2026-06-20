"""Web-based login view using QWebEngineView.

Replaces the widget-based LoginView when web UI is enabled.
Loads the React login page and communicates via QWebChannel.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    HAS_WEB_ENGINE = True
except ImportError:
    HAS_WEB_ENGINE = False


class WebLoginBridge(QWidget):
    """Bridge for login communication between React and Python."""

    # Signal emitted on successful authentication
    authenticated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auth_client = None
        self._token_store = None
        self._license_gate = None

    def set_auth_services(self, auth_client, token_store, license_gate):
        self._auth_client = auth_client
        self._token_store = token_store
        self._license_gate = license_gate

    def login(self, email: str, password: str) -> str:
        """Authenticate user. Called from React."""
        import json
        try:
            if not self._auth_client:
                return json.dumps({"error": "Auth services not available"})

            tokens = self._auth_client.login(email, password)
            self._token_store.save(tokens.access_token, tokens.refresh_token)

            if self._license_gate:
                self._license_gate.validate(tokens.access_token)

            self.authenticated.emit()
            return json.dumps({"status": "ok"})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def register(self, email: str, password: str, display_name: str) -> str:
        """Register new user. Called from React."""
        import json
        try:
            if not self._auth_client:
                return json.dumps({"error": "Auth services not available"})

            self._auth_client.register(email, password, display_name)
            return json.dumps({"status": "ok"})
        except Exception as exc:
            return json.dumps({"error": str(exc)})


class WebLoginView(QWidget):
    """Web-based login view using QWebEngineView."""

    # Signal emitted on successful authentication
    authenticated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not HAS_WEB_ENGINE:
            # Fallback: show error message
            from PyQt6.QtWidgets import QLabel
            label = QLabel("QWebEngineView not available. Install PyQt6-WebEngine.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Setup bridge
        self.bridge = WebLoginBridge()
        self.web_channel = QWebChannel()
        self.web_channel.registerObject("python", self.bridge)
        self.web_view.page().setWebChannel(self.web_channel)

        # Connect auth signal
        self.bridge.authenticated.connect(self.authenticated.emit)

        # Load the React login page
        self._load_login_page()

    def _load_login_page(self):
        """Load the React login page."""
        # Try to load from web/dist first
        web_dist = Path(__file__).parent.parent / "web" / "dist" / "index.html"
        if web_dist.exists():
            self.web_view.setUrl(QUrl.fromLocalFile(str(web_dist)))
            return

        # Fallback: load a simple login page
        self.web_view.setHtml(self._fallback_login_html())

    def _fallback_login_html(self) -> str:
        """Fallback login HTML when React app is not built."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    background: #0a0e27;
                    color: #eef4ff;
                    display: flex;
                    height: 100vh;
                }
                .brand {
                    flex: 1;
                    background: linear-gradient(135deg, #4c1d95, #6d28d9, #a855f7);
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 40px;
                }
                .brand h1 { font-size: 36px; margin-bottom: 16px; }
                .brand p { font-size: 18px; opacity: 0.8; text-align: center; max-width: 400px; }
                .form-panel {
                    width: 480px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 40px;
                }
                .form-container { width: 100%; max-width: 380px; }
                h2 { font-size: 24px; margin-bottom: 8px; }
                .subtitle { color: #8ea4c7; margin-bottom: 24px; }
                .tabs {
                    display: flex;
                    gap: 4px;
                    background: #0f1538;
                    padding: 4px;
                    border-radius: 8px;
                    margin-bottom: 24px;
                }
                .tab {
                    flex: 1;
                    padding: 8px;
                    text-align: center;
                    border: none;
                    background: transparent;
                    color: #8ea4c7;
                    cursor: pointer;
                    border-radius: 6px;
                    font-size: 14px;
                }
                .tab.active { background: #1e2548; color: #eef4ff; }
                .form-group { margin-bottom: 16px; }
                .form-group label {
                    display: block;
                    margin-bottom: 6px;
                    font-size: 14px;
                    font-weight: 500;
                }
                input {
                    width: 100%;
                    padding: 10px 12px;
                    border: 1px solid #27354b;
                    background: #0f1538;
                    color: #eef4ff;
                    border-radius: 6px;
                    font-size: 14px;
                }
                input:focus { outline: none; border-color: #00d4ff; }
                button.submit {
                    width: 100%;
                    padding: 10px;
                    background: linear-gradient(135deg, #7c3aed, #a855f7);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                    cursor: pointer;
                }
                button.submit:hover { opacity: 0.9; }
                .error { color: #ef4444; font-size: 13px; margin-top: 8px; }
            </style>
        </head>
        <body>
            <div class="brand">
                <div style="font-size: 48px; margin-bottom: 24px;">⚡</div>
                <h1>CAMXORA</h1>
                <p>Create studio-grade music videos, automatically.</p>
                <div style="margin-top: 40px; text-align: left; color: white;">
                    <p style="margin: 12px 0;">🎵 AI-powered song generation</p>
                    <p style="margin: 12px 0;">🎬 Spectrum video rendering</p>
                    <p style="margin: 12px 0;">🔄 Batch pipelines & auto-upload</p>
                </div>
            </div>
            <div class="form-panel">
                <div class="form-container">
                    <h2>Welcome back</h2>
                    <p class="subtitle">Sign in to your account</p>
                    <div class="tabs">
                        <button class="tab active" onclick="switchTab('login')">Login</button>
                        <button class="tab" onclick="switchTab('register')">Register</button>
                    </div>
                    <form id="loginForm" onsubmit="handleSubmit(event)">
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" id="email" placeholder="you@example.com" required>
                        </div>
                        <div class="form-group">
                            <label>Password</label>
                            <input type="password" id="password" placeholder="Enter your password" required>
                        </div>
                        <div id="error" class="error" style="display: none;"></div>
                        <button type="submit" class="submit">Sign In</button>
                    </form>
                    <p style="margin-top: 24px; color: #8ea4c7; font-size: 13px; text-align: center;">
                        Build React app: cd python_app/web && npm run build
                    </p>
                </div>
            </div>
            <script>
                let currentTab = 'login';
                function switchTab(tab) {
                    currentTab = tab;
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    event.target.classList.add('active');
                    document.querySelector('.submit').textContent = tab === 'login' ? 'Sign In' : 'Create Account';
                }
                function handleSubmit(e) {
                    e.preventDefault();
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    if (window.bridge) {
                        if (currentTab === 'login') {
                            window.bridge.login(email, password);
                        } else {
                            window.bridge.register(email, password, '');
                        }
                    }
                }
            </script>
        </body>
        </html>
        """

    def set_auth_services(self, auth_client, token_store, license_gate):
        """Set authentication services."""
        self.bridge.set_auth_services(auth_client, token_store, license_gate)
