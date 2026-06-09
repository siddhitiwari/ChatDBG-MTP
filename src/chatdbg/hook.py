import sys
import traceback as _traceback


def install() -> None:
    """Register a sys.excepthook that auto-runs ChatDBG post-mortem analysis
    on any unhandled exception.

    Usage:
        import chatdbg
        chatdbg.install()

    After this call, any unhandled exception will print the normal traceback
    and then automatically run ChatDBG root cause analysis.
    """
    _original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (SystemExit, KeyboardInterrupt)):
            _original(exc_type, exc_value, exc_tb)
            return

        _original(exc_type, exc_value, exc_tb)

        tb_text = "".join(_traceback.format_exception(exc_type, exc_value, exc_tb))

        print("\n[ChatDBG] Analyzing crash...\n")
        try:
            from chatdbg.postmortem.analyze import analyze_crash_text

            analyze_crash_text(tb_text)
        except Exception:
            pass

    sys.excepthook = _hook
