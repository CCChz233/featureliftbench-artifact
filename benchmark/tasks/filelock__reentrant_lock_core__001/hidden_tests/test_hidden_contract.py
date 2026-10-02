from featurelifted import FileLock

def test_force_release_and_idempotence(tmp_path):
    lock = FileLock(tmp_path / "x.lock")
    lock.acquire(); lock.acquire()
    lock.release(force=True)
    assert not lock.is_locked
    lock.release()

def test_two_instances_can_acquire_sequentially(tmp_path):
    path = tmp_path / "x.lock"
    a, b = FileLock(path), FileLock(path)
    a.acquire(); a.release()
    with b:
        assert b.lock_counter == 1
