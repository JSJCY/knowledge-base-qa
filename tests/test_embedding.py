import numpy as np

from app.services.embedding import EmbeddingService, bytes_to_vec, normalize, vec_to_bytes


def test_vec_bytes_roundtrip():
    vec = [0.1, -0.2, 0.35]
    restored = bytes_to_vec(vec_to_bytes(vec))
    assert np.allclose(restored, vec, atol=1e-6)


def test_normalize_unit_length():
    v = normalize(np.array([3.0, 4.0]))
    assert np.isclose(float(np.linalg.norm(v)), 1.0)


def test_normalize_zero_vector_is_safe():
    v = normalize(np.zeros(3))
    assert np.allclose(v, 0.0)


def test_embed_empty_list_without_loading_model():
    service = EmbeddingService("never/loaded")
    assert service.embed([]) == []
    assert service._model is None
