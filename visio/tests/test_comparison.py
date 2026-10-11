"""Regression checks for the isolated comparison adapters, without model downloads."""
import hashlib
import numpy as np
import pytest
import torch
from torch.nn import functional as F
from transformers import CLIPVisionConfig

from visio.compare_models import EffortNetwork, merge_effort_state


def test_effort_residual_merge_preserves_upstream_linear_forward():
    generator = torch.Generator().manual_seed(42)
    main = torch.randn(5, 7, generator=generator)
    u = torch.randn(5, 2, generator=generator)
    s = torch.randn(2, generator=generator)
    v = torch.randn(2, 7, generator=generator)
    bias = torch.randn(5, generator=generator)
    x = torch.randn(3, 4, 7, generator=generator)
    state = {"module.backbone.test." + name: value for name, value in
             [("weight_main", main), ("U_residual", u), ("S_residual", s), ("V_residual", v), ("bias", bias)]}
    merged = merge_effort_state(state)
    expected = F.linear(x, main + u @ torch.diag(s) @ v, bias)
    actual = F.linear(x, merged["backbone.test.weight"], merged["backbone.test.bias"])
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert set(merged) == {"backbone.test.weight", "backbone.test.bias"}


def test_effort_incomplete_residual_is_rejected():
    with pytest.raises(ValueError, match="Incomplete"):
        merge_effort_state({"a.weight_main": torch.ones(2, 2), "a.S_residual": torch.ones(1)})


def test_effort_head_uses_unnormalized_pooler():
    cfg = CLIPVisionConfig(hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                           num_attention_heads=4, image_size=28, patch_size=14)
    model = EffortNetwork(cfg).eval()
    pixels = torch.randn(2, 3, 28, 28)
    with torch.inference_mode():
        expected = model.head(model.backbone(pixels).pooler_output)
        torch.testing.assert_close(model(pixels), expected)


def test_effort_alignment_matches_upstream_golden():
    pytest.importorskip("skimage")
    from visio.comparison_effort_face import align_effort
    image = np.arange(200*240*3, dtype=np.uint32).reshape(200, 240, 3).astype(np.uint8)
    points = np.array([[80,70],[140,75],[110,103],[85,133],[134,135]], dtype=np.float32)
    crop = align_effort(image, points)
    # Generated with DeepfakeBench f188b1c... extract_aligned_face_dlib.img_align_crop.
    assert crop.shape == (256, 256, 3)
    assert hashlib.sha256(crop.tobytes()).hexdigest() == "28018947756481074123af676d89dad1d98e6e455f0fda3c3715ad593e1edd7a"
