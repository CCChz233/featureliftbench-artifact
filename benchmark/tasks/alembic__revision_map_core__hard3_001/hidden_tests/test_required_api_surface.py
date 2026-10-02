"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Revision,
    RevisionMap,
    CycleDetected,
    MissingRevision,
    MultipleHeads,
)


def test_required_api_surface():
    assert isinstance(Revision, type)
    assert isinstance(RevisionMap, type)
    assert RevisionMap is not None
    assert RevisionMap is not None
    assert RevisionMap is not None
    assert hasattr(RevisionMap, 'get_revision')
    assert hasattr(RevisionMap, 'get_revisions')
    assert hasattr(RevisionMap, 'get_heads')
    assert hasattr(RevisionMap, 'get_current_head')
    assert hasattr(RevisionMap, 'ancestors')
    assert hasattr(RevisionMap, 'iterate_revisions')
    assert issubclass(CycleDetected, BaseException)
    assert issubclass(MissingRevision, BaseException)
    assert issubclass(MultipleHeads, BaseException)
    revision_map = RevisionMap([Revision("base"), Revision("head", "base")])
    assert hasattr(revision_map, 'heads')
    assert hasattr(revision_map, 'bases')
    assert hasattr(revision_map, 'branch_labels')
