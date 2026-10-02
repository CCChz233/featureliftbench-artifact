import pytest

from featurelifted import CycleDetected, MissingRevision, MultipleHeads, Revision, RevisionMap


def test_branch_labels_resolve_and_multiple_heads_raise():
    revisions = [
        Revision("base", None),
        Revision("left", "base", branch_labels={"feature"}),
        Revision("right", "base"),
    ]
    revmap = RevisionMap(revisions)

    assert revmap.get_revision("feature").revision == "left"
    with pytest.raises(MultipleHeads):
        revmap.get_current_head()


def test_branch_label_propagates_to_branch_head():
    revisions = [
        Revision("base", None),
        Revision("left", "base", branch_labels={"feature"}),
        Revision("left2", "left"),
        Revision("right", "base", branch_labels={"other"}),
    ]
    revmap = RevisionMap(revisions)

    assert revmap.get_current_head("feature") == "left2"
    assert revmap.get_current_head("other") == "right"
    assert revmap.branch_labels == {"feature": "left", "other": "right"}


def test_dependencies_affect_ancestors_without_removing_versioned_head():
    revisions = [
        Revision("base", None),
        Revision("feature_base", None, branch_labels={"feature"}),
        Revision("feature_tip", "feature_base"),
        Revision("main_tip", "base", dependencies=("feature",)),
    ]
    revmap = RevisionMap(revisions)

    assert revmap.get_heads() == ["feature_tip", "main_tip"]
    assert revmap.ancestors("main_tip") == {"base", "feature_base"}


def test_missing_down_revision_raises():
    with pytest.raises(MissingRevision):
        RevisionMap([Revision("b", "missing")])


def test_cycle_detection_raises():
    with pytest.raises(CycleDetected):
        RevisionMap([Revision("a", "c"), Revision("b", "a"), Revision("c", "b")])


def test_head_symbol_and_base_symbol_resolution():
    revmap = RevisionMap([Revision("a", None), Revision("b", "a")])

    assert revmap.get_revision("head").revision == "b"
    assert revmap.get_revision("base") is None
