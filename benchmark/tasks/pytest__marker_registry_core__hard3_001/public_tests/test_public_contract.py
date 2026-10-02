
from featurelifted import MarkerRegistry


def test_from_ini_registers_markers():
    registry = MarkerRegistry.from_ini("slow: slow tests\nskip: skip marker")
    assert registry.get("slow").description == "slow tests"
