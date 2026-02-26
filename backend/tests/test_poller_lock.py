from app.poller_lock import PollerFileLock


def test_poller_lock_acquire_release(tmp_path) -> None:
    lock_path = tmp_path / "poller.lock"
    lock1 = PollerFileLock(lock_path)
    assert lock1.acquire(non_blocking=True) is True

    lock2 = PollerFileLock(lock_path)
    assert lock2.acquire(non_blocking=True) is False

    lock1.release()
    assert lock2.acquire(non_blocking=True) is True
    lock2.release()
