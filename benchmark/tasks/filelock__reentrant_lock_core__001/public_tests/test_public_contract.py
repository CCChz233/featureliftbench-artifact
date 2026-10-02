import pytest
from featurelifted import FileLock, Timeout

def test_context_and_reentrant_release(tmp_path):
    path = tmp_path / "demo.lock"
    lock = FileLock(path)
    with lock:
        assert lock.is_locked and path.exists()
        lock.acquire()
        lock.release()
        assert lock.is_locked
    assert not lock.is_locked and not path.exists()

def test_nonblocking_contention(tmp_path):
    path = tmp_path / "demo.lock"
    first, second = FileLock(path), FileLock(path)
    first.acquire()
    with pytest.raises(Timeout):
        second.acquire(timeout=0)
    first.release()
