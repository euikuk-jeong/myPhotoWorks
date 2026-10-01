"""Recommendation v2, stage 2 — evaluation replay with faces (plan §3-2, stage-2 completion
criterion "portrait / group 태그 top-1 개선").

``dev/eval_metrics.score_file(path, face_engine=None)``: the engine instance to use (the
evaluation script passes ``core.faces.get_face_engine()``); ``None`` means no faces. The same
analysis path as ``analyze_photo`` produces ``faces``, the legacy whole-frame fields stay filled.
``v2_rank`` / ``v2_tie`` follow the person chain through ``ranking.recommend``.
"""
from tests.synthetic import FACE, FakeFaceEngine, blend, person, scores, shallow_dof, to_rgb_image


def _file(tmp_path):
    path = tmp_path / "p.jpg"
    to_rgb_image(shallow_dof(seed=5)).save(path, "JPEG", quality=95)
    return path


def test_score_file_without_an_engine_has_no_faces(tmp_path):
    from myphotoworks.dev.eval_metrics import score_file

    assert score_file(_file(tmp_path)).faces is None


def test_score_file_with_an_engine_fills_faces_and_keeps_the_legacy_fields(tmp_path):
    from myphotoworks.core.faces import EYE_CLOSED_TH
    from myphotoworks.dev.eval_metrics import score_file

    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend(blink_l=EYE_CLOSED_TH + 0.3)])
    s = score_file(_file(tmp_path), face_engine=engine)
    assert s.faces.count == 1 and s.faces.closed_eyes == 1
    assert s.sharpness > 0 and s.exposure > 0                # baseline replay still works
    assert s.subject_source == "face"


def test_v2_rank_puts_faceless_photos_last_and_blinkers_after_open_eyes():
    from myphotoworks.dev.eval_metrics import v2_rank

    group = [scores(99, 99, 99), person(n=2, closed=1), person(n=2, closed=0)]
    assert v2_rank(group) == [2, 1, 0]


def test_v2_tie_reports_a_tied_person_group():
    from myphotoworks.dev.eval_metrics import v2_tie

    assert v2_tie([person(face_sharp=80.0), person(face_sharp=80.4)]) is True
    assert v2_tie([person(closed=1), person(closed=0)]) is False


def test_evaluate_hands_the_face_engine_to_the_scoring(tmp_path):
    """``evaluate(..., face_engine=...)``: without it the v2 replay would silently measure the
    stage-1 chain only (code review of stage 2)."""
    from myphotoworks.core.scoring import ALGORITHM_VERSION
    from myphotoworks.dev.eval_metrics import evaluate

    for name in ("a.jpg", "b.jpg"):
        to_rgb_image(shallow_dof(seed=5)).save(tmp_path / name, "JPEG", quality=95)
    label = {"schema": 1, "algorithm": ALGORITHM_VERSION, "root": str(tmp_path), "groups": [
        {"id": 0, "files": ["a.jpg", "b.jpg"], "picked": ["a.jpg"], "reviewed": True}]}
    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend(), blend()])
    report = evaluate([label], "v2", face_engine=engine)
    assert len(report.results) == 1 and len(engine.detect_shapes) == 2


def test_score_file_uses_the_fujifilm_af_point_like_the_grouping_run(tmp_path):
    from myphotoworks.dev.eval_metrics import score_file
    from tests.synthetic import fuji_jpeg

    path = fuji_jpeg(tmp_path / "af.jpg", shallow_dof(seed=5), focus_pixel=(800, 600))
    assert score_file(path).subject_source == "af"
