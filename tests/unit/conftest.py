import pytest

from regression_firewall.config.schema import Config, IgnoreConfig, NormalizationConfig
from regression_firewall.normalize.engine import Normalizer


@pytest.fixture
def cfg():
    return Config()


@pytest.fixture
def norm():
    return Normalizer(NormalizationConfig(), IgnoreConfig())

