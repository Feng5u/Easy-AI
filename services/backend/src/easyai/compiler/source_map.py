"""Append-only code writer: mappings always refer to final, unformatted lines."""

from typing import Literal

from easyai.domain.contracts import Origin, SourceSpan


def locate_line(spans: list[SourceSpan], line: int) -> SourceSpan | None:
    """Prefer the narrowest semantic hit, then an enclosing scaffold span."""
    hits = [span for span in spans if span.start_line <= line <= span.end_line]
    return min(
        hits,
        key=lambda span: (span.kind != "semantic", span.end_line - span.start_line),
        default=None,
    )


class CodeWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.spans: list[SourceSpan] = []

    def line(
        self,
        text: str = "",
        origin: Origin | None = None,
        kind: Literal["semantic", "scaffold"] = "semantic",
    ) -> None:
        self.lines.append(text)
        if origin is not None and text.strip():
            number = len(self.lines)
            self.spans.append(
                SourceSpan(start_line=number, end_line=number, origin=origin, kind=kind)
            )

    def code(self) -> str:
        return "\n".join(self.lines) + "\n"
