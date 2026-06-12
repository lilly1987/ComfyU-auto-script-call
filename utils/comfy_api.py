# -*- coding: utf-8 -*-
"""ComfyUI API utilities."""
import json
import time
from typing import Dict, Any, Optional, Tuple
from urllib import request
from urllib.error import URLError, HTTPError
from rich.progress import Progress

from .dict_utils import convert_paths
from .print_log import print, logger


def _get_win_error(exc: BaseException) -> Optional[int]:
    reason = getattr(exc, "reason", exc)
    return getattr(reason, "winerror", None)


def queue_prompt(prompt: Dict[str, Any], url: str = "http://127.0.0.1:8188/prompt") -> Tuple[bool, Optional[int]]:
    """
    Add a workflow prompt to the ComfyUI queue.

    Returns:
        Tuple[bool, Optional[int]]: success flag and HTTP status code when available.
    """
    try:
        p = {"prompt": prompt}
        p = convert_paths(p)
        data = json.dumps(p).encode("utf-8")
        req = request.Request(url, data=data)
    except TypeError:
        print.exception(show_locals=True)
        print.Err("Prompt conversion error:", prompt)
        return False, None
    except Exception:
        print.exception(show_locals=True)
        return False, None

    while True:
        try:
            request.urlopen(req)
            print("Prompt queued")
            return True, None
        except HTTPError as e:
            print.Err("Prompt content:", prompt)
            print.Err("HTTP error code:", e.code)
            logger.exception("HTTPError occurred: %s, prompt: %s", e, prompt)
            try:
                with open(time.strftime("log/prompt-%Y%m%d-%H%M%S.json"), "w", encoding="utf-8") as f:
                    json.dump(prompt, f, indent=2, ensure_ascii=False)
            except Exception as dump_error:
                logger.error("Failed to save prompt JSON: %s", dump_error)
            return False, e.code
        except URLError as e:
            win_error = _get_win_error(e)
            if win_error is not None:
                print.Warn("WinError:", win_error, e.reason)
                logger.debug("WinError during queue_prompt, will retry: %s", e)
                time.sleep(1)
                continue

            print.Warn("URL error:", e.reason)
            logger.exception("URLError occurred: %s", e)
            return False, None
        except Exception as e:
            logger.exception("Error occurred: %s", e)
            return False, None


def queue_prompt_wait(url: str = "http://127.0.0.1:8188/prompt", max_queue: int = 1) -> bool:
    """
    Wait until the ComfyUI queue has no more than the configured number of jobs.

    Returns:
        True when an error should stop the caller; otherwise returns None for legacy behavior.
    """
    start_time = time.time()

    with Progress() as progress:
        task = progress.add_task("Waiting", total=None)

        while True:
            try:
                with request.urlopen(url) as response:
                    data = json.loads(response.read().decode())
                    queue_remaining = data["exec_info"]["queue_remaining"]

                    elapsed = int(time.time() - start_time)
                    progress.update(task, description=f"Elapsed: {elapsed}s")

                    if queue_remaining == 0:
                        break

                time.sleep(1)
            except (URLError, ConnectionRefusedError, ConnectionResetError) as e:
                logger.debug("Ignoring connection error, will retry: %s", e)
                time.sleep(1)
                continue
            except Exception as e:
                logger.error("Error occurred: %s", e)
