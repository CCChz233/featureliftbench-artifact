from featurelifted import Backend, ChainerBackend, MemoryBackend, select_backend


class Low(Backend):
    priority = 0.1
    name = "low"

    def get_password(self, service, username):
        return "low"


class High(Backend):
    priority = 5
    name = "high"

    def get_password(self, service, username):
        return "high"


def test_select_highest_priority_backend():
    assert isinstance(select_backend([Low, High]), High)


def test_env_override_selects_named_backend():
    selected = select_backend([Low, High], env={"PYTHON_KEYRING_BACKEND": "low"})

    assert isinstance(selected, Low)


def test_chainer_get_password_uses_first_backend_with_value():
    first = MemoryBackend("first", priority=5)
    second = MemoryBackend("second", priority=1)
    second.set_password("svc", "user", "secret")

    backend = ChainerBackend([first, second])

    assert backend.get_password("svc", "user") == "secret"
