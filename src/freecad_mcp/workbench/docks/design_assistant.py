"""Design assistant dock for operation history and MCP responses."""

from __future__ import annotations

from typing import Any

from freecad_mcp.workbench.qt import load_qt_widgets


class DesignAssistantDock:
    title = "MCP Design Assistant"

    def __init__(self, parent: Any | None = None) -> None:
        self.history: list[str] = []
        self.parent = parent
        self.session: Any | None = None
        self.widget = self._build_widget()

    def set_session(self, session: Any) -> None:
        self.session = session

    def refresh_from_session(self) -> list[str]:
        if self.session is not None:
            return self.refresh(self.session.history)
        return self.refresh()

    def append_message(self, message: str) -> list[str]:
        self.history.append(message)
        self._render()
        return self.history

    def refresh(self, messages: list[str] | None = None) -> list[str]:
        if messages is not None:
            self.history = list(messages)
        self._render()
        return self.history

    def _build_widget(self) -> Any:
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return None
        dock = widgets.QDockWidget(self.title, self.parent)
        dock.setObjectName("MCPDesignAssistantDock")
        root = widgets.QWidget()
        layout = widgets.QVBoxLayout(root)
        text = widgets.QTextEdit()
        text.setReadOnly(True)
        layout.addWidget(text)
        controls = widgets.QHBoxLayout()
        prompt = widgets.QLineEdit()
        prompt.setPlaceholderText("make a bracket")
        run_button = widgets.QPushButton("Run")
        controls.addWidget(prompt)
        controls.addWidget(run_button)
        layout.addLayout(controls)
        run_button.clicked.connect(self._run_prompt)
        prompt.returnPressed.connect(self._run_prompt)
        dock.setWidget(root)
        self._text = text
        self._prompt = prompt
        return dock

    def _render(self) -> None:
        text = getattr(self, "_text", None)
        if text is not None:
            text.setPlainText("\n".join(self.history))

    def _run_prompt(self) -> None:
        prompt_widget = getattr(self, "_prompt", None)
        prompt = prompt_widget.text().strip() if prompt_widget is not None else ""
        if not prompt or self.session is None:
            return
        path = self.session.refresh_document()

        def execute() -> dict[str, Any]:
            return self.session.service.assistant_execute(prompt, path=path)

        result = self.session.run(f"Assistant prompt: {prompt}", execute)
        if result is not None:
            self.append_message(str(result))
