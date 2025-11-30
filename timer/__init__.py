from collections.abc import Callable
import logging
from threading import Thread, Event

import sys
from types import TracebackType
from sortedcontainers import SortedList
import arrow 
import time

from base import ExecutionContext

task_list: SortedList = SortedList(key=lambda x: x.execute_at.timestamp())

class Task[**P, T]:
    def __init__(self, at: arrow.Arrow, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> None:
        def inner():
            return fn(*args, **kwargs)
        task_list.append(self)
        self.at = at
        self.fn = inner
        self.done = False
        self.res: T | None = None
        self.exception: tuple[type[BaseException], BaseException, TracebackType] | tuple[None, None, None] = (None, None, None)
        task_list.add(self)
        self.flag = Event()
    
    @property
    def remaining_time(self) -> float:
        return (self.at - arrow.now()).total_seconds()
    
    def _exec(self):
        if self.done:
            raise RuntimeError("Task already done")
        
        def runner():
            try:
                self.res = self.fn()
            except Exception as e:
                self.exception = sys.exc_info()
            self.done = True
            self.flag.set()
        thread = Thread(target=runner)
        thread.start()
        

    def get_result(self) -> T:
        if not self.done:
            raise RuntimeError("Task not done")
        if self.exception[0] is not None:
            raise self.exception[1].with_traceback(self.exception[2])
        return self.res # pyright: ignore[reportReturnType]
    
    def wait_until_result(self, timeout: float | None = None) -> T:
        self.flag.wait(timeout=timeout)
        return self.get_result()
    
    def peek_result(self) -> T | None:
        if self.done:
            return self.get_result()
        return None

    @property
    def execute_at(self) -> arrow.Arrow:
        return self.at

WAIT_TIME = 1.0
def runner():
    while True:
        if len(task_list) == 0:
            time.sleep(0.1)
        task: Task = task_list[0] # pyright: ignore[reportAssignmentType]
        if task.remaining_time <= 0:
            try:
                task._exec()
            except:
                logging.warning("Task failed", exc_info=True)
            task_list.pop(0)
        elif 0 < task.remaining_time < WAIT_TIME:
            time.sleep(task.remaining_time)
        else:
            time.sleep(0.1)
        
def start(client: ExecutionContext):
    thread_proj = Thread(target=runner)
    thread_proj.start()