"""Subprocess CLI 适配器基类 — 共享 cancel_event 看门狗、进程组回收与 stdout 流式读取。"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from threading import Event
from typing import Callable, Generator, Iterable, Optional

from adapter.events import AgentEvent, EventKind
from adapter.protocol import CLIAdapter


class SubprocessCLIAdapter(CLIAdapter):
    """基于 subprocess 的 CLI 后端基类；子类只负责拼命令行与 parse_line。"""

    CANCEL_POLL_SEC = 0.3

    @staticmethod
    def terminate_process_group(proc: Optional[subprocess.Popen]) -> None:
        """杀掉整个进程组（start_new_session=True 时子进程同组）。

        先 SIGTERM 整组、给 2s 退出窗口，未退则 SIGKILL；拿不到进程组时退回单进程 kill。
        """
        if proc is None or proc.poll() is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, OSError):
            pgid = None
        try:
            if pgid is not None:
                os.killpg(pgid, signal.SIGTERM)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=2)
                return
            except subprocess.TimeoutExpired:
                pass
            if pgid is not None:
                os.killpg(pgid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=2)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            pass

    def stream_subprocess_io(
        self,
        proc: subprocess.Popen,
        *,
        message: str,
        cancel_event: Optional[Event],
        parse_line: Callable[[str], Iterable[AgentEvent]],
    ) -> Generator[AgentEvent, None, None]:
        """写入 stdin、逐行读 stdout 并 yield 事件；支持 cancel_event 与 stderr 汇总。"""
        cancelled = False
        stop_watch = threading.Event()
        watcher: Optional[threading.Thread] = None
        stderr_buf: list[str] = []

        def _drain_stderr() -> None:
            try:
                if proc.stderr:
                    stderr_buf.append(proc.stderr.read())
            except Exception:
                pass

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        # cancel_event 置位时 stdout 可能仍阻塞读；旁路线程杀进程组以解除阻塞并回收子进程。
        if cancel_event is not None:
            def _canceller(
                p: subprocess.Popen = proc,
                ev: Event = cancel_event,
                stop: threading.Event = stop_watch,
            ) -> None:
                while not stop.wait(self.CANCEL_POLL_SEC):
                    if p.poll() is not None:
                        return
                    if ev.is_set():
                        self.terminate_process_group(p)
                        return

            watcher = threading.Thread(target=_canceller, daemon=True)
            watcher.start()

        try:
            try:
                proc.stdin.write(message)
            except Exception:
                pass
            proc.stdin.close()

            # 先 yield 当前行事件，再检查 cancel，保证 step_finish / result 行仍能被读出。
            for line in proc.stdout:
                for ev in parse_line(line):
                    yield ev
                if cancel_event and cancel_event.is_set():
                    cancelled = True

            if cancelled:
                return

            proc.wait()
            stderr_thread.join(timeout=2.0)
            stderr_out = "".join(stderr_buf)
            if stderr_out.strip():
                yield AgentEvent(EventKind.ERROR, {"message": stderr_out.strip()})
        finally:
            stop_watch.set()
            self.terminate_process_group(proc)
            if watcher is not None:
                watcher.join(timeout=1)
