import json
import sqlite3

import pytest

from contextiq.config import Settings
from contextiq.context.embedders import HashingEmbedder
from contextiq.engine import ContextEngine
from contextiq.synth.generate import generate

QUESTION = "Why did customer complaints increase last month, which products were affected, and what should we do?"


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    """A fully generated and indexed environment using the deterministic hashing embedder."""
    settings = Settings(generated_dir=tmp_path_factory.mktemp("gen"), embedder="hash")
    generate(settings)
    engine = ContextEngine(settings, embedder=HashingEmbedder())
    engine.index()
    return engine


@pytest.fixture(scope="session")
def settings(env):
    return env.settings


@pytest.fixture(scope="session")
def db(settings):
    conn = sqlite3.connect(settings.db_path)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def truth(settings):
    return json.loads(settings.ground_truth_path.read_text())


@pytest.fixture(scope="session")
def meta(env):
    return env.meta


@pytest.fixture(scope="session")
def question():
    return QUESTION
